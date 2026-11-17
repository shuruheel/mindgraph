"""Durable transcript capture: a profile-scoped SQLite queue between Hermes's
turn hooks and ``/ingest/session``.

Why a queue on disk. A turn that only lives in process memory is lost by a
crash, a kill, or a server outage that outlasts the process. Here every turn is
committed to ``$HERMES_HOME/mindgraph/capture.db`` before ``sync_turn`` returns,
sealed into batches at the flush points, and delivered at least once: a batch
leaves the queue only when the server accepted it, and a new process picks up
whatever an earlier one left behind.

Why batches carry a tag. ``/ingest/session`` as deployed does not act on an idempotency
key: every call creates a Document. A request may land without the client learning of it (a
timeout, a dropped connection, a process killed after the send), so a batch is
marked as possibly sent *before* its request goes out, its tag (a digest of its
content) is written into the transcript title, and the next attempt looks for
that tag on the server before it sends again. The provider also sends an
idempotency key when the SDK takes one; the tag stays for servers that do not
act on it.

Why two ledgers. The pre-compress checkpoint hands over transcript rows that
``sync_turn`` has mostly captured already, and may run ahead of the turn it
interrupts. ``seen`` stops the checkpoint re-archiving what a turn delivered;
``prepaid`` stops the turn re-sending what the checkpoint archived first.

This module does not import Hermes.
"""

from __future__ import annotations

import hashlib
import json
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

