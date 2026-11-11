"""Per-message recall: what to ask MindGraph for, what is worth injecting, and
how long a turn may wait for it.

Recall runs before every model call, so its failure modes are the ones a
person notices: a turn that waits on a slow server, context about the wrong
thing, and the same items repeated message after message. Each has a rule here.

- **Query.** ``/retrieve/context`` OR-joins every query token into its keyword
  leg, so a sentence is reduced to its content terms. A message with too few of
  its own ("why?", "and the second one?") borrows the previous message's.
- **Floor.** An item is injected only when it mentions two distinct query terms
  (one, when the query has one). The server always returns its best matches;
  the best match for an unrelated message is still unrelated.
- **Deadline.** The live call gets ``deadline_s``. Past it the turn proceeds
  with the conversation's last recall, if that is on topic, and the late answer
  is kept for the next message.
- **Repeats.** An item already injected in this conversation is not injected
  again until compression drops it or its status changes.

This module does not import Hermes.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .render import node_display_type, status_tag

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
DEFAULT_MAX_CHARS = 4_000
DEFAULT_DEADLINE_S = 3.0
MAX_TERMS = 8
# Candidates fetched per injected slot: the floor discards some, and a second
# request to refill would cost the turn more than a wider first one.
OVERFETCH = 2
# A kept recall answers a later message only this long; after that the graph
# may have moved on.
CACHE_TTL_S = 600.0
NATURAL_QUERY_CHARS = 300
LABEL_MAX = 140
SUMMARY_MAX = 240
SOURCE_MAX = 100
HEADER = "Related memory (most relevant first):"

# Kept in step with mindgraph-mcp's hook-memory.ts (0.24.0 added the second
# group: function words that matched unrelated memory on their own).
STOPWORDS = frozenset(
    (
        "a an and are as at be but by can could did do does for from had has have how i if in into is it its "
        "me my of on or our please should so that the their them then there these they this to us was we were "
        "what when where which who why will with would you your about just also any some tell know want need "
        "let lets like get got make "
        "yes no not ok okay sure may might must up down out off over under again after before while "
        "without within including include use using used keep now next here than very more most "
        "other each both all one two been being am done going go"
    ).split()
)
# Unicode-aware: "decisión" and "Größe" are one word each, not fragments.
_WORD = re.compile(r"[^\W_][\w.\-/#+]*")
_SPLIT = re.compile(r"[\W_]+")
# Scripts written without spaces between words. A run of them is one "word" to
# a tokenizer, so neither keyword reduction nor a lexical floor means anything.
_UNSEGMENTED = re.compile(r"[฀-๿぀-ヿ㐀-䶿一-鿿가-힯]")
_INFRA_TYPES = frozenset({"Chunk", "Document", "Article", "Session"})


@dataclass(frozen=True)
class RecallConfig:
    enabled: bool = True
    limit: int = DEFAULT_LIMIT
    max_chars: int = DEFAULT_MAX_CHARS
    deadline_s: float = DEFAULT_DEADLINE_S
    floor: bool = True
    # A corpus Project that bounds recall. Opt-in: Hermes's own session
    # transcripts are not members of a Project, so a bound hides them.
    project_uid: Optional[str] = None
    # None leaves the question-aware rerank to the server's default.
    rerank: Optional[bool] = None


def _bounded(raw: Optional[str], default: float, low: float, high: float) -> float:
    try:
        value = float((raw or "").strip())
    except ValueError:
        return default
    return min(high, max(low, value))


def _switch(raw: Optional[str]) -> Optional[bool]:
    value = (raw or "").strip().lower()
    if value in ("1", "true", "on", "yes"):
        return True
    if value in ("0", "false", "off", "no"):
        return False
    return None


def workspace_project(hermes_home: Optional[str], cwd: Optional[str]) -> Optional[str]:
    """The Project mapped to this conversation's workspace in
    ``$HERMES_HOME/mindgraph/workspaces.json`` (``{"/abs/path": "project-uid"}``),
    by longest matching path prefix."""
    if not hermes_home or not cwd:
        return None
    try:
        mapping = json.loads((Path(hermes_home) / "mindgraph" / "workspaces.json").read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(mapping, dict):
        return None
    here = Path(cwd).expanduser()
    best: tuple[int, Optional[str]] = (-1, None)
    for root, uid in mapping.items():
        if not (isinstance(root, str) and isinstance(uid, str) and uid.strip()):
            continue
        base = Path(root).expanduser()
        if here == base or base in here.parents:
            depth = len(base.parts)
            if depth > best[0]:
                best = (depth, uid.strip())
    return best[1]


def load_config(
    get: Callable[[str, str], Optional[str]], *, hermes_home: Optional[str] = None, cwd: Optional[str] = None
) -> RecallConfig:
    """Recall settings from the profile's secret scope; every one is optional."""
    return RecallConfig(
        enabled=_switch(get("MINDGRAPH_RECALL", "")) is not False,
        limit=int(_bounded(get("MINDGRAPH_RECALL_LIMIT", ""), DEFAULT_LIMIT, 1, 20)),
        max_chars=int(_bounded(get("MINDGRAPH_RECALL_MAX_CHARS", ""), DEFAULT_MAX_CHARS, 512, 24_000)),
        deadline_s=_bounded(get("MINDGRAPH_RECALL_DEADLINE_MS", ""), DEFAULT_DEADLINE_S * 1000, 250, 8_000) / 1000,
        floor=_switch(get("MINDGRAPH_RECALL_FLOOR", "")) is not False,
        project_uid=(get("MINDGRAPH_PROJECT_UID", "") or "").strip() or workspace_project(hermes_home, cwd),
        rerank=_switch(get("MINDGRAPH_RECALL_RERANK", "")),
    )


