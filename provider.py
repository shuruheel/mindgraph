"""MindGraphMemoryProvider: the Hermes ``MemoryProvider`` lifecycle around the
mindgraph-mcp tool surface.

- ``initialize`` binds a ``Runtime`` (client, identity, session) to this instance.
- ``system_prompt_block`` is static: the MCP server's memory instructions.
- ``prefetch`` recalls bounded topic context for the current message, plus the
  open-work brief on a conversation's first turn.
- ``sync_turn`` commits completed turns to the profile's capture queue
  (``capture.py``); the queue is sealed into batches and delivered as session
  transcripts before compression, at session end or switch, and whenever it
  grows past ``FLUSH_CHARS``. A batch leaves the queue only when the server
  took it, so a crash or an outage delays capture instead of losing it.
- ``on_pre_compress`` is a checkpoint (API v2): with ``require_checkpoint`` the
  transcript rows about to be compressed are committed first, and a failed
  commit raises so Hermes keeps the uncompressed transcript.
- ``on_memory_write`` mirrors Hermes's built-in memory into ``/memory/remember``.
- Tool calls route through ``dispatch.handle_tool`` behind the governance gate.

Automatic writes run only for the ``primary`` agent context.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
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
    DeliveryRejected,
    DeliveryUncertain,
    Receipt,
)
from .dispatch import contract, handle_tool, static_tool_schemas
from .governance import GovernanceGate
from .memory_tool import MemoryRuntimeConfig, handle_memory_tool
from .render import render_resume_context
from .results import is_error
from .runtime import DEFAULT_AGENT_ID, DEFAULT_BASE_URL, HARNESS, Runtime

try:  # RecallStatus drives the "🧠 MindGraph — recalled N memories" line on newer Hermes.
    from agent.memory_provider import RecallStatus
except ImportError:  # pragma: no cover - older Hermes
    RecallStatus = None  # type: ignore[assignment,misc]

try:  # Background work must carry the profile's contextvars (HERMES_HOME, secret scope).
    from agent.memory_provider import spawn_context_thread
except ImportError:  # pragma: no cover - older Hermes

    def spawn_context_thread(target, *, name, daemon=True, args=(), kwargs=None):  # type: ignore[misc]
        return threading.Thread(target=target, name=name, daemon=daemon, args=args, kwargs=kwargs)

logger = logging.getLogger(__name__)

FLUSH_CHARS = 24_000
# Hermes's pre-compress checkpoint contract this provider implements when its
# queue is on disk. 1 is the best-effort legacy contract.
CHECKPOINT_API_VERSION = 2
# A flush point waits this long for delivery. What is still queued afterwards
# is on disk and goes out at the next flush or the next start.
FLUSH_BUDGET_S = 20.0
# Marker Hermes leaves on a previous compaction's summary row; a summary is
# derived text, never evidence.
_COMPRESSED_SUMMARY_KEY = "_compressed_summary"
PREFETCH_MAX_CHARS = 4_000
PREFETCH_LIMIT = 5
MIN_PREFETCH_CHARS = 12
_STOPWORDS = frozenset(
    "a an and are as at be but by can could did do does for from had has have how i if in into is it its "
    "me my of on or our please should so that the their them then there these they this to us was we were "
    "what when where which who why will with would you your about just also any some tell know want need "
    "let lets like get got make".split()
)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-/#+]*")

_HERMES_NOTES = """
## In Hermes

- Relevant MindGraph context is recalled automatically for each message and appears in the turn as "MindGraph context". Call `mindgraph_memory` only when that recall is insufficient.
- Completed turns are ingested into MindGraph as a session transcript, so do not re-store what was simply said; use the typed write tools for decisions, corrections, lessons and facts that need structure or confidence.
- Writes from Hermes's built-in memory tool are mirrored into MindGraph automatically."""