SCHEMA_VERSION = 2
# Reject new evidence atomically at capacity. Accepted checkpoints must never
# be evicted while they are the only durable copy of a compressed transcript.
MAX_PENDING_CHARS = 20_000_000
# One /ingest/session body. Larger batches are split at part boundaries.
MAX_BATCH_CHARS = 200_000
RETRY_BASE_S = 5.0
RETRY_MAX_S = 900.0
# A delivery holds its batch this long. A crashed process's lease expires and
# another process (or the next start) takes the batch over. Well above the
# longest one delivery can take (a lookup, a session open and the ingest, each
# under the client's timeout).
LEASE_S = 120.0
# A batch the server keeps failing on is parked after this many attempts so it
# cannot hold every later batch behind it. Its text stays in the queue.
MAX_ATTEMPTS = 10
# Receipts and the seen ledger older than this are pruned; undelivered text never is.
RETENTION_S = 30 * 86_400.0
# A checkpoint's claim on a turn it ran ahead of matters only until that turn
# completes; an interrupted turn never completes, and its claim must not
# swallow the same words said again later.
PREPAID_TTL_S = 3_600.0
PRUNE_EVERY_S = 86_400.0
_OPEN_ATTEMPTS = 3
_WS = re.compile(r"\s+")

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    context TEXT NOT NULL,
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
    seq INTEGER NOT NULL,
    session TEXT NOT NULL,
    context TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS batches_state ON batches (state, seq);
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
CREATE TABLE IF NOT EXISTS rewinds (session TEXT PRIMARY KEY, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS session_epochs (session TEXT PRIMARY KEY, generation INTEGER NOT NULL);
"""


class CaptureError(RuntimeError):
    """The queue could not commit. A checkpoint that sees this must not report success."""


class CaptureFull(CaptureError):
    """New evidence cannot fit without losing an already accepted checkpoint."""


class DeliveryRejected(Exception):
    """The server refused the batch and will refuse it again unchanged (a 4xx
    other than auth, rate limit or timeout). The batch is parked, not retried."""


class DeliveryNotSent(Exception):
    """The request certainly did not land (the connection was refused, the
    server answered with a status that precedes any write). Safe to send again
    without looking."""


class DeliveryUncertain(Exception):
    """The request may have landed (a timeout, a dropped connection, a 5xx, an
    unreadable answer). The next attempt reconciles before it resends. Any
    failure delivery cannot classify is treated the same way."""


@dataclass(frozen=True)
class Batch:
    batch_id: str
    session: str
    context: str
    origin: str
    content: str
    part_count: int
    attempts: int
    # An earlier attempt may have reached the server.
    uncertain: bool
    # First retained part's capture time, never the later retry/delivery time.
    # Checkpoint recovery can observe older turns for the first time here.
    captured_at: Optional[str] = None
    # Unknown for recovered checkpoint text, including mixed batches.
    occurred_at: Optional[str] = None
    actor_scope: Optional[str] = None
    turn_framing: Optional[dict[str, Any]] = None

    @property
    def tag(self) -> str:
        return self.batch_id[:12]


@dataclass(frozen=True)
class Receipt:
    job_id: Optional[str] = None
    document_uid: Optional[str] = None


def part_digest(role: str, text: str) -> str:
    """Identity of one transcript row within a conversation. Whitespace is
    collapsed so the same message handed over by two hooks hashes alike. The
    conversation id is not part of it: Hermes renames a conversation when it
    compresses, and the row is still the same row."""
    normalized = _WS.sub(" ", text).strip()
    return hashlib.sha256(f"{role}\x1f{normalized}".encode()).hexdigest()


def render_parts(parts: Iterable[tuple]) -> str:
    return render_framed_parts(parts)[0]


def render_framed_parts(parts: Iterable[tuple]) -> tuple[str, dict[str, Any]]:
    """Frame actual captured roles with UTF-8 offsets; text cannot forge a turn."""
    labels = {"user": "User", "user_attribution": "User attribution", "assistant": "Assistant", "delegation_task": "Delegated task",
              "delegation_result": "Delegated result"}
    rendered, spans = [], []
    offset = 0
    for row in parts:
        role, text = row[:2]
        author = json.loads(row[2]) if len(row) > 2 and row[2] else None
        label = labels.get(role, role)
        if author:
            label += " " + json.dumps(author, ensure_ascii=False, sort_keys=True)
        segment = f"{label}: {text}"
        length = len(segment.encode("utf-8"))
        spans.append({"role": role, "plain_user": role == "user" and not author,
                      "start": offset, "end": offset + length})
        rendered.append(segment)
        offset += length + 2
    content = "\n\n".join(rendered)
    framing = {"schema": "utf8-turn-spans/v1", "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
               "spans": spans}
    if len(json.dumps(framing).encode("utf-8")) > 60_000:
        framing = {"schema": "utf8-turn-spans/unavailable", "sha256": framing["sha256"],
                   "reason": "turn_span_budget_exceeded"}
    return content, framing


def retry_delay(attempts: int) -> float:
    return min(RETRY_BASE_S * (2 ** max(attempts - 1, 0)), RETRY_MAX_S)


class CaptureQueue:
    """One profile's capture queue. Safe across threads (one lock, one
    connection) and across processes sharing the profile (WAL, leases)."""

    def __init__(self, path: Optional[Path], *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._owner = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._pruned_at = 0.0
        self.path = path
        self.durable = path is not None
        target = str(path) if path is not None else ":memory:"
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: transactions are explicit, so a multi-statement
        # seal either commits whole or not at all.
        self._db = sqlite3.connect(target, timeout=10.0, isolation_level=None, check_same_thread=False)
        self._db.execute("PRAGMA busy_timeout = 10000")
        # Delivered transcript text is overwritten, not left in free pages.
        self._db.execute("PRAGMA secure_delete = ON")
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
        self._tx(self._migrate)

    def _migrate(self) -> None:
        # A profile namespace, not a claim that every transport speaker is one
        # person. Servers must still require an explicit single-user policy or
        # authenticated speaker bindings before using it for revisions.
        self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('actor_scope', ?)", (str(uuid.uuid4()),)
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(parts)")}
        if "author" not in columns:
            self._db.execute("ALTER TABLE parts ADD COLUMN author TEXT")
            # v1 copied ledgers without evidence ownership. After an undo or
            # eviction, an orphaned alias is indistinguishable from delivered
            # evidence (the old undo/drop receipt may already be pruned).
            # Only retained text is verifiable: replay other rows once rather
            # than certify missing evidence. Prepaid records have no verifiable
            # occurrence identity either, so don't suppress a completed turn.
            self._db.execute("DELETE FROM seen")
            self._db.execute("DELETE FROM prepaid")
            self._db.execute(
                "INSERT INTO seen(session, digest, at) "
                "SELECT session, digest, MAX(created_at) FROM parts GROUP BY session, digest"
            )
        self._db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
        )

    @classmethod
    def open(cls, hermes_home: Optional[str], *, clock: Callable[[], float] = time.time) -> "CaptureQueue":
        """The profile's queue, or an in-memory one when the profile directory
        cannot hold it. The fallback keeps capture working for the life of the
        process and reports itself as not durable."""
        if hermes_home:
            path = Path(hermes_home) / "mindgraph" / "capture.db"
            failure: Optional[BaseException] = None
            for attempt in range(_OPEN_ATTEMPTS):
                try:
                    return cls(path, clock=clock)
                except sqlite3.OperationalError as exc:
                    failure = exc
                    if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                        break
                    # Another process holds the file for a moment; a lock must
                    # not cost this process its durability for good.
                    time.sleep(0.2 * (attempt + 1))
                except (OSError, sqlite3.Error) as exc:
                    failure = exc
                    break
            logger.warning(
                "MindGraph capture queue unavailable at %s (%s); turns are held in memory only", path, failure
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
                result = work()
                self._db.execute("COMMIT")
                return result
            except sqlite3.Error as exc:
                self._rollback()
                raise CaptureError(f"capture queue write failed: {exc}") from exc
            except BaseException as exc:
                self._rollback()
                if isinstance(exc, CaptureFull):
                    self._bump("capacity_rejections", 1)
                raise

    def _rollback(self) -> None:
        """Leave no transaction open: a failed COMMIT would otherwise make
        every later write fail with "transaction within a transaction"."""
        try:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _read(self, query: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            try:
                return self._db.execute(query, args).fetchall()
            except sqlite3.Error as exc:
                raise CaptureError(f"capture queue read failed: {exc}") from exc

    def _bump(self, key: str, amount: int) -> None:
        self._db.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + CAST(excluded.value AS INTEGER)",
            (key, str(amount)),
        )

    def epoch(self, session: str) -> int:
        rows = self._read("SELECT generation FROM session_epochs WHERE session = ?", (session,))
        return int(rows[0][0]) if rows else 0

    def add_turn(self, session: str, user: str, assistant: str, *, context: str = "primary",
                 generation: Optional[int] = None, author: Optional[dict[str, Any]] = None) -> int:
        """Commit one completed turn; returns undelivered characters still open
        (unsealed) for the flush threshold."""
        now = self._clock()

        def work() -> int:
            if generation is not None and generation != self.epoch(session):
                self._bump("undo_discarded_parts", sum(1 for text in (user, assistant) if text))
                return self._open_chars()
            for role, text in (("user", user), ("assistant", assistant)):
                if not text:
                    continue
                digest = part_digest(role, text)
                spent = self._db.execute(
                    "DELETE FROM prepaid WHERE session = ? AND digest = ? AND at >= ?",
                    (session, digest, now - PREPAID_TTL_S),
                ).rowcount
                if spent:
                    if role == "user" and author:
                        enriched = self._db.execute(
                            "UPDATE parts SET author = ? WHERE session = ? AND digest = ? "
                            "AND origin = 'checkpoint' AND batch_id IS NULL",
                            (json.dumps(author), session, digest),
                        ).rowcount
                        if not enriched:
                            # Sealed batches are immutable (their hash is the
                            # retry identity). Preserve newly supplied provenance
                            # separately even if that checkpoint is already sent.
                            attribution = f"Checkpointed message sha256:{digest}: {text}"
                            self._insert_part(session, context, "user_attribution", attribution,
                                              part_digest("user_attribution", attribution), "turn", now, author=author)
                    continue  # the checkpoint archived this row before its turn completed
                self._insert_part(session, context, role, text, digest, "turn", now,
                                  author=author if role == "user" else None)
                self._db.execute(
                    "INSERT OR IGNORE INTO seen (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                )
            self._check_capacity()
            return self._open_chars()

        return self._tx(work)

    def add_evidence(self, session: str, rows: Iterable[tuple[str, str]], *, context: str = "primary") -> int:
        """Commit the checkpoint's transcript rows that no hook has captured yet;
        returns how many were new. Idempotent: the same transcript again adds nothing."""
        now = self._clock()

        def work() -> int:
            added = 0
            for role, text in rows:
                if role not in ("user", "assistant") or not text:
                    continue
                digest = part_digest(role, text)
                fresh = self._db.execute(
                    "INSERT OR IGNORE INTO seen (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                ).rowcount
                if not fresh:
                    continue
                self._insert_part(session, context, role, text, digest, "checkpoint", now)
                self._db.execute(
                    "INSERT OR REPLACE INTO prepaid (session, digest, at) VALUES (?, ?, ?)", (session, digest, now)
                )
                added += 1
            if added:
                self._check_capacity()
            return added

        return self._tx(work)

    def _insert_part(
        self, session: str, context: str, role: str, text: str, digest: str, origin: str, now: float,
        *, author: Optional[dict[str, Any]] = None,
    ) -> None:
        self._db.execute(
            "INSERT INTO parts (session, context, role, text, digest, origin, created_at, author) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session, context, role, text, digest, origin, now, json.dumps(author) if author else None),
        )

    def add_delegation(self, session: str, task: str, result: str, *, child_session_id: str = "",
                       generation: Optional[int] = None) -> None:
        def work() -> None:
            if generation is not None and generation != self.epoch(session):
                return
            for role, text in (("delegation_task", task), ("delegation_result", result)):
                if not text:
                    continue
                text = f"[child_session_id={json.dumps(child_session_id)}] {text}" if child_session_id else text
                digest = part_digest(role, text)
                fresh = self._db.execute(
                    "INSERT OR IGNORE INTO seen VALUES (?, ?, ?)", (session, digest, self._clock())
                ).rowcount
                if fresh:
                    self._insert_part(session, "primary", role, text, digest, "delegation", self._clock())
            self._check_capacity()
        self._tx(work)

    def _check_capacity(self) -> None:
        total = self._db.execute(
            "SELECT COALESCE(SUM(LENGTH(text) + COALESCE(LENGTH(author), 0)), 0) FROM parts"
        ).fetchone()[0]
        if total > MAX_PENDING_CHARS:
            raise CaptureFull(f"capture queue capacity exceeded ({total} > {MAX_PENDING_CHARS} characters)")

    def _open_chars(self) -> int:
        row = self._db.execute("SELECT COALESCE(SUM(LENGTH(text)), 0) FROM parts WHERE batch_id IS NULL").fetchone()
        return int(row[0])

    def carry_ledger(self, old: str, new: str) -> None:
        """A conversation continues under a new id (compression, a branch):
        only server-accepted evidence is shared. Pending evidence can still be
        removed by undo in its original session; a successor must keep its own
        checkpoint copy until delivery establishes an independent archive."""
        if not old or not new or old == new:
            return

        def work() -> None:
            self._db.execute(
                "INSERT INTO session_epochs VALUES (?, ?) ON CONFLICT(session) "
                "DO UPDATE SET generation = MAX(generation, excluded.generation)", (new, self.epoch(old))
            )
            for table in ("seen", "prepaid"):
                self._db.execute(
                    f"INSERT OR IGNORE INTO {table} (session, digest, at) "
                    f"SELECT ?, digest, at FROM {table} ledger WHERE session = ? "
                    "AND NOT EXISTS (SELECT 1 FROM parts p WHERE p.digest = ledger.digest)",
                    (new, old),
                )

        self._tx(work)

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
                f"SELECT id, session, role, text, origin, context FROM parts WHERE {where} ORDER BY id", args
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
            return sealed

        result = self._tx(work)
        if now - self._pruned_at > PRUNE_EVERY_S:
            self.prune()
        return result

    def _seal_chunk(self, session: str, rows: list[tuple], now: float) -> str:
        digest = hashlib.sha256()
        digest.update(session.encode())
        for row in rows:
            digest.update(f"\x1e{row[0]}\x1f{row[2]}\x1f{row[3]}".encode())
        batch_id = digest.hexdigest()
        origin = "checkpoint" if all(row[4] == "checkpoint" for row in rows) else "turn"
        # seq is the first part's id: batches leave in the order their turns
        # arrived, whatever the clock said and however their ids hash.
        self._db.execute(
            "INSERT INTO batches (batch_id, seq, session, context, origin, chars, part_count, state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'sealed', ?)",
            (batch_id, rows[0][0], session, rows[0][5], origin, sum(len(row[3]) for row in rows), len(rows), now),
        )
        self._db.executemany("UPDATE parts SET batch_id = ? WHERE id = ?", [(batch_id, row[0]) for row in rows])
        return batch_id

    def discard_session(self, session: str) -> int:
        """/undo: nothing unsent from this conversation becomes durable. Hermes
        does not say how far the undo went, so every unsent row goes, and the
        count is reported. Their ledger entries go too, so text said again
        after the undo is captured again."""
        now = self._clock()

        def work() -> int:
            self._db.execute(
                "INSERT INTO session_epochs VALUES (?, 1) ON CONFLICT(session) "
                "DO UPDATE SET generation = generation + 1", (session,)
            )
            self._db.execute("INSERT OR REPLACE INTO rewinds (session, at) VALUES (?, ?)", (session, now))
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
            self._bump("undo_discarded_parts", len(rows))
            return len(rows)

        return self._tx(work)

    # ── Delivery ───────────────────────────────────────────────────────────

    def due(self, *, force: bool = False) -> bool:
        """Whether a claim would hand out a batch now. Cheap, for callers that
        would otherwise start a thread to find nothing."""
        now = self._clock()
        rows = self._read(
            "SELECT next_attempt_at, lease_owner, lease_until FROM batches WHERE state = 'sealed' ORDER BY seq LIMIT 1"
        )
        if not rows:
            return False
        next_attempt_at, owner, lease_until = rows[0]
        if lease_until > now and owner != self._owner:
            return False
        return force or next_attempt_at <= now

    def claim(self, *, force: bool = False) -> Optional[Batch]:
        """Lease the oldest sealed batch, or nothing while it is backing off or
        another live process holds it: batches reach the server in turn order,
        so a newer one never overtakes it. ``force`` ignores the backoff (a
        flush point is a reason to try now), never a live lease.

        The batch is marked as possibly sent here, before any request: if the
        process dies between the send and the bookkeeping, the next attempt
        knows to look first. The returned ``uncertain`` is the mark as it stood
        before this claim."""
        now = self._clock()

        def work() -> Optional[Batch]:
            while True:
                row = self._db.execute(
                    "SELECT batch_id, session, context, origin, part_count, attempts, uncertain, next_attempt_at, "
                    "lease_owner, lease_until FROM batches WHERE state = 'sealed' ORDER BY seq LIMIT 1"
                ).fetchone()
                if row is None:
                    return None
                if row[9] > now and row[8] != self._owner:
                    return None
                if not force and row[7] > now:
                    return None
                parts = self._db.execute(
                    "SELECT role, text, author, created_at, origin FROM parts WHERE batch_id = ? ORDER BY id", (row[0],)
                ).fetchall()
                if not parts:
                    # Its text is gone (another process delivered it): nothing to send.
                    self._db.execute(
                        "UPDATE batches SET state = 'dropped', last_error = 'no text left to send', delivered_at = ? "
                        "WHERE batch_id = ?",
                        (now, row[0]),
                    )
                    continue
                self._db.execute(
                    "UPDATE batches SET lease_owner = ?, lease_until = ?, uncertain = 1 WHERE batch_id = ?",
                    (self._owner, now + LEASE_S, row[0]),
                )
                content, framing = render_framed_parts(parts)
                return Batch(
                    row[0], row[1], row[2], row[3], content, row[4], row[5], bool(row[6]),
                    _iso(parts[0][3]),
                    _iso(parts[0][3]) if all(part[4] == "turn" for part in parts) else None,
                    self._db.execute("SELECT value FROM meta WHERE key = 'actor_scope'").fetchone()[0],
                    framing,
                )

        return self._tx(work)

    def mark_delivered(self, batch_id: str, receipt: Receipt) -> None:
        now = self._clock()

        def work() -> None:
            # Whoever holds the lease now: the server has it, and that is final.
            done = self._db.execute(
                "UPDATE batches SET state = 'delivered', delivered_at = ?, job_id = ?, document_uid = ?, "
                "last_error = NULL, uncertain = 0, lease_owner = NULL, lease_until = 0 "
                "WHERE batch_id = ? AND state = 'sealed'",
                (now, receipt.job_id, receipt.document_uid, batch_id),
            ).rowcount
            if done:
                # The server holds the text now; the queue keeps only the receipt.
                self._db.execute("DELETE FROM parts WHERE batch_id = ?", (batch_id,))

        self._tx(work)

    def mark_retry(self, batch_id: str, error: str, *, uncertain: bool) -> None:
        """Delivery failed in a way a later attempt may fix. ``uncertain`` says
        whether the request may have reached the server; when it certainly did
        not, the mark set at claim is cleared and the retry sends without a
        lookup. Only the lease holder may record this: a slow sender whose
        lease was taken over must not undo the new holder's work."""
        now = self._clock()

        def work() -> None:
            row = self._db.execute(
                "SELECT attempts FROM batches WHERE batch_id = ? AND state = 'sealed' AND lease_owner = ?",
                (batch_id, self._owner),
            ).fetchone()
            if row is None:
                return
            count = int(row[0]) + 1
            self._db.execute(
                "UPDATE batches SET attempts = ?, next_attempt_at = ?, last_error = ?, uncertain = ?, "
                "lease_owner = NULL, lease_until = 0 WHERE batch_id = ?",
                (count, now + retry_delay(count), error[:500], int(uncertain), batch_id),
            )

        self._tx(work)

    def mark_failed(self, batch_id: str, error: str, *, uncertain: bool = False) -> None:
        """Park the batch with its text: the server will not take it as it is,
        or has failed on it too many times. ``retry_failed`` returns it to the
        queue, still knowing whether an attempt may have landed."""

        def work() -> None:
            self._db.execute(
                "UPDATE batches SET state = 'failed', attempts = attempts + 1, last_error = ?, uncertain = ?, "
                "lease_owner = NULL, lease_until = 0 WHERE batch_id = ? AND state = 'sealed' AND lease_owner = ?",
                (error[:500], int(uncertain), batch_id, self._owner),
            )

        self._tx(work)

    def retry_failed(self) -> int:
        def work() -> int:
            return self._db.execute(
                "UPDATE batches SET state = 'sealed', next_attempt_at = 0, attempts = 0 WHERE state = 'failed'"
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
        rows = self._read(
            "SELECT batch_id, job_id FROM batches WHERE state = 'delivered' AND job_id IS NOT NULL "
            "AND (job_status IS NULL OR job_status NOT IN "
            "('completed', 'completed_with_errors', 'failed', 'cancelled', 'unknown')) "
            "ORDER BY delivered_at DESC LIMIT ?",
            (limit,),
        )
        return [(row[0], row[1]) for row in rows]

    def prune(self) -> None:
        """Forget receipts and ledger rows past retention. Never touches undelivered text."""
        now = self._clock()

        def work() -> None:
            self._db.execute(
                "DELETE FROM batches WHERE state IN ('delivered', 'dropped') AND COALESCE(delivered_at, created_at) < ?",
                (now - RETENTION_S,),
            )
            self._db.execute("DELETE FROM seen WHERE at < ?", (now - RETENTION_S,))
            self._db.execute("DELETE FROM prepaid WHERE at < ?", (now - PREPAID_TTL_S,))
            self._db.execute("DELETE FROM rewinds WHERE at < ?", (now - PREPAID_TTL_S,))

        try:
            self._tx(work)
            self._pruned_at = now
        except CaptureError as exc:  # housekeeping never fails a turn
            logger.debug("MindGraph capture queue prune failed: %s", exc)

    # ── Status ─────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """What is waiting, what failed and what was last delivered: the
        observable side of at-least-once."""
        with self._lock:
            open_parts, open_chars = self._read(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(text)), 0) FROM parts WHERE batch_id IS NULL"
            )[0]
            counts = dict(self._read("SELECT state, COUNT(*) FROM batches GROUP BY state"))
            pending_chars = self._read("SELECT COALESCE(SUM(chars), 0) FROM batches WHERE state = 'sealed'")[0][0]
            oldest = self._read("SELECT MIN(created_at) FROM batches WHERE state IN ('sealed', 'failed')")[0][0]
            last = self._read(
                "SELECT delivered_at, job_id, document_uid, job_status FROM batches WHERE state = 'delivered' "
                "ORDER BY delivered_at DESC LIMIT 1"
            )
            error = self._read(
                "SELECT last_error, attempts, next_attempt_at, state FROM batches "
                "WHERE state IN ('sealed', 'failed') AND last_error IS NOT NULL ORDER BY seq LIMIT 1"
            )
            failed_jobs = self._read(
                "SELECT COUNT(*) FROM batches WHERE state = 'delivered' AND job_status = 'failed'"
            )[0][0]
            undone = self._read("SELECT value FROM meta WHERE key = 'undo_discarded_parts'")
            rejected = self._read("SELECT value FROM meta WHERE key = 'capacity_rejections'")
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
            "undo_discarded_parts": int(undone[0][0]) if undone else 0,
            "capacity_rejections": int(rejected[0][0]) if rejected else 0,
        }
        if oldest is not None:
            report["oldest_pending_age_s"] = max(0, int(self._clock() - oldest))
        if last:
            report["last_delivery"] = {
                key: value
                for key, value in (
                    ("at", _iso(last[0][0])), ("job_id", last[0][1]), ("document_uid", last[0][2]),
                    ("job_status", last[0][3]),
                )
                if value is not None
            }
        if error:
            message, attempts, next_attempt_at, state = error[0]
            report["last_error"] = {
                "message": message,
                "attempts": int(attempts),
                "state": "parked" if state == "failed" else "retrying",
                **({"next_attempt_in_s": max(0, int(next_attempt_at - self._clock()))} if state == "sealed" else {}),
            }
        return report


def _iso(stamp: Optional[float]) -> Optional[str]:
    if stamp is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))


# ── Delivery ───────────────────────────────────────────────────────────────


@dataclass
class DrainResult:
    delivered: int = 0
    reconciled: int = 0
    parked: int = 0
    blocked: Optional[str] = None  # why the drain stopped with batches still queued


class Deliverer:
    """Moves sealed batches to the server, oldest first.

    ``send`` delivers one batch and returns its receipt. It raises
    ``DeliveryRejected`` when the server will never take the batch and
    ``DeliveryNotSent`` when the request certainly did not land; anything else
    it raises is an outcome nobody knows. ``find`` looks for a batch the server
    already holds and returns its receipt, ``None`` when it is certainly
    absent, and raises when it cannot tell.
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
                    if batch is None or not self._deliver(batch, result):
                        break
                except CaptureError as exc:
                    # The queue itself failed. The batch keeps the possibly-sent
                    # mark it got at claim, so nothing is resent blind.
                    result.blocked = str(exc)
                    break
        finally:
            self._lock.release()
        return result

    def _give_up(self, batch: Batch) -> bool:
        return batch.attempts + 1 >= MAX_ATTEMPTS

    def _deliver(self, batch: Batch, result: DrainResult) -> bool:
        """True when the queue may move on to the next batch."""
        if batch.uncertain:
            try:
                receipt = self._find(batch)
            except Exception as exc:
                reason = f"could not verify an earlier attempt: {exc}"
                if self._give_up(batch):
                    # Parked still marked: the next start looks again before sending.
                    self._queue.mark_failed(batch.batch_id, reason, uncertain=True)
                    logger.warning("MindGraph transcript batch %s parked: %s", batch.tag, reason)
                    result.parked += 1
                    return True
                self._queue.mark_retry(batch.batch_id, reason, uncertain=True)
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
            uncertain = not isinstance(exc, DeliveryNotSent)
            if self._give_up(batch):
                self._queue.mark_failed(
                    batch.batch_id, f"gave up after {batch.attempts + 1} attempts: {exc}", uncertain=uncertain
                )
                logger.warning("MindGraph transcript batch %s parked after repeated failures: %s", batch.tag, exc)
                result.parked += 1
                return True
            self._queue.mark_retry(batch.batch_id, str(exc), uncertain=uncertain)
            logger.warning(
                "MindGraph transcript ingest failed (batch %s, %d parts kept on disk, attempt %d): %s",
                batch.tag, batch.part_count, batch.attempts + 1, exc,
            )
            result.blocked = str(exc)
            return False
        self._queue.mark_delivered(batch.batch_id, receipt)
        result.delivered += 1
        return True