# ── Query ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecallQuery:
    query: str
    # Terms the floor checks. Empty means no lexical floor applies.
    terms: tuple[str, ...] = ()
    borrowed: bool = False

    @property
    def key(self) -> str:
        return self.query


def content_terms(message: str, max_terms: int = MAX_TERMS) -> list[str]:
    """Discriminating words of a message, in order, without repeats."""
    seen: dict[str, None] = {}
    for word in _WORD.findall(message[:600]):
        key = word.lower().strip(".-/")
        if len(key) < 2 or key in STOPWORDS or key == "redacted" or key in seen:
            continue
        seen[key] = None
        if len(seen) >= max_terms:
            break
    return list(seen)


def build_query(message: str, previous: str = "") -> Optional[RecallQuery]:
    """The recall request for one message, or ``None`` when it carries nothing
    to recall on. ``previous`` is the person's message before it."""
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return None
    if _UNSEGMENTED.search(text):
        # The vector leg reads this; the keyword leg and the floor cannot.
        return RecallQuery(query=text[:NATURAL_QUERY_CHARS])
    terms = content_terms(text)
    borrowed = False
    if len(terms) < 2 and previous and not _UNSEGMENTED.search(previous):
        # "What did we decide?" names no subject; the message before it does.
        for term in content_terms(previous):
            if term not in terms:
                terms.append(term)
                borrowed = True
            if len(terms) >= MAX_TERMS:
                break
    if not terms:
        return None
    return RecallQuery(query=" ".join(terms), terms=tuple(terms), borrowed=borrowed)


# ── Relevance floor (port of hook-memory.ts ``recallTermOverlap``) ─────────


def _word_parts(text: str) -> list[str]:
    return [part for part in _SPLIT.split(text.lower()) if part]


def _same_word(left: str, right: str) -> bool:
    return left == right or (len(left) >= 4 and len(right) >= 4 and (left.startswith(right) or right.startswith(left)))


def term_overlap(terms: tuple[str, ...], text: str) -> tuple[int, int]:
    """``(matched, usable)``: how many distinct query terms the text mentions.
    A term counts through any part of three or more characters that appears as
    a word or the stem of one (``update`` ~ ``updates``). Bare numbers and
    two-letter fragments never count: "items 2-4" once matched "n = 4"."""
    hay = _word_parts(text)
    matched = usable = 0
    for term in dict.fromkeys(terms):
        parts = [part for part in _word_parts(term) if len(part) >= 3 and not part.isdigit()]
        if not parts:
            continue
        usable += 1
        if any(_same_word(word, part) for part in parts for word in hay):
            matched += 1
    return matched, usable