def topic_query(message: str, max_terms: int = 8) -> str:
    """Discriminating keywords for BM25 topic recall: a full sentence dilutes the
    query with words every node shares."""
    seen: dict[str, None] = {}
    for word in _WORD.findall(message[:600]):
        key = word.lower().strip(".-/")
        if len(key) < 2 or key in _STOPWORDS or key in seen:
            continue
        seen[key] = None
        if len(seen) >= max_terms:
            break
    return " ".join(seen)


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


def batch_title(batch: Batch, agent_context: str) -> str:
    """The transcript title. The tag makes a batch findable among the server's
    jobs, which is how an attempt of unknown outcome is reconciled."""
    kind = "session" if agent_context == "primary" else f"{agent_context} session"
    return f"Hermes {kind} {batch.session} · {batch.tag}"


class MindGraphMemoryProvider(MemoryProvider):
    """MindGraph semantic graph memory for Hermes Agent."""

    def __init__(self) -> None:
        self._rt: Optional[Runtime] = None
        self._gate: Optional[GovernanceGate] = None
        self._memory_config: Optional[MemoryRuntimeConfig] = None
        self._model: str = ""
        self._auto_capture = True
        self._briefed_sessions: set[str] = set()
        self._recall_count: Optional[int] = None
        self._recall_generation = 0
        # sync_turn (manager worker) and session switch/end/shutdown (caller
        # thread) both touch the pending buffer and the session bindings.
        self._lock = threading.Lock()
        self._capture: Optional[CaptureQueue] = None
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
        if self._auto_capture:
            # Bound to this profile's directory, like every other binding here.
            self._capture = CaptureQueue.open(kwargs.get("hermes_home"))
            self._deliverer = Deliverer(self._capture, self._send_batch, self._find_batch)
            self._recover_capture()
        # mindgraph_memory status must describe what this provider actually does.
        self._memory_config = MemoryRuntimeConfig(
            server_version=__version__,
            base_url=base_url,
            org_id=org_id,
            agent_id=agent_id,
            automatic_capture=self._auto_capture and self._rt.write_enabled,
            automatic_delivery=True,
            capture_status=self._capture_status if self._capture is not None else None,
        )

    def system_prompt_block(self) -> str:
        if self._rt is None:
            return ""
        return f"# MindGraph memory\n\n{contract()['instructions']}\n{_HERMES_NOTES}"

    def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        if self._rt is not None:
            self._rt.turn_number = max(int(turn_number or 0), 0)
        if kwargs.get("model"):
            self._model = str(kwargs["model"])

    # ── Recall ─────────────────────────────────────────────────────────────

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall for the current message.

        Hermes runs this on a thread bounded by its prefetch timeout. A call that
        outlives that timeout must not overwrite a later turn's recall status, so
        each call takes a generation and only the latest one may publish.
        """
        with self._lock:
            self._recall_generation += 1
            generation = self._recall_generation
            self._recall_count = None
        rt = self._rt
        if rt is None or self._memory_config is None:
            return ""
        sections: list[str] = []
        count = 0
        brief = self._first_turn_brief(session_id or rt.session_id)
        if brief:
            sections.append(brief)
            count += 1
        terms = topic_query(query or "") if len((query or "").strip()) >= MIN_PREFETCH_CHARS else ""
        if terms:
            result = handle_memory_tool(
                rt,
                {
                    "action": "context",
                    "mode": "topic",
                    "query": terms,
                    "limit": PREFETCH_LIMIT,
                    "max_output_chars": PREFETCH_MAX_CHARS,
                    "agent_id": rt.agent_id,
                },
                self._memory_config,
            )
            rendered, returned = _rendered_context(result)
            if rendered:
                sections.append(rendered)
                count += returned
        if not sections:
            return ""
        with self._lock:
            if generation == self._recall_generation:
                self._recall_count = count
        return "## MindGraph context (recalled for this message)\n\n" + "\n\n".join(sections)

    def _first_turn_brief(self, session_id: str) -> str:
        """Open work, once per conversation, and only when there is some. A failed
        lookup is retried on the next message."""
        rt = self._rt
        if rt is None or session_id in self._briefed_sessions:
            return ""
        try:
            brief = rt.client.plan(action="resume_work", agent_id=rt.agent_id, limit=1)
        except Exception as exc:
            logger.debug("MindGraph resume brief failed (non-fatal): %s", exc)
            return ""
        self._briefed_sessions.add(session_id)
        if not isinstance(brief, dict) or not brief.get("task"):
            return ""
        return render_resume_context(brief) or ""

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

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "", **kwargs: Any) -> None:
        """Runs on Hermes's background worker: one local commit, then delivery
        of whatever is due."""
        if not self._can_write() or self._capture is None:
            return
        user, assistant = (user_content or "").strip(), (assistant_content or "").strip()
        if not (user or assistant):
            return
        try:
            # Tagged with the turn's own conversation: a switch may already have
            # rebound the runtime by the time this queued call runs.
            open_chars = self._capture.add_turn(session_id or self._rt.session_id, user, assistant)
        except CaptureError as exc:
            logger.warning("MindGraph could not queue a turn for capture: %s", exc)
            return
        if open_chars >= FLUSH_CHARS:
            self._flush("size")
        else:
            self._drain("retry", force=False)  # a batch that was backing off may be due

    def _flush(self, reason: str) -> None:
        """Seal what is open and deliver. A seal that cannot commit raises:
        callers that promise durability must not swallow it."""
        if self._capture is None:
            return
        self._capture.seal()
        self._drain(reason, force=True)

    def _drain(self, reason: str, *, force: bool) -> None:
        if self._deliverer is None or self._rt is None:
            return
        result = self._deliverer.drain(force=force, budget_s=FLUSH_BUDGET_S)
        if result.delivered or result.reconciled or result.parked:
            logger.debug(
                "MindGraph capture (%s): %d delivered, %d reconciled, %d parked%s",
                reason, result.delivered, result.reconciled, result.parked,
                f"; stopped: {result.blocked}" if result.blocked else "",
            )

    def _send_batch(self, batch: Batch) -> Receipt:
        rt = self._rt
        try:
            response = rt.client.ingest_session(
                batch.content,
                title=batch_title(batch, rt.agent_context),
                session_uid=self._ensure_session(batch.session),
                agent_id=rt.agent_id,
            )
        except MindGraphError as exc:
            status = exc.status or 0
            if status == 404:
                # The cached Session is gone on the server; the next attempt reopens it.
                with self._lock:
                    self._mg_sessions.pop(batch.session, None)
                raise
            if status >= 500:
                raise DeliveryUncertain(str(exc)) from exc
            if status in (401, 403, 408, 409, 425, 429):
                raise  # credentials, a policy or load: a later attempt may pass
            raise DeliveryRejected(str(exc)) from exc
        except httpx.ConnectError:
            raise  # never reached the server
        except httpx.TransportError as exc:
            raise DeliveryUncertain(f"{type(exc).__name__}: {exc}") from exc
        receipt = response if isinstance(response, dict) else {}
        document = receipt.get("document_uid") or receipt.get("doc_uid")
        job = receipt.get("job_id")
        return Receipt(
            job_id=job if isinstance(job, str) else None,
            document_uid=document if isinstance(document, str) else None,
        )

    def _find_batch(self, batch: Batch) -> Optional[Receipt]:
        """Whether an attempt of unknown outcome landed: its tag is in the title
        of the job the server created for it."""
        try:
            jobs = self._rt.client.list_jobs()
        except MindGraphError as exc:
            if 400 <= (exc.status or 0) < 500 and exc.status not in (408, 425, 429):
                # This credential cannot list jobs, so nothing can be verified.
                # Resend: a possible duplicate is the lesser loss.
                return None
            raise
        for job in jobs if isinstance(jobs, list) else []:
            if isinstance(job, dict) and batch.tag in str(job.get("title") or ""):
                job_id = job.get("id") or job.get("job_id")
                return Receipt(job_id=job_id if isinstance(job_id, str) else None)
        return None

    def _recover_capture(self) -> None:
        """Deliver what an earlier process left behind, off the startup path."""
        capture = self._capture
        if capture is None or not self._can_write():
            return
        try:
            capture.prune()
            # Parked batches get one more attempt per process: the reason they
            # were refused (a key, a policy, a server bug) may be gone.
            requeued = capture.retry_failed()
            leftover = capture.status()
        except CaptureError as exc:
            logger.warning("MindGraph capture queue could not be read at startup: %s", exc)
            return
        if not (requeued or leftover["pending_batches"] or leftover["buffered_parts"]):
            return

        def recover() -> None:
            try:
                self._flush("recovery")
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

        Always: seal the queued turns and deliver them. With
        ``require_checkpoint`` (the operator's ``compression.checkpoint_required``)
        the transcript rows themselves are committed first, in any agent
        context, and a commit that fails raises so Hermes keeps the transcript.
        Success means committed to the profile's queue on disk; delivery to
        MindGraph follows at least once."""
        rt, capture = self._rt, self._capture
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
                capture.add_evidence(rt.session_id, evidence_rows(messages))
            self._flush("pre-compress")
        except CaptureError:
            if require_checkpoint:
                raise
            logger.warning("MindGraph pre-compress flush failed (non-fatal)", exc_info=True)
        return ""

    def on_memory_write(
        self, action: str, target: str, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """Mirror built-in memory writes, keyed by content so replays upsert."""
        rt = self._rt
        if rt is None or not self._can_write():
            return
        previous = (metadata or {}).get("previous_content")
        # Without the replaced entry's content its identity is unknown; never guess a forget.
        if action in ("replace", "remove") and isinstance(previous, str) and previous.strip():
            try:
                rt.client.forget(
                    custom_id=builtin_memory_custom_id(target, previous),
                    reason=f"Hermes built-in memory {action}",
                    agent_id=rt.agent_id,
                )
            except Exception as exc:  # e.g. an entry written before this provider was active
                logger.debug("MindGraph forget of replaced built-in memory failed: %s", exc)
        if action in ("add", "replace") and (content or "").strip():
            try:
                rt.client.remember(
                    content.strip(),
                    custom_id=builtin_memory_custom_id(target, content),
                    agent_id=rt.agent_id,
                )
            except Exception as exc:
                logger.warning("MindGraph mirror of built-in memory %s failed: %s", action, exc)

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
            return
        if new_session_id == rt.session_id:
            return
        previous = rt.session_id
        self._flush_quietly("session switch")
        with self._lock:
            rt.session_id = new_session_id
            rt.turn_number = 0
        self._close_sessions(only=previous)

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        self._flush_quietly("session end")
        self._close_sessions()

    def _flush_quietly(self, reason: str) -> None:
        """A flush at a boundary that promises nothing: what cannot be sealed or
        sent stays queued."""
        if not self._can_write():
            return
        try:
            self._flush(reason)
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
        self._flush_quietly("shutdown")
        self._close_sessions()
        if self._capture is not None:
            self._capture.close()
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


def _rendered_context(result: str) -> tuple[str, int]:
    """Rendered text and returned-item count from a memory-tool result; an empty
    recall injects nothing."""
    if is_error(result):
        logger.debug("MindGraph topic recall failed: %s", result[:300])
        return "", 0
    try:
        decoded = json.loads(result)
    except ValueError:
        return "", 0
    text = decoded.get("result") if isinstance(decoded, dict) else None
    budget = (decoded.get("structured") or {}).get("budget") if isinstance(decoded, dict) else None
    returned = budget.get("returned_items") if isinstance(budget, dict) else None
    if returned == 0 or not text:
        return "", 0
    return text.strip(), returned if isinstance(returned, int) else 1
