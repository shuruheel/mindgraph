"""Per-message recall: what to ask MindGraph for, what is worth injecting, and
how long a turn may wait for it.

Recall runs before every model call, so its failure modes are the ones a
person notices: a turn that waits on a slow server, context about the wrong
thing, and the same items repeated message after message. Each has a rule here.

- **Query.** ``/retrieve/context`` OR-joins every query token into its keyword
  leg, so a sentence is reduced to its content terms. A message with too few of
  its own ("why?", "what did we decide?") borrows the previous message's.
- **Floor.** An item is injected only when it mentions at least half of the usable
  query terms and at least two distinct terms (one for a one-term query). The server always returns its best matches;
  the best match for an unrelated message is still unrelated. For a borrowed
  query, one of the message's own terms is enough, so "what about Postgres?"
  finds Postgres and is not outvoted by the topic it moved on from.
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
# Under Hermes's own 8 s prefetch timeout: an answer Hermes has stopped
# waiting for would be marked as shown without being shown.
MAX_DEADLINE_MS = 6_000
MAX_TERMS = 8
# Candidates fetched per injected slot: the floor discards some, and a second
# request to refill would cost the turn more than a wider first one.
OVERFETCH = 2
# Extra candidates for a conversation that has already been shown some:
# without them a steady topic runs out of new items after two messages.
MAX_EXTRA_CANDIDATES = 20
# A kept recall answers a later message only this long; after that the graph
# may have moved on.
CACHE_TTL_S = 600.0
NATURAL_QUERY_CHARS = 300
MAX_UNSEGMENTED_RUNS = 3
LABEL_MAX = 140
SUMMARY_MAX = 240
SOURCE_MAX = 100
HEADER = "Related memory (most relevant first):"

# The English groups are kept in step with mindgraph-mcp's hook-memory.ts
# (0.24.0 added the second: function words that matched unrelated memory on
# their own).
_ENGLISH = (
    "a an and are as at be but by can could did do does for from had has have how i if in into is it its "
    "me my of on or our please should so that the their them then there these they this to us was we were "
    "what when where which who why will with would you your about just also any some tell know want need "
    "let lets like get got make "
    "yes no not ok okay sure may might must up down out off over under again after before while "
    "without within including include use using used keep now next here than very more most "
    "other each both all one two been being am done going go"
)
# Function words of other Latin-script languages. Without them a Spanish or
# German sentence fills the term cap with articles and prepositions, and two of
# those are enough to pass the floor. Words that are content terms in English
# ("die", "son", "pour", "sin", "war") are left out on purpose.
_OTHER_LATIN = (
    "que qué cual cuál como cómo cuando cuándo donde dónde porque para por con sobre entre desde hasta "
    "pero este esta esto estos estas ese esa eso los las del una unos unas fue han ser está están "
    "nuestro nuestra tiene tenemos "
    "les des une avec dans sur sous mais donc est sont était été cette ces quel quelle quoi "
    "comment pourquoi notre nous vous ils elles leur "
    "der das dem ein eine einen einem einer und oder aber nicht mit von für auf aus bei nach über "
    "unter wie warum wann welche welcher ist sind wurde haben wir ihr sie "
    "não uma uns umas nos nas pelo pela com sem mas foi são isso essa esse nosso nossa "
    "che chi cosa quando dove perché senza della dello degli delle nel nella sono gli uno"
)
STOPWORDS = frozenset(f"{_ENGLISH} {_OTHER_LATIN}".split())
# Unicode-aware: "decisión" and "Größe" are one word each, not fragments.
_WORD = re.compile(r"[^\W_][\w.\-/#+]*")
_SPLIT = re.compile(r"[\W_]+")
# Scripts written without spaces between words (Thai, Lao, Myanmar, Khmer,
# Japanese, Chinese), and Hangul, whose particles attach to the word. A run of
# them is one "word" to a tokenizer, so neither keyword reduction nor a lexical
# floor means anything for it.
_UNSEGMENTED = re.compile(
    "[฀-໿က-႟ក-៿぀-ヿ㐀-䶿一-鿿"
    "가-힯豈-﫿･-ﾟ\U00020000-\U0002a6df]+"
)
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
    if value != value:  # NaN
        return default
    return min(high, max(low, value))


def _switch(raw: Optional[str]) -> Optional[bool]:
    value = (raw or "").strip().lower()
    if value in ("1", "true", "on", "yes"):
        return True
    if value in ("0", "false", "off", "no"):
        return False
    return None


def _resolved(path: str) -> Path:
    """Absolute, with symlinks followed, so /tmp/x and /private/tmp/x agree."""
    expanded = Path(path).expanduser()
    try:
        return expanded.resolve()
    except OSError:
        return expanded.absolute()


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
    here = _resolved(cwd)
    best: tuple[int, Optional[str]] = (-1, None)
    for root, uid in mapping.items():
        if not (isinstance(root, str) and isinstance(uid, str) and uid.strip()):
            continue
        base = _resolved(root)
        if here == base or base in here.parents:
            depth = len(base.parts)
            if depth > best[0]:
                best = (depth, uid.strip())
    return best[1]


def load_config(
    get: Callable[[str, str], Optional[str]], *, hermes_home: Optional[str] = None, cwd: Optional[str] = None
) -> RecallConfig:
    """Recall settings from the profile's secret scope; every one is optional."""
    deadline_ms = _bounded(get("MINDGRAPH_RECALL_DEADLINE_MS", ""), DEFAULT_DEADLINE_S * 1000, 250, MAX_DEADLINE_MS)
    return RecallConfig(
        enabled=_switch(get("MINDGRAPH_RECALL", "")) is not False,
        limit=int(_bounded(get("MINDGRAPH_RECALL_LIMIT", ""), DEFAULT_LIMIT, 1, 20)),
        max_chars=int(_bounded(get("MINDGRAPH_RECALL_MAX_CHARS", ""), DEFAULT_MAX_CHARS, 512, 24_000)),
        deadline_s=deadline_ms / 1000,
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
    # The message's own terms, when the rest were borrowed from the one before.
    own: tuple[str, ...] = ()
    borrowed: bool = False

    @property
    def key(self) -> str:
        return self.query


def content_terms(message: str, max_terms: int = MAX_TERMS) -> list[str]:
    """Discriminating words of a message, in order, without repeats. A
    two-letter word is kept only when it reads as a name ("CI", "S3"), never
    as a lowercase function word ("la", "de")."""
    seen: dict[str, None] = {}
    for word in _WORD.findall(_UNSEGMENTED.sub(" ", message[:600])):
        stripped = word.strip(".-/")
        key = stripped.lower()
        if len(key) < 2 or key in STOPWORDS or key == "redacted" or key in seen:
            continue
        if len(key) == 2 and not (stripped.isupper() or any(ch.isdigit() for ch in key)):
            continue
        seen[key] = None
        if len(seen) >= max_terms:
            break
    return list(seen)


def _is_command(text: str) -> bool:
    """A slash command ("/compress", "/model gpt") and not a path that opens a
    message ("/Users/me/app.py fails")."""
    head = text.split(None, 1)[0]
    return head.startswith("/") and "/" not in head[1:]


def build_query(message: str, previous: str = "") -> Optional[RecallQuery]:
    """The recall request for one message, or ``None`` when it carries nothing
    to recall on. ``previous`` is the person's message before it."""
    text = (message or "").strip()
    if not text or _is_command(text):
        return None
    terms = content_terms(text)
    runs = [run[:40] for run in _UNSEGMENTED.findall(text)][:MAX_UNSEGMENTED_RUNS]
    if runs and not terms:
        # The vector leg reads this; the keyword leg and the floor cannot.
        return RecallQuery(query=text[:NATURAL_QUERY_CHARS])
    own = tuple(terms)
    borrowed = False
    if len(terms) < 2 and previous and not runs:
        # "What did we decide?" names no subject; the message before it does.
        for term in content_terms(previous):
            if term not in terms:
                terms.append(term)
                borrowed = True
            if len(terms) >= MAX_TERMS:
                break
    if not terms:
        return None
    # Unsegmented runs ride along for the vector leg; the floor reads the
    # delimited terms only.
    return RecallQuery(
        query=" ".join([*terms, *runs]), terms=tuple(terms), own=own if borrowed else (), borrowed=borrowed
    )


# ── Relevance floor ────────────────────────────────────────────────────────
#
# Started as a port of hook-memory.ts ``recallTermOverlap``. Two departures:
# words are compared by stem ("policies" ~ "policy", "bugs" ~ "bug"), and a
# prefix counts only when little is left over ("test" does not match
# "testament").


def _word_parts(text: str) -> list[str]:
    return [part for part in _SPLIT.split(text.lower()) if part]


def _stems(word: str) -> set[str]:
    """The word and what is left of it without a plural or tense ending."""
    forms = {word}
    for suffix, replacement in (("ies", "y"), ("es", ""), ("s", ""), ("ing", ""), ("ed", ""), ("d", "")):
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= 3:
            forms.add(word[: len(word) - len(suffix)] + replacement)
    return forms


def _same_word(left: str, right: str) -> bool:
    if left == right or _stems(left) & _stems(right):
        return True
    short, long = sorted((left, right), key=len)
    return len(short) >= 4 and long.startswith(short) and len(long) - len(short) <= 3


def term_overlap(terms: tuple[str, ...], text: str) -> tuple[int, int]:
    """``(matched, usable)``: how many distinct query terms the text mentions.
    A term counts through any part of three or more characters that appears as
    a word or a form of one (``update`` ~ ``updates``). Bare numbers and
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


def _on_own_subject(query: RecallQuery, text: str) -> bool:
    return bool(query.borrowed and query.own and term_overlap(query.own, text)[0] >= 1)


def relevant(query: RecallQuery, text: str) -> bool:
    if not query.terms:
        return True
    if query.borrowed and query.own:
        # The message's own subject outranks the one it borrowed.
        if _on_own_subject(query, text):
            return True
        lent = tuple(term for term in query.terms if term not in query.own)
        matched, usable = term_overlap(lent, text)
        return usable > 0 and matched >= max(min(2, usable), (usable + 1) // 2)
    matched, usable = term_overlap(query.terms, text)
    # Two generic overlaps in a longer question ("child", "center") must not
    # admit a child-study center for a CSS flexbox question.
    return usable > 0 and matched >= max(min(2, usable), (usable + 1) // 2)


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
    """Injectable items of a ``/retrieve/context`` response, in the server's
    order; for a borrowed query, items on the message's own subject first."""
    payload = response if isinstance(response, dict) else {}
    graph = payload.get("graph") if isinstance(payload.get("graph"), dict) else {}
    items: list[Item] = []
    leading: set[str] = set()
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
        subject = f"{label} {informative or ''}"
        if floor and not relevant(query, subject):
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
        if _on_own_subject(query, subject):
            leading.add(uid)
    # "What about Postgres?" after a Redis discussion: Postgres first.
    return sorted(items, key=lambda item: item.uid not in leading) if leading else items


def render_items(items: list[Item], max_chars: int) -> str:
    block = HEADER
    for item in items:
        if len(block) + 1 + len(item.line) > max_chars:
            continue  # one long line must not shut out the shorter ones after it
        block += f"\n{item.line}"
    return block if block != HEADER else ""


# ── Engine ─────────────────────────────────────────────────────────────────


@dataclass
class Recalled:
    text: str = ""
    count: int = 0
    # live | cached | stale (kept recall used past the deadline) | none
    source: str = "none"
    # Separate successful empty recall from a failed/late request.
    outcome: str = "not_requested"


@dataclass
class _Kept:
    key: str
    terms: tuple[str, ...]
    response: Any
    at: float
    seq: int


@dataclass
class _Conversation:
    last_message: str = ""
    kept: Optional[_Kept] = None
    injected: set[str] = field(default_factory=set)
    # The query whose live call failed; retried off the turn path.
    retry: Optional[RecallQuery] = None
    retrying: bool = False


class RecallEngine:
    """Recall for one provider instance. ``fetch`` performs the
    ``/retrieve/context`` call for a query and a candidate count; ``spawn``
    starts a daemon thread that carries the profile's context."""

    def __init__(
        self,
        fetch: Callable[[RecallQuery, int], Any],
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
        self._seq = 0

    def _conversation(self, session: str) -> _Conversation:
        return self._conversations.setdefault(session, _Conversation())

    def _candidates(self, conversation: _Conversation) -> int:
        return self.config.limit * OVERFETCH + min(len(conversation.injected), MAX_EXTRA_CANDIDATES)

    def recall(self, session: str, message: str, *, previous: str = "") -> Recalled:
        """Recall for the message about to be answered. Never raises and never
        waits past the deadline. ``previous`` is Hermes's record of the
        person's last message; this process's own record is the fallback."""
        if not self.config.enabled:
            return Recalled(outcome="disabled")
        with self._lock:
            conversation = self._conversation(session)
            query = build_query(message, previous or conversation.last_message)
            conversation.last_message = (message or "").strip() or conversation.last_message
            kept = conversation.kept
            self._seq += 1
            seq = self._seq
            candidates = self._candidates(conversation)
        if query is None:
            return Recalled(outcome="no_query")
        now = self._clock()
        if kept is not None and kept.key == query.key and now - kept.at <= CACHE_TTL_S:
            cached = self._inject(session, query, kept.response, "cached")
            if cached.count:
                return cached
            # Everything in the kept answer has been shown: ask again, wider.

        box: dict[str, Any] = {}
        done = threading.Event()

        def run() -> None:
            try:
                box["response"] = self._fetch(query, candidates)
            except Exception as exc:
                box["error"] = exc
                self._mark_retry(session, query)  # on time or late: redo it off the turn path
            else:
                self._keep(session, query, box["response"], seq)
            finally:
                done.set()

        self._spawn(run, name="mindgraph-recall").start()
        if done.wait(self.config.deadline_s):
            if "error" in box:
                logger.debug("MindGraph recall failed: %s", box["error"])
                return self._fallback(session, query, kept, "error")
            return self._inject(session, query, box["response"], "live")
        logger.info(
            "MindGraph recall passed its %.1fs deadline; the turn proceeds and the answer is kept for the next message",
            self.config.deadline_s,
        )
        return self._fallback(session, query, kept, "timeout")

    def _keep(self, session: str, query: RecallQuery, response: Any, seq: int) -> None:
        with self._lock:
            conversation = self._conversation(session)
            if conversation.kept is None or seq >= conversation.kept.seq:  # a late answer never replaces a newer one
                conversation.kept = _Kept(query.key, query.terms, response, self._clock(), seq)
            if conversation.retry is not None and conversation.retry.key == query.key:
                conversation.retry = None

    def _mark_retry(self, session: str, query: RecallQuery) -> None:
        with self._lock:
            self._conversation(session).retry = query

    def _fallback(self, session: str, query: RecallQuery, kept: Optional[_Kept], outcome: str) -> Recalled:
        """The conversation's last recall, when it is recent and shares a term
        with this message. The floor then decides item by item."""
        if kept is None or self._clock() - kept.at > CACHE_TTL_S or not query.terms:
            return Recalled(outcome=outcome)
        if not set(query.terms) & set(kept.terms):
            return Recalled(outcome=outcome)
        result = self._inject(session, query, kept.response, "stale")
        result.outcome = outcome
        return result

    def _inject(self, session: str, query: RecallQuery, response: Any, source: str) -> Recalled:
        items = select_items(response, query, floor=self.config.floor)
        with self._lock:
            conversation = self._conversation(session)
            fresh = [item for item in items if item.identity not in conversation.injected][: self.config.limit]
            text = render_items(fresh, self.config.max_chars)
            shown = [item for item in fresh if item.line in text]
            conversation.injected.update(item.identity for item in shown)
        return Recalled(text=text, count=len(shown), source=source if shown else "none", outcome="success")

    def after_turn(self, session: str) -> Optional[threading.Thread]:
        """Once a turn completes: retry a recall that failed, so the next
        message has something to fall back on. A healthy conversation makes no
        extra call. The retry runs on its own thread: Hermes's one background
        worker also carries capture and must not wait on a stalled server."""
        if not self.config.enabled:
            return None
        with self._lock:
            conversation = self._conversation(session)
            if conversation.retry is None or conversation.retrying:
                return None
            query, conversation.retry, conversation.retrying = conversation.retry, None, True
            self._seq += 1
            seq = self._seq
            candidates = self._candidates(conversation)

        def run() -> None:
            try:
                self._keep(session, query, self._fetch(query, candidates), seq)
            except Exception as exc:
                logger.debug("MindGraph background recall retry failed: %s", exc)
            finally:
                with self._lock:
                    self._conversation(session).retrying = False

        thread = self._spawn(run, name="mindgraph-recall-retry")
        thread.start()
        return thread

    def forget_injected(self, session: str) -> None:
        """Compression dropped earlier turns, and the items injected with them."""
        with self._lock:
            if session in self._conversations:
                self._conversations[session].injected.clear()

    def rewound(self, session: str) -> None:
        """/undo removed turns without saying how many: what they were shown,
        and which message came last, are no longer known."""
        with self._lock:
            conversation = self._conversations.get(session)
            if conversation is not None:
                conversation.injected.clear()
                conversation.last_message = ""
                conversation.kept = None

    def rebind(self, old: str, new: str) -> None:
        """A conversation continued under a new id keeps its recall state."""
        with self._lock:
            if old in self._conversations and new not in self._conversations:
                self._conversations[new] = self._conversations.pop(old)

    def drop(self, session: str) -> None:
        with self._lock:
            self._conversations.pop(session, None)
