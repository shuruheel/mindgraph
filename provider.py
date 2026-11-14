"""MindGraphMemoryProvider: the Hermes ``MemoryProvider`` lifecycle around the
mindgraph-mcp tool surface.

- ``initialize`` binds a ``Runtime`` (client, identity, session) to this instance.
- ``system_prompt_block`` is static: the MCP server's memory instructions.
- ``prefetch`` recalls bounded context for the current message (``recall.py``:
  content-term query, relevance floor, a deadline, no repeats), plus the
  open-work brief on a conversation's first turn. ``queue_prefetch`` redoes a
  recall that failed, off the turn path.
- ``sync_turn`` commits completed turns to the profile's capture queue
  (``capture.py``); the queue is sealed into batches and delivered as session
  transcripts before compression, at session end or switch, and whenever it
  grows past ``FLUSH_CHARS``. A batch leaves the queue only when the server
  took it, so a crash or an outage delays capture instead of losing it.
- ``on_pre_compress`` is a checkpoint (API v2): with ``require_checkpoint`` the
  transcript rows about to be compressed are committed first, and a failed
  commit raises so Hermes keeps the uncompressed transcript.
- ``on_memory_write`` durably queues ordered built-in memory changes for replay.
- ``on_delegation`` captures parent-side tasks/results with child session identity.
- Tool calls route through ``dispatch.handle_tool`` behind the governance gate.

Ordinary automatic writes run only for the ``primary`` agent context; required
checkpoints also run in forks. Isolated RPC hosts disable turn/delegation capture.
"""

from __future__ import annotations

import contextvars
import hashlib
import inspect
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Iterable, Optional

import httpx
from agent.memory_provider import MemoryProvider
from agent.secret_scope import get_secret
from mindgraph import MindGraphError

from . import __version__
from .capture import (
    Batch,
    CaptureError,
    CaptureQueue,
    Deliverer,
    DeliveryNotSent,
    DeliveryRejected,
    DeliveryUncertain,
    Receipt,
)
from .dispatch import contract, handle_tool, static_tool_schemas
from .governance import GovernanceGate
from .memory_tool import MemoryRuntimeConfig
from .mirroring import MemoryOutbox
from .recall import RecallEngine, RecallQuery, load_config
from .render import render_resume_context
from .runtime import DEFAULT_AGENT_ID, DEFAULT_BASE_URL, HARNESS, Runtime

try:  # RecallStatus drives the "🧠 MindGraph — recalled N memories" line on newer Hermes.
    from agent.memory_provider import RecallStatus
except ImportError:  # pragma: no cover - older Hermes
    RecallStatus = None  # type: ignore[assignment,misc]

try:  # Background work must carry the profile's contextvars (HERMES_HOME, secret scope).
    from agent.memory_provider import spawn_context_thread
except ImportError:  # pragma: no cover - older Hermes

    def spawn_context_thread(target, *, name, daemon=True, args=(), kwargs=None):  # type: ignore[misc]
        context = contextvars.copy_context()
        return threading.Thread(target=lambda: context.run(target, *args, **(kwargs or {})), name=name, daemon=daemon)

logger = logging.getLogger(__name__)

FLUSH_CHARS = 24_000
# Hermes's pre-compress checkpoint contract this provider implements when its
# queue is on disk. 1 is the best-effort legacy contract.
CHECKPOINT_API_VERSION = 2
# How long a boundary hook waits for delivery before it returns. Delivery runs
# on its own thread and carries on past the wait; whatever is still queued is
# on disk and goes out at the next flush or the next start. sync_turn never
# waits: it runs on Hermes's one background worker, behind which later turns
# queue to be committed.
FLUSH_WAIT_S = 10.0
CHECKPOINT_WAIT_S = 5.0
SHUTDOWN_WAIT_S = 5.0
# Marker Hermes leaves on a previous compaction's summary row; a summary is
# derived text, never evidence.
_COMPRESSED_SUMMARY_KEY = "_compressed_summary"
_HERMES_NOTES = """
## In Hermes

- Relevant MindGraph context is recalled automatically for each message and appears in the turn as "MindGraph context". Call `mindgraph_memory` only when that recall is insufficient.
- Completed turns are ingested into MindGraph as a session transcript, so do not re-store what was simply said; use the typed write tools for decisions, corrections, lessons and facts that need structure or confidence.
- Writes from Hermes's built-in memory tool are mirrored into MindGraph automatically."""


