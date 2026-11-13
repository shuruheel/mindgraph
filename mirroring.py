"""Ordered, durable replay of successful Hermes built-in memory changes.

Operations use the profile's capture database but do not depend on automatic
transcript capture being enabled. A replacement saves the new entry before
forgetting the old one; failed operations hold later operations behind them.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any, Callable

from mindgraph import MindGraphError

from .capture import LEASE_S, CaptureError, CaptureQueue, retry_delay

logger = logging.getLogger(__name__)
MAX_OUTBOX_CHARS = 2_000_000


class MemoryOutbox:
    def __init__(self, queue: CaptureQueue, send: Callable[[str, dict[str, Any]], None]) -> None:
        self.queue, self.send = queue, send
        self._lock = threading.Lock()
        self._thread = None
        self._again = False
        self._force = False
        self._owner = uuid.uuid4().hex
        self._enqueue_failures = 0
        self._enqueue_error = None
        queue._tx(lambda: queue._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, payload TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                last_error TEXT, owner TEXT, lease_until REAL NOT NULL DEFAULT 0
            )
        """))

    def enqueue(self, operations: list[tuple[str, dict[str, Any]]]) -> None:
        if not operations:
            return
        def work() -> None:
            pending = self.queue._db.execute(
                "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM memory_outbox"
            ).fetchone()[0]
            rows = [(action, json.dumps(payload, ensure_ascii=False)) for action, payload in operations]
            if pending + sum(len(payload) for _, payload in rows) > MAX_OUTBOX_CHARS:
                raise CaptureError("memory mirror outbox capacity exceeded; change was not queued")
            self.queue._db.executemany("INSERT INTO memory_outbox(action, payload) VALUES (?, ?)", rows)
        try:
            self.queue._tx(work)
        except Exception as exc:
            with self._lock:
                # This count is also usable when the database cannot accept
                # bookkeeping about a failed write.
                self._enqueue_failures += 1
                self._enqueue_error = str(exc)[:500]
                try:
                    def record():
                        self.queue._bump("mirror_enqueue_failures", 1)
                        self.queue._db.execute(
                            "INSERT OR REPLACE INTO meta VALUES ('mirror_enqueue_error', ?)", (self._enqueue_error,)
                        )
                    self.queue._tx(record)
                    self._enqueue_failures -= 1  # now represented durably
                except Exception:
                    pass
            raise

    def _claim(self, force: bool):
        def work():
            row = self.queue._db.execute(
                "SELECT id, action, payload, attempts, next_attempt, lease_until FROM memory_outbox ORDER BY id LIMIT 1"
            ).fetchone()
            now = self.queue._clock()
            if row is None or row[5] > now or (not force and row[4] > now):
                return None
            self.queue._db.execute(
                "UPDATE memory_outbox SET owner = ?, lease_until = ? WHERE id = ?",
                (self._owner, now + LEASE_S, row[0]),
            )
            return row
        return self.queue._tx(work)

    def _drain(self, force: bool) -> None:
        while (row := self._claim(force)) is not None:
            ident, action, payload, attempts = row[:4]
            try:
                self.send(action, json.loads(payload))
            except Exception as exc:
                # Forget is idempotent even when the earlier attempt succeeded
                # but its response was lost, or the entry predates this provider.
                if not (action == "forget" and isinstance(exc, MindGraphError) and exc.status == 404):
                    params = (str(exc)[:500], self.queue._clock() + retry_delay(attempts + 1), ident, self._owner)
                    self.queue._tx(lambda params=params: self.queue._db.execute(
                        "UPDATE memory_outbox SET attempts = attempts + 1, last_error = ?, next_attempt = ?, "
                        "owner = NULL, lease_until = 0 WHERE id = ? AND owner = ?",
                        params,
                    ))
                    logger.warning("MindGraph memory mirror delayed; retained for retry: %s", exc)
                    return
            self.queue._tx(lambda ident=ident: self.queue._db.execute(
                "DELETE FROM memory_outbox WHERE id = ? AND owner = ?", (ident, self._owner)
            ))

    def kick(self, spawn: Callable, *, force: bool = False, wait_s: float = 0.0) -> None:
        """At most one context-bound worker per instance; SQLite leases cover peers."""
        with self._lock:
            self._again = True
            self._force = self._force or force
            if self._thread is None:
                self._thread = spawn(self._run, name="mindgraph-memory-mirror")
                self._thread.start()
            thread = self._thread
        if wait_s:
            thread.join(wait_s)

    def _run(self) -> None:
        while True:
            with self._lock:
                force, self._force, self._again = self._force, False, False
            try:
                self._drain(force)
            except Exception as exc:
                logger.warning("MindGraph memory mirror worker stopped; queued changes retained: %s", exc)
            with self._lock:
                if not self._again:
                    self._thread = None
                    return

    def status(self) -> dict[str, Any]:
        with self._lock:
            rejected, enqueue_error = self._enqueue_failures, self._enqueue_error
        try:
            count = self.queue._read("SELECT COUNT(*) FROM memory_outbox")[0][0]
            failures = self.queue._read(
                "SELECT attempts, last_error FROM memory_outbox WHERE last_error IS NOT NULL ORDER BY id LIMIT 1"
            )
            saved = dict(self.queue._read("SELECT key, value FROM meta WHERE key LIKE 'mirror_enqueue_%'"))
            return {"durable": self.queue.durable, "pending_operations": count,
                    "enqueue_failures": rejected + int(saved.get("mirror_enqueue_failures", 0)),
                    **({"enqueue_error": saved.get("mirror_enqueue_error") or enqueue_error}
                       if saved.get("mirror_enqueue_error") or enqueue_error else {}),
                    **({"attempts": failures[0][0], "last_error": failures[0][1]} if failures else {})}
        except CaptureError as exc:
            return {"durable": self.queue.durable, "pending_operations": None, "enqueue_failures": rejected,
                    "enqueue_error": enqueue_error, "last_error": str(exc)}