def relevant(query: RecallQuery, text: str) -> bool:
    if not query.terms:
        return True
    matched, usable = term_overlap(query.terms, text)
    return usable > 0 and matched >= min(2, usable)


# ── Rendering ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Item:
    uid: str
    line: str
    # uid plus status: a decision that has since been superseded is news.
    identity: str


def _text(value: Any) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _one_line(value: str, limit: int) -> str:
    flat = " ".join(value.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 1]}…"


def _stated(node: dict[str, Any]) -> Optional[str]:
    """The most recent date the item was stated, when the server annotated one."""
    stated = node.get("stated_at")
    if isinstance(stated, list):
        dates = [d for d in stated if isinstance(d, str) and d]
        return max(dates)[:10] if dates else None
    return stated[:10] if isinstance(stated, str) and stated else None


def select_items(response: Any, query: RecallQuery, *, floor: bool = True) -> list[Item]:
    """Injectable items of a ``/retrieve/context`` response, in the server's order."""
    payload = response if isinstance(response, dict) else {}
    graph = payload.get("graph") if isinstance(payload.get("graph"), dict) else {}
    items: list[Item] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        uid, kind = _text(node.get("uid")), node_display_type(node)
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        label = _text(node.get("label")) or _text(props.get("label")) or _text(props.get("name"))
        if not uid or not label or kind in _INFRA_TYPES:
            continue
        summary = (
            _text(node.get("summary")) or _text(props.get("summary")) or _text(props.get("description"))
            or _text(props.get("content"))
        )
        informative = summary if summary and summary != label else None
        # A bare entity name (a file path, an identifier) tells the model
        # nothing and takes a slot.
        if not informative and kind == "Entity":
            continue
        if floor and not relevant(query, f"{label} {informative or ''}"):
            continue
        status = status_tag(node)
        line = f"- [{kind}] {_one_line(label, LABEL_MAX)}{status}"
        if informative:
            line += f" — {_one_line(informative, SUMMARY_MAX)}"
        docs = node.get("source_documents") if isinstance(node.get("source_documents"), list) else []
        source = _text(docs[0].get("title")) if docs and isinstance(docs[0], dict) else None
        provenance = "; ".join(
            part
            for part in (
                f"stated {_stated(node)}" if _stated(node) else None,
                f"source: {_one_line(source, SOURCE_MAX)}" if source else None,
            )
            if part
        )
        if provenance:
            line += f" ({provenance})"
        items.append(Item(uid=uid, line=line, identity=f"{uid}{status}"))
    return items


def render_items(items: list[Item], max_chars: int) -> str:
    block = HEADER
    for item in items:
        if len(block) + 1 + len(item.line) > max_chars:
            break
        block += f"\n{item.line}"
    return block if block != HEADER else ""


# ── Engine ─────────────────────────────────────────────────────────────────


@dataclass
class Recalled:
    text: str = ""
    count: int = 0
    # live | cached | stale (kept recall used past the deadline) | none
    source: str = "none"


@dataclass
class _Kept:
    key: str
    terms: tuple[str, ...]
    response: Any
    at: float


@dataclass
class _Conversation:
    last_message: str = ""
    kept: Optional[_Kept] = None
    injected: set[str] = field(default_factory=set)
    # The query whose live call failed or ran late; retried off the turn path.
    retry: Optional[RecallQuery] = None