def builtin_memory_custom_id(target: str, content: str) -> str:
    digest = hashlib.sha256(content.strip().encode()).hexdigest()[:32]
    return f"hermes:{target}:{digest}"


def _message_text(content: Any) -> str:
    """Text of one transcript row. Only text parts count; images, tool calls
    and tool output are never captured."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [
        part["text"]
        for part in content
        if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text")
        and isinstance(part.get("text"), str)
    ]
    return "\n".join(parts).strip()


def evidence_rows(messages: Iterable[Any]) -> list[tuple[str, str]]:
    """Direct user and assistant text from a transcript, in order.

    Hermes hands checkpoint providers this shape already; the same rules are
    applied here because an older Hermes passes the raw list (tool rows, system
    messages, earlier compaction summaries) whatever the provider advertises."""
    rows: list[tuple[str, str]] = []
    for message in messages or []:
        if not isinstance(message, dict) or message.get(_COMPRESSED_SUMMARY_KEY):
            continue
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _message_text(message.get("content"))
        if text:
            rows.append((role, text))
    return rows


def batch_title(batch: Batch) -> str:
    """The transcript title. The tag makes a batch findable on the server,
    which is how an attempt of unknown outcome is reconciled. The kind is the
    agent context that queued the batch, not the one delivering it."""
    kind = "session" if batch.context == "primary" else f"{batch.context} session"
    return f"Hermes {kind} {batch.session} · {batch.tag}"


def _takes_idempotency_key(method: Any) -> bool:
    """Whether this SDK's ``ingest_session`` has the ``idempotency_key`` argument
    (newer than 0.17.0). A catch-all ``**kwargs`` does not count."""
    try:
        return "idempotency_key" in inspect.signature(method).parameters
    except (TypeError, ValueError):
        return False


def _labels(value: Any) -> Iterable[tuple[str, Optional[str]]]:
    """``(label, uid)`` of every node in a search response, whatever its nesting."""
    if isinstance(value, list):
        for item in value:
            yield from _labels(item)
    elif isinstance(value, dict):
        label, uid = value.get("label"), value.get("uid")
        if isinstance(label, str):
            yield label, uid if isinstance(uid, str) else None
        for key in ("node", "results", "nodes", "items"):
            if key in value:
                yield from _labels(value[key])


class MindGraphMemoryProvider(MemoryProvider):
    """MindGraph semantic graph memory for Hermes Agent."""

    def __init__(self) -> None:
        self._rt: Optional[Runtime] = None
        self._gate: Optional[GovernanceGate] = None
        self._memory_config: Optional[MemoryRuntimeConfig] = None
        self._model: str = ""
        self._auto_capture = True
        self._isolated_host = False
        self._recall: Optional[RecallEngine] = None
        self._briefed_sessions: set[str] = set()
        # Conversation id -> the open-work lookup in flight or just finished.
        self._briefs: dict[str, dict[str, Any]] = {}
        self._previous_message = ""
        self._recall_count: Optional[int] = None
        self._recall_generation = 0
        # sync_turn (manager worker) and session switch/end/shutdown (caller
        # thread) both touch the pending buffer and the session bindings.
        self._lock = threading.Lock()
        self._capture: Optional[CaptureQueue] = None
        self._store: Optional[CaptureQueue] = None
        self._outbox: Optional[MemoryOutbox] = None
        # Hermes copies the caller's context into its serialized sync worker.
        # A queued pre-undo call keeps its old generation even after a new turn starts.
        self._turn_context = contextvars.ContextVar(f"mindgraph-turn-{id(self)}", default=None)
        self._deliverer: Optional[Deliverer] = None
        # Hermes conversation id -> open MindGraph Session uid.
        self._mg_sessions: dict[str, str] = {}

    # ── Identity and setup ─────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "mindgraph"

    def is_available(self) -> bool:
        # Key presence only (no network, no import probe): Hermes installs the SDK
        # from pyproject.toml before activation.
        return bool(get_secret("MINDGRAPH_API_KEY", ""))

    def unavailable_reason(self) -> str:
        return "MINDGRAPH_API_KEY is not set; run `hermes memory setup` and choose mindgraph."

    def get_config_schema(self) -> list[dict[str, Any]]:
        # Every field carries env_var, so Hermes stores them in .env and save_config stays a no-op.
        return [
            {
                "key": "api_key",
                "description": "MindGraph API key",
                "secret": True,
                "required": True,
                "env_var": "MINDGRAPH_API_KEY",
                "url": "https://mindgraph.cloud",
            },
            {
                "key": "base_url",
                "description": "API endpoint (override for self-hosted deployments)",
                "default": DEFAULT_BASE_URL,
                "env_var": "MINDGRAPH_BASE_URL",
            },
            {
                "key": "agent_id",
                "description": "Agent identifier stamped on every write for provenance",
                "default": DEFAULT_AGENT_ID,
                "env_var": "MINDGRAPH_AGENT_ID",
            },
        ]

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        # RPC hooks have separate contexts and no transportable turn identity.
        # Required checkpoints receive an explicit snapshot and remain safe.
        self._isolated_host = os.environ.get("HERMES_PLUGIN_HOST_PROCESS") == "1"
        base_url = (get_secret("MINDGRAPH_BASE_URL", "") or "").strip() or DEFAULT_BASE_URL
        agent_id = (get_secret("MINDGRAPH_AGENT_ID", "") or "").strip() or DEFAULT_AGENT_ID
        api_key = get_secret("MINDGRAPH_API_KEY", "") or ""
        org_id = (get_secret("MINDGRAPH_ORG_ID", "") or "").strip() or None
        self._rt = Runtime(
            api_key=api_key,
            base_url=base_url,
            agent_id=agent_id,
            org_id=org_id,
            session_id=session_id or "",
            platform=str(kwargs.get("platform") or ""),
            agent_context=str(kwargs.get("agent_context") or "primary"),
        )
        self._gate = GovernanceGate(
            base_url=base_url,
            api_key=api_key,
            agent_id=agent_id,
            org_id=org_id,
            disabled=(get_secret("MINDGRAPH_GOVERNANCE", "") or "").strip().lower() == "off",
        )
        self._auto_capture = (get_secret("MINDGRAPH_AUTO_CAPTURE", "") or "").strip().lower() not in (
            "0",
            "false",
            "off",
        )
        self._store = CaptureQueue.open(kwargs.get("hermes_home"))
        self._outbox = MemoryOutbox(self._store, self._send_memory_operation)
        if self._can_write():
            self._outbox.kick(spawn_context_thread, force=True)
        if self._auto_capture:
            # Bound to this profile's directory, like every other binding here.
            self._capture = self._store
            self._turn_context.set((session_id, self._capture.epoch(session_id), {}))
            self._deliverer = Deliverer(self._capture, self._send_batch, self._find_batch)
            self._recover_capture()
        self._recall = RecallEngine(
            self._fetch_recall,
            load_config(get_secret, hermes_home=kwargs.get("hermes_home"), cwd=kwargs.get("cwd")),
            spawn_context_thread,
        )
        self._resume_task_uid = str(kwargs.get("task_uid") or get_secret("MINDGRAPH_RESUME_TASK_UID", "") or "")
        # mindgraph_memory status must describe what this provider actually does.
        self._memory_config = MemoryRuntimeConfig(
            server_version=__version__,
            base_url=base_url,
            org_id=org_id,
            agent_id=agent_id,
            automatic_capture=self._auto_capture and self._rt.write_enabled and not self._isolated_host,
            capture_unavailable_reason=(
                "Automatic turn/delegation capture is disabled in Hermes isolated plugin-host mode: "
                "its RPC hooks do not carry turn identity across undo. Required checkpoints, "
                "built-in memory mirroring, recall and tools remain available."
                if self._isolated_host and self._auto_capture else None
            ),
            automatic_delivery=self._recall.config.enabled,
            capture_status=self._capture_status if self._capture is not None else None,
            mirror_status=self._outbox.status,
        )

    def system_prompt_block(self) -> str:
        if self._rt is None:
            return ""
        return f"# MindGraph memory\n\n{contract()['instructions']}\n{_HERMES_NOTES}"

    def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        if self._rt is not None:
            self._rt.turn_number = max(int(turn_number or 0), 0)
            if self._capture is not None:
                self._turn_context.set((self._rt.session_id, self._capture.epoch(self._rt.session_id),
                                        self._author(kwargs, prefix="author_")))
        if self._outbox is not None and self._can_write():
            self._outbox.kick(spawn_context_thread)
        if kwargs.get("model"):
            self._model = str(kwargs["model"])
        # The person's message before this one, from Hermes's own transcript: a
        # resumed process has it even though it never saw that turn.
        previous = kwargs.get("previous_message")
        self._previous_message = previous if isinstance(previous, str) else ""

    # ── Recall ─────────────────────────────────────────────────────────────

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall for the current message, bounded by the recall deadline.

        Hermes runs this on a thread with its own, longer timeout. A call that
        outlives a later turn's must not overwrite that turn's recall status,
        so each call takes a generation and only the latest one may publish.
        """
        with self._lock:
            self._recall_generation += 1
            generation = self._recall_generation
            self._recall_count = None
        rt, recall = self._rt, self._recall
        if rt is None or recall is None:
            return ""
        session = session_id or rt.session_id
        if not recall.config.enabled:
            return ""  # recall off is no automatic injection at all, the brief included
        deadline = time.monotonic() + recall.config.deadline_s
        self._start_brief(session)  # runs beside the recall, not before it
        recalled = recall.recall(session, query or "", previous=self._previous_message)
        brief = self._collect_brief(session, deadline)
        sections = [text for text in (brief, recalled.text) if text]
        if not sections:
            return ""
        with self._lock:
            if generation == self._recall_generation:
                self._recall_count = recalled.count + (1 if brief else 0)
        return "## MindGraph context (recalled for this message)\n\n" + "\n\n".join(sections)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """After a turn: retry a recall that failed, on its own thread, so the
        next message has one to fall back on."""
        if self._rt is not None and self._recall is not None:
            self._recall.after_turn(session_id or self._rt.session_id)

    def _fetch_recall(self, query: RecallQuery, candidates: int) -> Any:
        config = self._recall.config
        options = {
            "project_uid": config.project_uid,
            # More than will be shown: the floor and repeat suppression discard some.
            "node_limit": candidates,
            "chunk_limit": 0,
            "article_limit": 0,
            "include_graph": True,
            # Automatic recall is on the first-token path. Direct matches avoid
            # a whole-graph expansion; explicit retrieval tools can still expand.
            "graph_expansion_limit": 0,
            "graph_max_depth": 2,
            "rerank": config.rerank,
        }
        return self._rt.client.retrieve_context(
            query.query, **{key: value for key, value in options.items() if value is not None}
        )

    def _start_brief(self, session_id: str) -> None:
        """Look up open work once per conversation. A failed lookup is retried
        on the next message; a late one is used by it."""
        rt = self._rt
        with self._lock:
            entry = self._briefs.get(session_id)
            if session_id in self._briefed_sessions or (entry is not None and not entry.get("failed")):
                return
            entry = self._briefs[session_id] = {"done": threading.Event()}

        def run() -> None:
            try:
                scope = {}
                if self._resume_task_uid:
                    scope["task_uid"] = self._resume_task_uid
                elif self._recall.config.project_uid:
                    scope["scope_uids"] = [self._recall.config.project_uid]
                brief = rt.client.plan(action="resume_work", agent_id=rt.agent_id, limit=1, **scope)
                found = isinstance(brief, dict) and brief.get("task")
                entry["text"] = (render_resume_context(brief) or "") if found else ""
            except Exception as exc:
                logger.debug("MindGraph resume brief failed (non-fatal): %s", exc)
                entry["failed"] = True
            finally:
                entry["done"].set()

        spawn_context_thread(run, name="mindgraph-brief").start()

    def _collect_brief(self, session_id: str, deadline: float) -> str:
        with self._lock:
            entry = self._briefs.get(session_id)
        if entry is None or not entry["done"].wait(max(0.0, deadline - time.monotonic())):
            return ""
        if entry.get("failed"):
            return ""
        with self._lock:
            self._briefed_sessions.add(session_id)
            self._briefs.pop(session_id, None)
        return entry.get("text", "")

    def recall_status(self):
        if RecallStatus is None or self._recall_count is None:
            return None
        return RecallStatus(provider_label="MindGraph", count=self._recall_count)

    # ── Capture ────────────────────────────────────────────────────────────
    #
    # Every turn is committed to the profile's queue before sync_turn returns.
    # Delivery is separate and at least once: a batch leaves the queue only on
    # the server's acceptance, and whatever a flush could not deliver stays on
    # disk for the next flush or the next process. ``_lock`` guards the session
    # bindings and is never held across network I/O.

    @property
    def pre_compress_checkpoint_api_version(self) -> int:  # type: ignore[override]
        """v2 only while a checkpoint can be committed to disk. An in-memory
        fallback queue or capture switched off is the best-effort contract, and
        Hermes then says so if the operator requires checkpoints."""
        capture = self._capture
        return CHECKPOINT_API_VERSION if capture is not None and capture.durable else 1

    def _can_write(self) -> bool:
        return self._rt is not None and self._rt.write_enabled

    def _ensure_session(self, harness_session_id: str) -> Optional[str]:
        """The MindGraph Session for one Hermes conversation; open is an identity
        upsert, so reopening after a lost uid is harmless."""
        rt = self._rt
        with self._lock:
            uid = self._mg_sessions.get(harness_session_id)
        if uid:
            return uid
        opened = rt.client.session(
            action="open",
            label=f"Hermes {harness_session_id}",
            harness=HARNESS,
            harness_session_id=harness_session_id,
            **({"model": self._model} if self._model else {}),
            agent_id=rt.agent_id,
        )
        uid = opened.get("uid") if isinstance(opened, dict) else None
        if not (isinstance(uid, str) and uid):
            return None
        with self._lock:
            self._mg_sessions[harness_session_id] = uid
        return uid

    @staticmethod
    def _author(values: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
        result = {}
        for key in ("id", "name", "is_bot"):
            value = values.get(prefix + key)
            if isinstance(value, (str, int, bool)) and value is not None:
                result[key] = value
        return result if result.get("id") or result.get("name") else {}

    def _capture_context(self, session: str) -> tuple[int, dict[str, Any]]:
        bound = self._turn_context.get()
        if bound is None or bound[0] != session:
            # Legacy/direct callers and an asynchronous /new boundary can lack
            # a binding. They can only claim the initial generation, never the
            # current one: after any undo this fails closed in the queue.
            return 0, {}
        return bound[1], bound[2]

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "", **kwargs: Any) -> None:
        """One local commit. Delivery is started, never waited for: this runs
        on Hermes's single background worker, and a turn waiting behind a slow
        server would not be committed at all if Hermes exited meanwhile."""
        if not self._can_write() or self._capture is None or self._isolated_host:
            return
        user, assistant = (user_content or "").strip(), (assistant_content or "").strip()
        if not (user or assistant):
            return
        try:
            # Tagged with the turn's own conversation: a switch may already have
            # rebound the runtime by the time this queued call runs.
            session = session_id or self._rt.session_id
            generation, author = self._capture_context(session)
            if isinstance(kwargs.get("turn_author"), dict):
                author = self._author(kwargs["turn_author"])
            open_chars = self._capture.add_turn(session, user, assistant, context=self._rt.agent_context,
                                                generation=generation, author=author)
            if open_chars >= FLUSH_CHARS:
                self._capture.seal()
        except CaptureError as exc:
            logger.warning("MindGraph could not queue a turn for capture: %s", exc)
            self._drain("capture rejected", force=True, wait_s=0.0)
            return
        self._drain("turn", force=open_chars >= FLUSH_CHARS, wait_s=0.0)

    def on_delegation(self, task: str, result: str, *, child_session_id: str = "", **kwargs: Any) -> None:
        if not self._can_write() or self._capture is None or self._isolated_host:
            return
        bound = self._turn_context.get()
        session = bound[0] if bound is not None else self._rt.session_id
        generation, _ = self._capture_context(session)
        self._capture.add_delegation(session, task, result, child_session_id=child_session_id, generation=generation)
        # A delegation may carry the only copy of its result in the parent.
        self._capture.seal(session)
        self._drain("delegation", force=True, wait_s=0.0)

    def _flush(self, reason: str, *, wait_s: float) -> None:
        """Seal what is open, then deliver. The seal is the durable step and
        raises when it cannot commit; delivery never raises."""
        if self._capture is None:
            return
        self._capture.seal()
        self._drain(reason, force=True, wait_s=wait_s)

    def _drain(self, reason: str, *, force: bool, wait_s: float) -> None:
        """Deliver on a thread of the provider's own and wait at most ``wait_s``
        for it. A caller is never held longer than that by a slow server."""
        deliverer, capture = self._deliverer, self._capture
        if deliverer is None or capture is None or self._rt is None:
            return
        try:
            if not capture.due(force=force):
                return
        except CaptureError as exc:
            logger.debug("MindGraph capture queue unreadable (%s): %s", reason, exc)
            return

        def run() -> None:
            try:
                result = deliverer.drain(force=force)
            except Exception as exc:  # a delivery thread must never die loudly
                logger.warning("MindGraph capture delivery failed (%s; kept on disk): %s", reason, exc)
                return
            if result.delivered or result.reconciled or result.parked:
                logger.debug(
                    "MindGraph capture (%s): %d delivered, %d reconciled, %d parked%s",
                    reason, result.delivered, result.reconciled, result.parked,
                    f"; stopped: {result.blocked}" if result.blocked else "",
                )

        thread = spawn_context_thread(run, name="mindgraph-capture")
        thread.start()
        if wait_s > 0:
            thread.join(wait_s)

    def _send_batch(self, batch: Batch) -> Receipt:
        rt = self._rt
        try:
            session_uid = self._ensure_session(batch.session)
        except Exception as exc:
            # Nothing was sent. The transcript is not at fault, so it is retried, not parked.
            raise DeliveryNotSent(f"could not open the MindGraph session: {exc}") from exc
        # A server that knows the key returns the first transcript on a resend
        # instead of storing a second. Older servers ignore it, and an SDK
        # without the argument is not given it; the tag lookup covers both.
        extra = (
            {"idempotency_key": f"hermes:{batch.batch_id}"} if _takes_idempotency_key(rt.client.ingest_session) else {}
        )
        if batch.captured_at:
            extra.update(
                context=json.dumps({
                    "schema": "memory-capture/v1",
                    "actor_scope": batch.actor_scope,
                    "turn_framing": batch.turn_framing,
                    "captured_at": batch.captured_at,
                    "time_basis": "live_turns" if batch.occurred_at else "checkpoint_observation",
                    "note": (
                        "Capture time is not the time of the events discussed. Turns are in conversation order. "
                        "If no document date is supplied, recovered turns' original timestamps are unavailable. "
                        "The actor scope identifies a Hermes profile, not an authenticated transport speaker."
                    ),
                }),
            )
        if batch.occurred_at:
            extra["occurred_at"] = batch.occurred_at
        try:
            response = rt.client.ingest_session(
                batch.content, title=batch_title(batch), session_uid=session_uid, agent_id=rt.agent_id, **extra
            )
        except MindGraphError as exc:
            status = exc.status or 0
            if status == 404:
                # The cached Session is gone on the server; the next attempt reopens it.
                with self._lock:
                    self._mg_sessions.pop(batch.session, None)
                raise DeliveryNotSent(str(exc)) from exc
            if status >= 500:
                raise DeliveryUncertain(str(exc)) from exc
            if status in (401, 403, 408, 409, 425, 429):
                # Credentials, a policy or load, answered before any write: a later attempt may pass.
                raise DeliveryNotSent(str(exc)) from exc
            raise DeliveryRejected(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise DeliveryNotSent(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            # A timeout, a dropped connection, an answer that is not JSON: it may have landed.
            raise DeliveryUncertain(f"{type(exc).__name__}: {exc}") from exc
        receipt = response if isinstance(response, dict) else {}
        document = receipt.get("document_uid") or receipt.get("doc_uid")
        job = receipt.get("job_id")
        return Receipt(
            # A replayed request names its Document and has no job of its own.
            job_id=job if isinstance(job, str) and job else None,
            document_uid=document if isinstance(document, str) and document else None,
        )

    def _find_batch(self, batch: Batch) -> Optional[Receipt]:
        """Whether an attempt of unknown outcome landed. The batch's tag is in
        the title of the job the server created, and of the transcript Document.
        The job list is quick but forgets (it lives in memory, 24 hours at
        most); the Document is durable, so it has the last word."""
        client = self._rt.client
        try:
            jobs = client.list_jobs()
        except MindGraphError as exc:
            if not _refused(exc):
                raise
            jobs = []  # this credential cannot list jobs; the Document search still can tell
        for job in jobs if isinstance(jobs, list) else []:
            if isinstance(job, dict) and batch.tag in str(job.get("title") or ""):
                job_id = job.get("id") or job.get("job_id")
                return Receipt(job_id=job_id if isinstance(job_id, str) else None)
        try:
            found = client.retrieve(action="text", query=batch.tag, node_types=["Document"], limit=5)
        except MindGraphError as exc:
            if _refused(exc):
                # Nothing here can verify. Resend: a possible duplicate is the lesser loss.
                return None
            raise
        for label, uid in _labels(found):
            if batch.tag in label:
                return Receipt(document_uid=uid)
        return None

    def _recover_capture(self) -> None:
        """Deliver what an earlier process left behind, off the startup path."""
        capture = self._capture
        if capture is None or not self._can_write():
            return
        try:
            capture.prune()
            # Parked batches get another round per process: the reason they
            # were refused (a key, a policy, a server bug) may be gone.
            requeued = capture.retry_failed()
            leftover = capture.status()
        except (CaptureError, sqlite3.Error) as exc:
            logger.warning("MindGraph capture queue could not be read at startup: %s", exc)
            return
        if not (requeued or leftover["pending_batches"] or leftover["buffered_parts"]):
            return

        def recover() -> None:
            try:
                capture.seal()
                self._deliverer.drain(force=True)
            except Exception as exc:
                logger.warning("MindGraph capture recovery failed (kept on disk): %s", exc)

        spawn_context_thread(recover, name="mindgraph-capture-recovery").start()

    def _capture_status(self) -> dict[str, Any]:
        """Queue state for ``mindgraph_memory status``, after asking the server
        what became of the most recent deliveries."""
        capture, rt = self._capture, self._rt
        if capture is None or rt is None:
            return {}
        for batch_id, job_id in capture.unsettled_receipts():
            try:
                job = rt.client.get_job(job_id)
            except MindGraphError as exc:
                if exc.status == 404:
                    capture.set_job_status(batch_id, "unknown")
                continue
            except Exception:
                continue
            status = job.get("status") if isinstance(job, dict) else None
            if isinstance(status, str) and status:
                detail = job.get("error_details") if isinstance(job.get("error_details"), dict) else {}
                error = detail.get("message") or job.get("error")
                capture.set_job_status(batch_id, status.lower(), error if isinstance(error, str) else None)
        return capture.status()

    def on_pre_compress(self, messages: list[dict[str, Any]], *, require_checkpoint: bool = False) -> str:
        """Checkpoint before a lossy rewrite.

        Always: seal the queued turns and start delivering them. With
        ``require_checkpoint`` (the operator's ``compression.checkpoint_required``)
        the transcript rows themselves are committed first, in any agent
        context, and a commit that fails raises so Hermes keeps the transcript.
        Success means committed to the profile's queue on disk; delivery to
        MindGraph follows at least once and never decides the outcome here."""
        rt, capture = self._rt, self._capture
        if rt is not None and self._recall is not None:
            # The turns being compressed carried earlier recall with them.
            self._recall.forget_injected(rt.session_id)
        if rt is None or capture is None:
            if require_checkpoint:
                raise RuntimeError("MindGraph capture is off; no pre-compress checkpoint can be taken")
            return ""
        if not (rt.write_enabled or require_checkpoint):
            return ""
        try:
            if require_checkpoint:
                if not capture.durable:
                    raise CaptureError("the capture queue is in memory only")
                capture.add_evidence(rt.session_id, evidence_rows(messages), context=rt.agent_context)
            self._flush("pre-compress", wait_s=CHECKPOINT_WAIT_S)
        except CaptureError:
            if require_checkpoint:
                self._drain("checkpoint rejected", force=True, wait_s=0.0)
                raise
            logger.warning("MindGraph pre-compress flush failed (non-fatal)", exc_info=True)
        return ""

    def on_memory_write(
        self, action: str, target: str, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """Commit a mirror operation before returning; delivery may be retried."""
        rt = self._rt
        if rt is None or not self._can_write() or self._outbox is None:
            return
        previous = (metadata or {}).get("previous_content")
        operations = []
        if action in ("add", "replace") and (content or "").strip():
            operations.append(("remember", {"text": content.strip(),
                                           "custom_id": builtin_memory_custom_id(target, content),
                                           "agent_id": rt.agent_id}))
        # Save the replacement first. Forgetting identical content would delete
        # the entry we just upserted. Unknown previous content never guesses identity.
        if (action in ("replace", "remove") and isinstance(previous, str) and previous.strip()
                and (action == "remove" or previous.strip() != (content or "").strip())):
            operations.append(("forget", {"custom_id": builtin_memory_custom_id(target, previous),
                                         "reason": f"Hermes built-in memory {action}", "agent_id": rt.agent_id}))
        self._outbox.enqueue(operations)
        self._outbox.kick(spawn_context_thread)

    def _send_memory_operation(self, action: str, payload: dict[str, Any]) -> None:
        if action == "remember":
            payload = dict(payload)
            self._rt.client.remember(payload.pop("text"), **payload)
        elif action == "forget":
            self._rt.client.forget(**payload)

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs: Any,
    ) -> None:
        rt = self._rt
        if rt is None or not new_session_id:
            return
        if rewound:
            # /undo truncated the transcript without saying how far. Undelivered
            # turns may include what the user retracted, so none are sent.
            if self._capture is not None:
                try:
                    dropped = self._capture.discard_session(new_session_id)
                except CaptureError as exc:
                    logger.warning("MindGraph could not discard undone turns: %s", exc)
                else:
                    if dropped:
                        logger.info("MindGraph dropped %d undelivered transcript rows after an undo", dropped)
            if self._recall is not None:
                self._recall.rewound(new_session_id)
            return
        if new_session_id == rt.session_id:
            return
        previous = rt.session_id
        self._flush_quietly("session switch", FLUSH_WAIT_S)
        if self._capture is not None and not reset and kwargs.get("reason") != "resume":
            # The same conversation under a new id (compression, a branch):
            # what was captured under the old id is not captured again.
            try:
                self._capture.carry_ledger(previous, new_session_id)
            except CaptureError as exc:
                logger.debug("MindGraph could not carry the capture ledger across a session switch: %s", exc)
        if self._recall is not None:
            if reset:
                self._recall.drop(previous)
            elif kwargs.get("reason") == "compression":
                # The same conversation under a new id: it keeps what it was
                # shown and is not briefed on open work a second time.
                self._recall.rebind(previous, new_session_id)
                with self._lock:
                    if previous in self._briefed_sessions:
                        self._briefed_sessions.add(new_session_id)
            # /resume and /branch open a different conversation: it starts with
            # no recall state, and the one left behind keeps its own.
        with self._lock:
            rt.session_id = new_session_id
            rt.turn_number = 0
        if self._capture is not None:
            bound = self._turn_context.get()
            author = bound[2] if bound and bound[0] == previous and kwargs.get("reason") == "compression" else {}
            self._turn_context.set((new_session_id, self._capture.epoch(new_session_id), author))
        self._close_sessions(only=previous)

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        self._flush_quietly("session end", FLUSH_WAIT_S)
        self._close_sessions()

    def _flush_quietly(self, reason: str, wait_s: float) -> None:
        """A flush at a boundary that promises nothing: what cannot be sealed or
        sent stays queued."""
        if not self._can_write():
            return
        if self._outbox is not None:
            self._outbox.kick(spawn_context_thread, force=True, wait_s=wait_s)
        try:
            self._flush(reason, wait_s=wait_s)
        except CaptureError as exc:
            logger.warning("MindGraph capture flush failed (%s; kept for the next flush): %s", reason, exc)

    def _close_sessions(self, only: Optional[str] = None) -> None:
        rt = self._rt
        if rt is None:
            return
        with self._lock:
            targets = {
                sid: uid for sid, uid in self._mg_sessions.items() if only is None or sid == only
            }
            for sid in targets:
                del self._mg_sessions[sid]
        for uid in targets.values():
            try:
                rt.client.session(action="close", session_uid=uid, agent_id=rt.agent_id)
            except Exception as exc:
                logger.debug("MindGraph session close failed (non-fatal): %s", exc)

    def shutdown(self) -> None:
        self._flush_quietly("shutdown", SHUTDOWN_WAIT_S)
        self._close_sessions()
        if self._store is not None:
            self._store.close()
        if self._rt is not None:
            self._rt.close()

    # ── Tools ──────────────────────────────────────────────────────────────

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        # Static only. Hermes builds its routing table from this list before
        # initialize(), so tools that appear later (the MCP server's generated
        # ontology tools) would be shown to the model but never routed. Domain
        # objects stay reachable through mindgraph_ontology.
        return static_tool_schemas()

    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs: Any) -> str:
        if self._rt is None or self._memory_config is None:
            return '{"error":"MindGraph provider is not initialized"}'
        return handle_tool(self._rt, self._gate, self._memory_config, tool_name, args)


def _refused(exc: MindGraphError) -> bool:
    """A 4xx that will not change on a retry (not a timeout or a rate limit)."""
    status = exc.status or 0
    return 400 <= status < 500 and status not in (408, 425, 429)
