"""Durable transcript capture: a profile-scoped SQLite queue between Hermes's
turn hooks and ``/ingest/session``.

Why a queue on disk. A turn that only lives in process memory is lost by a
crash, a kill, or a server outage that outlasts the process. Here every turn is
committed to ``$HERMES_HOME/mindgraph/capture.db`` before ``sync_turn`` returns,
sealed into batches at the flush points, and delivered at least once: a batch
leaves the queue only when the server accepted it, and a new process picks up
whatever an earlier one left behind.

Why batches carry a tag. ``/ingest/session`` has no idempotency key: every call
creates a Document. A request that timed out may or may not have landed, so the
batch tag (a digest of its content) is written into the transcript title and a
retry first looks for a job with that tag before sending again.

Why two ledgers. The pre-compress checkpoint hands over transcript rows that
``sync_turn`` has mostly captured already, and may run ahead of the turn it
interrupts. ``seen`` stops the checkpoint re-archiving what a turn delivered;
``prepaid`` stops the turn re-sending what the checkpoint archived first.

This module does not import Hermes.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# Undelivered text the queue will hold. Past it the oldest undelivered batches
# are dropped, counted and reported: a server that is down for good must not
# fill the disk, and a silent drop is the failure this module exists to remove.
MAX_PENDING_CHARS = 20_000_000
# One /ingest/session body. Larger batches are split at part boundaries.
MAX_BATCH_CHARS = 200_000
RETRY_BASE_S = 5.0
RETRY_MAX_S = 900.0
# A delivery holds its batch this long. A crashed process's lease expires and
# another process (or the next start) takes the batch over.
LEASE_S = 120.0
# A batch the server keeps failing on is parked after this many attempts so it
# cannot hold every later batch behind it. Its text stays in the queue.
MAX_ATTEMPTS = 10
# Receipts and ledgers older than this are pruned; undelivered text never is.
RETENTION_S = 30 * 86_400.0
_WS = re.compile(r"\s+")

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    digest TEXT NOT NULL,
    origin TEXT NOT NULL,
    created_at REAL NOT NULL,
    batch_id TEXT
);
CREATE INDEX IF NOT EXISTS parts_open ON parts (batch_id, session, id);
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    session TEXT NOT NULL,
    origin TEXT NOT NULL,
    chars INTEGER NOT NULL,
    part_count INTEGER NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL DEFAULT 0,
    uncertain INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    job_id TEXT,
    document_uid TEXT,
    job_status TEXT,
    created_at REAL NOT NULL,
    delivered_at REAL,
    lease_owner TEXT,
    lease_until REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS batches_state ON batches (state, created_at);
CREATE TABLE IF NOT EXISTS seen (
    session TEXT NOT NULL,
    digest TEXT NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (session, digest)
);
CREATE TABLE IF NOT EXISTS prepaid (
    session TEXT NOT NULL,
    digest TEXT NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (session, digest)
);
"""


class CaptureError(RuntimeError):
    """The queue could not commit. A checkpoint that sees this must not report success."""


class DeliveryRejected(Exception):
    """The server refused the batch and will refuse it again unchanged (a 4xx
    other than auth, rate limit or timeout). The batch is parked, not retried."""


@dataclass(frozen=True)
class Batch:
    batch_id: str
    session: str
    origin: str
    content: str
    part_count: int
    attempts: int
    uncertain: bool

    @property
    def tag(self) -> str:
        return self.batch_id[:12]


@dataclass(frozen=True)
class Receipt:
    job_id: Optional[str] = None
    document_uid: Optional[str] = None


def part_digest(session: str, role: str, text: str) -> str:
    """Identity of one transcript row. Whitespace is collapsed so the same
    message handed over by two hooks hashes alike."""
    normalized = _WS.sub(" ", text).strip()
    return hashlib.sha256(f"{session}\x1f{role}\x1f{normalized}".encode()).hexdigest()


