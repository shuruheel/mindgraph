"""MindGraphMemoryProvider: the Hermes ``MemoryProvider`` lifecycle around the
mindgraph-mcp tool surface.

- ``initialize`` binds a ``Runtime`` (client, identity, session) to this instance.
- ``system_prompt_block`` is static: the MCP server's memory instructions.
- ``prefetch`` recalls bounded topic context for the current message, plus the
  open-work brief on a conversation's first turn.
- ``sync_turn`` buffers completed turns; the buffer is ingested as a session
  transcript before compression, at session end or switch, and whenever it
  grows past ``FLUSH_CHARS``, so nothing is sent twice.
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
from typing import Any, Optional

from agent.memory_provider import MemoryProvider
from agent.secret_scope import get_secret

from . import __version__
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

logger = logging.getLogger(__name__)

FLUSH_CHARS = 24_000
MAX_PENDING_CHARS = 200_000
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


def _render_turn(turn: dict[str, str]) -> str:
    parts = []
    if turn["user"]:
        parts.append(f"User: {turn['user']}")
    if turn["assistant"]:
        parts.append(f"Assistant: {turn['assistant']}")
    return "\n\n".join(parts)


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
        self._flush_lock = threading.Lock()
        self._pending: list[dict[str, str]] = []
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
        # mindgraph_memory status must describe what this provider actually does.
        self._memory_config = MemoryRuntimeConfig(
            server_version=__version__,
            base_url=base_url,
            org_id=org_id,
            agent_id=agent_id,
            automatic_capture=self._auto_capture and self._rt.write_enabled,
            automatic_delivery=True,
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
    # Locking: ``_lock`` guards the buffer and the session bindings and is never
    # held across network I/O, so caller-thread hooks (switch, compression) never
    # wait on a slow ingest. ``_flush_lock`` serializes flushes so batches reach
    # the server in turn order.

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
        """Runs on Hermes's background worker, so the flush may block."""
        if not self._can_write() or not self._auto_capture:
            return
        user, assistant = (user_content or "").strip(), (assistant_content or "").strip()
        if not (user or assistant):
            return
        with self._lock:
            # Tag with the turn's own conversation: a switch may already have
            # rebound the runtime by the time this queued call runs.
            self._pending.append({"session": session_id or self._rt.session_id, "user": user, "assistant": assistant})
            size = sum(len(t["user"]) + len(t["assistant"]) for t in self._pending)
        if size >= FLUSH_CHARS:
            self._flush("size")

    def _flush(self, reason: str) -> None:
        if not self._can_write():
            return
        rt = self._rt
        with self._flush_lock:
            with self._lock:
                batch, self._pending = self._pending, []
            failed: list[dict[str, str]] = []
            for harness_session_id in dict.fromkeys(turn["session"] for turn in batch):
                turns = [turn for turn in batch if turn["session"] == harness_session_id]
                try:
                    rt.client.ingest_session(
                        "\n\n".join(_render_turn(turn) for turn in turns),
                        title=f"Hermes session {harness_session_id}",
                        session_uid=self._ensure_session(harness_session_id),
                        agent_id=rt.agent_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "MindGraph transcript ingest failed (%s; %d turns kept): %s", reason, len(turns), exc
                    )
                    failed.extend(turns)
            if failed:
                with self._lock:
                    self._pending = failed + self._pending
                    self._bound_pending()

    def _bound_pending(self) -> None:
        """A persistently failing server must not grow the retry buffer forever."""
        total = sum(len(t["user"]) + len(t["assistant"]) for t in self._pending)
        while self._pending and total > MAX_PENDING_CHARS:
            dropped = self._pending.pop(0)
            total -= len(dropped["user"]) + len(dropped["assistant"])

    def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        self._flush("pre-compress")
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
            # /undo truncated the transcript without saying how far. Unflushed
            # turns may include what the user retracted, so none become durable.
            with self._lock:
                dropped = [t for t in self._pending if t["session"] == new_session_id]
                self._pending = [t for t in self._pending if t["session"] != new_session_id]
            if dropped:
                logger.info("MindGraph dropped %d unflushed turns after an undo", len(dropped))
            return
        if new_session_id == rt.session_id:
            return
        previous = rt.session_id
        self._flush("session switch")
        with self._lock:
            rt.session_id = new_session_id
            rt.turn_number = 0
        self._close_sessions(only=previous)

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        self._flush("session end")
        self._close_sessions()

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
        self._flush("shutdown")
        self._close_sessions()
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