class RecallEngine:
    """Recall for one provider instance. ``fetch`` performs the
    ``/retrieve/context`` call for a query; ``spawn`` starts a daemon thread
    that carries the profile's context."""

    def __init__(
        self,
        fetch: Callable[[RecallQuery], Any],
        config: RecallConfig,
        spawn: Callable[..., threading.Thread],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self.config = config
        self._spawn = spawn
        self._clock = clock
        self._lock = threading.Lock()
        self._conversations: dict[str, _Conversation] = {}

    def _conversation(self, session: str) -> _Conversation:
        return self._conversations.setdefault(session, _Conversation())

    def recall(self, session: str, message: str, *, previous: str = "") -> Recalled:
        """Recall for the message about to be answered. Never raises and never
        waits past the deadline."""
        if not self.config.enabled:
            return Recalled()
        with self._lock:
            conversation = self._conversation(session)
            query = build_query(message, conversation.last_message or previous)
            conversation.last_message = (message or "").strip() or conversation.last_message
            kept = conversation.kept
        if query is None:
            return Recalled()
        now = self._clock()
        if kept is not None and kept.key == query.key and now - kept.at <= CACHE_TTL_S:
            return self._inject(session, query, kept.response, "cached")

        box: dict[str, Any] = {}
        done = threading.Event()

        def run() -> None:
            try:
                box["response"] = self._fetch(query)
            except Exception as exc:
                box["error"] = exc
                self._mark_retry(session, query)  # on time or late: redo it off the turn path
            else:
                self._keep(session, query, box["response"])
            finally:
                done.set()

        self._spawn(run, name="mindgraph-recall").start()
        if done.wait(self.config.deadline_s):
            if "error" in box:
                logger.debug("MindGraph recall failed: %s", box["error"])
                return self._fallback(session, query, kept)
            return self._inject(session, query, box["response"], "live")
        logger.info(
            "MindGraph recall passed its %.1fs deadline; the turn proceeds and the answer is kept for the next message",
            self.config.deadline_s,
        )
        return self._fallback(session, query, kept)

    def _keep(self, session: str, query: RecallQuery, response: Any) -> None:
        with self._lock:
            conversation = self._conversation(session)
            conversation.kept = _Kept(query.key, query.terms, response, self._clock())
            if conversation.retry is not None and conversation.retry.key == query.key:
                conversation.retry = None

    def _mark_retry(self, session: str, query: RecallQuery) -> None:
        with self._lock:
            self._conversation(session).retry = query

    def _fallback(self, session: str, query: RecallQuery, kept: Optional[_Kept]) -> Recalled:
        """The conversation's last recall, when it is recent and shares a term
        with this message. The floor then decides item by item."""
        if kept is None or self._clock() - kept.at > CACHE_TTL_S or not query.terms:
            return Recalled()
        if not set(query.terms) & set(kept.terms):
            return Recalled()
        return self._inject(session, query, kept.response, "stale")

    def _inject(self, session: str, query: RecallQuery, response: Any, source: str) -> Recalled:
        items = select_items(response, query, floor=self.config.floor)
        with self._lock:
            conversation = self._conversation(session)
            fresh = [item for item in items if item.identity not in conversation.injected][: self.config.limit]
            text = render_items(fresh, self.config.max_chars)
            shown = [item for item in fresh if item.line in text]
            conversation.injected.update(item.identity for item in shown)
        return Recalled(text=text, count=len(shown), source=source if shown else "none")

    def after_turn(self, session: str, message: str) -> None:
        """Runs off the turn path once a turn completes: retry a recall that
        failed, so the next message has something to fall back on. A healthy
        conversation makes no extra call here."""
        if not self.config.enabled:
            return
        with self._lock:
            conversation = self._conversation(session)
            conversation.last_message = (message or "").strip() or conversation.last_message
            query, conversation.retry = conversation.retry, None
        if query is None:
            return
        try:
            self._keep(session, query, self._fetch(query))
        except Exception as exc:
            logger.debug("MindGraph background recall retry failed: %s", exc)

    def forget_injected(self, session: str) -> None:
        """Compression dropped earlier turns, and the items injected with them."""
        with self._lock:
            if session in self._conversations:
                self._conversations[session].injected.clear()

    def rebind(self, old: str, new: str) -> None:
        """A conversation continued under a new id keeps its recall state."""
        with self._lock:
            if old in self._conversations and new not in self._conversations:
                self._conversations[new] = self._conversations.pop(old)

    def drop(self, session: str) -> None:
        with self._lock:
            self._conversations.pop(session, None)