def render_parts(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{'User' if role == 'user' else 'Assistant'}: {text}" for role, text in parts)


def retry_delay(attempts: int) -> float:
    return min(RETRY_BASE_S * (2 ** max(attempts - 1, 0)), RETRY_MAX_S)


class CaptureQueue:
    """One profile's capture queue. Safe across threads (one lock, one
    connection) and across processes sharing the profile (WAL, leases)."""

    def __init__(self, path: Optional[Path], *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._owner = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.path = path
        self.durable = path is not None
        target = str(path) if path is not None else ":memory:"
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: transactions are explicit, so a multi-statement
        # seal either commits whole or not at all.
        self._db = sqlite3.connect(target, timeout=10.0, isolation_level=None, check_same_thread=False)
        self._db.execute("PRAGMA busy_timeout = 10000")
        if path is not None:
            self._db.execute("PRAGMA journal_mode = WAL")
            # FULL: a committed turn survives power loss, which is what a
            # checkpoint that reports success is claiming.
            self._db.execute("PRAGMA synchronous = FULL")
            try:
                os.chmod(path, 0o600)  # transcript text; the profile owner only
            except OSError:
                pass
        self._db.executescript(_DDL)
        self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
        )

    @classmethod
    def open(cls, hermes_home: Optional[str], *, clock: Callable[[], float] = time.time) -> "CaptureQueue":
        """The profile's queue, or an in-memory one when the profile directory
        cannot hold it. The fallback keeps capture working for the life of the
        process and reports itself as not durable."""
        if hermes_home:
            path = Path(hermes_home) / "mindgraph" / "capture.db"
            try:
                return cls(path, clock=clock)
            except (OSError, sqlite3.Error) as exc:
                logger.warning(
                    "MindGraph capture queue unavailable at %s (%s); turns are held in memory only", path, exc
                )
        return cls(None, clock=clock)

    def close(self) -> None:
        with self._lock:
            try:
                self._db.close()
            except sqlite3.Error:
                pass

    # ── Writes ─────────────────────────────────────────────────────────────

    def _tx(self, work: Callable[[], Any]) -> Any:
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    result = work()
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                self._db.execute("COMMIT")
                return result
            except sqlite3.Error as exc:
                raise CaptureError(f"capture queue write failed: {exc}") from exc

    def add_turn(self, session: str, user: str, assistant: str) -> int:
        """Commit one completed turn; returns undelivered characters still open
        (unsealed) for the flush threshold."""
        now = self._clock()

        def work() -> int:
            for role, text in (("user", user), ("assistant", assistant)):
                if not text:
                    continue
                digest = part_digest(session, role, text)
                spent = self._db.execute(
                    "DELETE FROM prepaid WHERE session = ? AND digest = ?", (session, digest)
                ).rowcount
                if spent:
                    continue  # the checkpoint archived this row before its turn completed
                self._db.execute(
                    "INSERT INTO parts (session, role, text, digest, origin, created_at) VALUES (?, ?, ?, ?, 'turn', ?)",
                    (session, role, text, digest, now),
                )
                self._db.execute(
                    "INSERT OR IGNORE INTO seen (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                )
            return self._open_chars()

        return self._tx(work)

    def add_evidence(self, session: str, rows: Iterable[tuple[str, str]]) -> int:
        """Commit the checkpoint's transcript rows that no hook has captured yet;
        returns how many were new. Idempotent: the same transcript again adds nothing."""
        now = self._clock()

        def work() -> int:
            added = 0
            for role, text in rows:
                if role not in ("user", "assistant") or not text:
                    continue
                digest = part_digest(session, role, text)
                fresh = self._db.execute(
                    "INSERT OR IGNORE INTO seen (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                ).rowcount
                if not fresh:
                    continue
                self._db.execute(
                    "INSERT INTO parts (session, role, text, digest, origin, created_at) "
                    "VALUES (?, ?, ?, ?, 'checkpoint', ?)",
                    (session, role, text, digest, now),
                )
                self._db.execute(
                    "INSERT OR IGNORE INTO prepaid (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                )
                added += 1
            return added

        return self._tx(work)

    def _open_chars(self) -> int:
        row = self._db.execute("SELECT COALESCE(SUM(LENGTH(text)), 0) FROM parts WHERE batch_id IS NULL").fetchone()
        return int(row[0])

    def seal(self, session: Optional[str] = None) -> list[str]:
        """Group open parts into batches, one conversation at a time and in turn
        order. A batch's id is a digest of its content, so sealing is the point
        at which a retry becomes recognizable."""
        now = self._clock()

        def work() -> list[str]:
            sealed: list[str] = []
            where = "batch_id IS NULL" + (" AND session = ?" if session is not None else "")
            args: tuple = (session,) if session is not None else ()
            rows = self._db.execute(
                f"SELECT id, session, role, text, origin FROM parts WHERE {where} ORDER BY id", args
            ).fetchall()
            groups: dict[str, list[tuple]] = {}
            for row in rows:
                groups.setdefault(row[1], []).append(row)
            for sess, members in groups.items():
                chunk: list[tuple] = []
                size = 0
                for row in members:
                    length = len(row[3])
                    if chunk and size + length > MAX_BATCH_CHARS:
                        sealed.append(self._seal_chunk(sess, chunk, now))
                        chunk, size = [], 0
                    chunk.append(row)
                    size += length
                if chunk:
                    sealed.append(self._seal_chunk(sess, chunk, now))
            self._enforce_bound(now)
            return sealed

        return self._tx(work)

    def _seal_chunk(self, session: str, rows: list[tuple], now: float) -> str:
        digest = hashlib.sha256()
        digest.update(session.encode())
        for row in rows:
            digest.update(f"\x1e{row[0]}\x1f{row[2]}\x1f{row[3]}".encode())
        batch_id = digest.hexdigest()
        origin = "checkpoint" if all(row[4] == "checkpoint" for row in rows) else "turn"
        self._db.execute(
            "INSERT INTO batches (batch_id, session, origin, chars, part_count, state, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'sealed', ?)",
            (batch_id, session, origin, sum(len(row[3]) for row in rows), len(rows), now),
        )
        self._db.executemany("UPDATE parts SET batch_id = ? WHERE id = ?", [(batch_id, row[0]) for row in rows])
        return batch_id

    def _enforce_bound(self, now: float) -> None:
        total = int(
            self._db.execute("SELECT COALESCE(SUM(chars), 0) FROM batches WHERE state IN ('sealed', 'failed')").fetchone()[0]
        )
        if total <= MAX_PENDING_CHARS:
            return
        for batch_id, chars in self._db.execute(
            "SELECT batch_id, chars FROM batches WHERE state IN ('sealed', 'failed') ORDER BY created_at, batch_id"
        ).fetchall():
            if total <= MAX_PENDING_CHARS:
                break
            self._db.execute("DELETE FROM parts WHERE batch_id = ?", (batch_id,))
            self._db.execute(
                "UPDATE batches SET state = 'dropped', last_error = 'queue bound exceeded', delivered_at = ? "
                "WHERE batch_id = ?",
                (now, batch_id),
            )
            total -= int(chars)
            logger.warning(
                "MindGraph capture queue is over %d characters; dropped undelivered batch %s (%d characters)",
                MAX_PENDING_CHARS, batch_id[:12], chars,
            )

    def discard_session(self, session: str) -> int:
        """/undo: nothing unsent from this conversation becomes durable. Returns
        the parts removed. Their ledger entries go too, so text said again after
        the undo is captured again."""

        def work() -> int:
            rows = self._db.execute(
                "SELECT p.id, p.digest FROM parts p LEFT JOIN batches b ON b.batch_id = p.batch_id "
                "WHERE p.session = ? AND (p.batch_id IS NULL OR b.state IN ('sealed', 'failed'))",
                (session,),
            ).fetchall()
            if not rows:
                return 0
            self._db.executemany("DELETE FROM parts WHERE id = ?", [(row[0],) for row in rows])
            for table in ("seen", "prepaid"):
                self._db.executemany(
                    f"DELETE FROM {table} WHERE session = ? AND digest = ?", [(session, row[1]) for row in rows]
                )
            self._db.execute(
                "DELETE FROM batches WHERE session = ? AND state IN ('sealed', 'failed') "
                "AND batch_id NOT IN (SELECT DISTINCT batch_id FROM parts WHERE batch_id IS NOT NULL)",
                (session,),
            )
            return len(rows)

        return self._tx(work)

    # ── Delivery ───────────────────────────────────────────────────────────

    def claim(self, *, force: bool = False) -> Optional[Batch]:
        """Lease the oldest sealed batch, or nothing while it is backing off or
        another live process holds it: batches reach the server in turn order,
        so a newer one never overtakes it. ``force`` ignores the backoff (a
        flush point is a reason to try now), never a live lease."""
        now = self._clock()

        def work() -> Optional[Batch]:
            row = self._db.execute(
                "SELECT batch_id, session, origin, part_count, attempts, uncertain, next_attempt_at, "
                "lease_owner, lease_until FROM batches WHERE state = 'sealed' ORDER BY created_at, batch_id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            if row[8] > now and row[7] != self._owner:
                return None
            if not force and row[6] > now:
                return None
            self._db.execute(
                "UPDATE batches SET lease_owner = ?, lease_until = ? WHERE batch_id = ?",
                (self._owner, now + LEASE_S, row[0]),
            )
            parts = self._db.execute(
                "SELECT role, text FROM parts WHERE batch_id = ? ORDER BY id", (row[0],)
            ).fetchall()
            return Batch(row[0], row[1], row[2], render_parts(parts), row[3], row[4], bool(row[5]))

        return self._tx(work)

    def mark_delivered(self, batch_id: str, receipt: Receipt) -> None:
        now = self._clock()

        def work() -> None:
            self._db.execute(
                "UPDATE batches SET state = 'delivered', delivered_at = ?, job_id = ?, document_uid = ?, "
                "last_error = NULL, uncertain = 0, lease_owner = NULL, lease_until = 0 WHERE batch_id = ?",
                (now, receipt.job_id, receipt.document_uid, batch_id),
            )
            # The server holds the text now; the queue keeps only the receipt.
            self._db.execute("DELETE FROM parts WHERE batch_id = ?", (batch_id,))

        self._tx(work)

    def mark_retry(self, batch_id: str, error: str, *, uncertain: bool) -> None:
        """Delivery failed in a way a later attempt may fix. ``uncertain`` records
        that the request may have reached the server, so the next attempt
        reconciles before it resends."""
        now = self._clock()

        def work() -> None:
            attempts = self._db.execute("SELECT attempts FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
            count = (int(attempts[0]) if attempts else 0) + 1
            self._db.execute(
                "UPDATE batches SET attempts = ?, next_attempt_at = ?, last_error = ?, "
                "uncertain = MAX(uncertain, ?), lease_owner = NULL, lease_until = 0 WHERE batch_id = ?",
                (count, now + retry_delay(count), error[:500], int(uncertain), batch_id),
            )

        self._tx(work)

    def mark_failed(self, batch_id: str, error: str) -> None:
        """The server will not take this batch as it is. Parked with its text so
        nothing is lost; ``retry_failed`` returns it to the queue."""

        def work() -> None:
            self._db.execute(
                "UPDATE batches SET state = 'failed', attempts = attempts + 1, last_error = ?, "
                "lease_owner = NULL, lease_until = 0 WHERE batch_id = ?",
                (error[:500], batch_id),
            )

        self._tx(work)

    def retry_failed(self) -> int:
        def work() -> int:
            return self._db.execute(
                "UPDATE batches SET state = 'sealed', next_attempt_at = 0, uncertain = 0 WHERE state = 'failed'"
            ).rowcount

        return self._tx(work)

    def set_job_status(self, batch_id: str, status: str, error: Optional[str] = None) -> None:
        def work() -> None:
            self._db.execute(
                "UPDATE batches SET job_status = ?, last_error = COALESCE(?, last_error) WHERE batch_id = ?",
                (status, error[:500] if error else None, batch_id),
            )

        self._tx(work)

    def unsettled_receipts(self, limit: int = 5) -> list[tuple[str, str]]:
        """Delivered batches whose extraction job has no terminal status recorded."""
        with self._lock:
            rows = self._db.execute(
                "SELECT batch_id, job_id FROM batches WHERE state = 'delivered' AND job_id IS NOT NULL "
                "AND (job_status IS NULL OR job_status NOT IN ('completed', 'failed', 'cancelled', 'unknown')) "
                "ORDER BY delivered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def prune(self) -> None:
        """Forget receipts and ledger rows past retention. Never touches undelivered text."""
        cutoff = self._clock() - RETENTION_S

        def work() -> None:
            self._db.execute(
                "DELETE FROM batches WHERE state IN ('delivered', 'dropped') AND COALESCE(delivered_at, created_at) < ?",
                (cutoff,),
            )
            self._db.execute("DELETE FROM seen WHERE at < ?", (cutoff,))
            self._db.execute("DELETE FROM prepaid WHERE at < ?", (cutoff,))

        try:
            self._tx(work)
        except CaptureError as exc:  # housekeeping never fails a turn
            logger.debug("MindGraph capture queue prune failed: %s", exc)

    # ── Status ─────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """What is waiting, what failed and what was last delivered: the
        observable side of at-least-once."""
        with self._lock:
            open_parts, open_chars = self._db.execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(text)), 0) FROM parts WHERE batch_id IS NULL"
            ).fetchone()
            counts = dict(self._db.execute("SELECT state, COUNT(*) FROM batches GROUP BY state").fetchall())
            pending_chars = self._db.execute(
                "SELECT COALESCE(SUM(chars), 0) FROM batches WHERE state = 'sealed'"
            ).fetchone()[0]
            oldest = self._db.execute(
                "SELECT MIN(created_at) FROM batches WHERE state IN ('sealed', 'failed')"
            ).fetchone()[0]
            last = self._db.execute(
                "SELECT delivered_at, job_id, document_uid, job_status FROM batches WHERE state = 'delivered' "
                "ORDER BY delivered_at DESC LIMIT 1"
            ).fetchone()
            error = self._db.execute(
                "SELECT last_error, attempts, next_attempt_at, state FROM batches "
                "WHERE state IN ('sealed', 'failed') AND last_error IS NOT NULL ORDER BY created_at LIMIT 1"
            ).fetchone()
            failed_jobs = self._db.execute(
                "SELECT COUNT(*) FROM batches WHERE state = 'delivered' AND job_status = 'failed'"
            ).fetchone()[0]
        report: dict[str, Any] = {
            "durable": self.durable,
            "buffered_parts": int(open_parts),
            "buffered_chars": int(open_chars),
            "pending_batches": int(counts.get("sealed", 0)),
            "pending_chars": int(pending_chars),
            "failed_batches": int(counts.get("failed", 0)),
            "dropped_batches": int(counts.get("dropped", 0)),
            "delivered_batches": int(counts.get("delivered", 0)),
            "failed_extraction_jobs": int(failed_jobs),
        }
        if oldest is not None:
            report["oldest_pending_age_s"] = max(0, int(self._clock() - oldest))
        if last is not None:
            report["last_delivery"] = {
                key: value
                for key, value in (
                    ("at", _iso(last[0])), ("job_id", last[1]), ("document_uid", last[2]), ("job_status", last[3]),
                )
                if value is not None
            }
        if error is not None:
            report["last_error"] = {
                "message": error[0],
                "attempts": int(error[1]),
                "state": "parked" if error[3] == "failed" else "retrying",
                **({"next_attempt_in_s": max(0, int(error[2] - self._clock()))} if error[3] == "sealed" else {}),
            }
        return report


def _iso(stamp: Optional[float]) -> Optional[str]:
    if stamp is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))


# ── Delivery ───────────────────────────────────────────────────────────────


class DeliveryUncertain(Exception):
    """The request may have reached the server (a timeout, a dropped connection,
    a 5xx). The next attempt reconciles before it resends."""


@dataclass
class DrainResult:
    delivered: int = 0
    reconciled: int = 0
    parked: int = 0
    blocked: Optional[str] = None  # why the drain stopped with batches still queued


class Deliverer:
    """Moves sealed batches to the server, oldest first.

    ``send`` delivers one batch and returns its receipt. It raises
    ``DeliveryRejected`` when the server will never take the batch,
    ``DeliveryUncertain`` when the outcome is unknown, and anything else for a
    failure that certainly did not land. ``find`` looks for a batch the server
    already holds and returns its receipt, ``None`` when it is certainly absent,
    and raises when it cannot tell.
    """

    def __init__(
        self,
        queue: CaptureQueue,
        send: Callable[[Batch], Receipt],
        find: Callable[[Batch], Optional[Receipt]],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._queue = queue
        self._send = send
        self._find = find
        self._clock = clock
        # One drain at a time per provider; the lease covers other processes.
        self._lock = threading.Lock()

    def drain(self, *, force: bool = False, budget_s: Optional[float] = None) -> DrainResult:
        result = DrainResult()
        deadline = None if budget_s is None else self._clock() + budget_s
        # A routine drain yields to one already running; a flush point waits its turn.
        if not self._lock.acquire(blocking=force):
            return result
        try:
            while deadline is None or self._clock() < deadline:
                try:
                    batch = self._queue.claim(force=force)
                except CaptureError as exc:
                    result.blocked = str(exc)
                    break
                if batch is None:
                    break
                if not self._deliver(batch, result):
                    break
        finally:
            self._lock.release()
        return result

    def _deliver(self, batch: Batch, result: DrainResult) -> bool:
        """True when the queue may move on to the next batch."""
        if batch.uncertain:
            try:
                receipt = self._find(batch)
            except Exception as exc:
                self._queue.mark_retry(batch.batch_id, f"could not verify an earlier attempt: {exc}", uncertain=True)
                result.blocked = str(exc)
                return False
            if receipt is not None:
                self._queue.mark_delivered(batch.batch_id, receipt)
                result.reconciled += 1
                return True
        try:
            receipt = self._send(batch)
        except DeliveryRejected as exc:
            self._queue.mark_failed(batch.batch_id, str(exc))
            logger.warning("MindGraph refused transcript batch %s; parked: %s", batch.tag, exc)
            result.parked += 1
            return True
        except Exception as exc:
            if batch.attempts + 1 >= MAX_ATTEMPTS:
                self._queue.mark_failed(batch.batch_id, f"gave up after {batch.attempts + 1} attempts: {exc}")
                logger.warning("MindGraph transcript batch %s parked after repeated failures: %s", batch.tag, exc)
                result.parked += 1
                return True
            self._queue.mark_retry(batch.batch_id, str(exc), uncertain=isinstance(exc, DeliveryUncertain))
            logger.warning(
                "MindGraph transcript ingest failed (batch %s, %d parts kept on disk, attempt %d): %s",
                batch.tag, batch.part_count, batch.attempts + 1, exc,
            )
            result.blocked = str(exc)
            return False
        self._queue.mark_delivered(batch.batch_id, receipt)
        result.delivered += 1
        return True
