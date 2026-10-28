"""Model-facing rendering of MindGraph read responses, ported from mindgraph-mcp's
render.ts.

Raw wire JSON costs several times its signal in tokens (one live ``retrieve
context`` call measured ~15k tokens for ~2k of signal). These renderers keep
labels, uids, epistemic tags, one short source quote and label-level
relationships, pack whole items under a hard character budget, and say what they
omitted. Node uids stay in the output because models chain follow-up calls by uid.

Wire shapes (verified against mindgraph-server): /retrieve text|semantic|hybrid|
preferences return ``[{node, score, legs?}]``; /traverse top_k_paths returns
``{paths: [{node_uids, labels, cost}]}``; context edges spell types
SCREAMING_SNAKE while traverse serializes PascalCase. Machine-parsed surfaces
(plan, sync, code) are never rendered, and ``format: "json"`` is the escape hatch.

Every renderer returns ``None`` for a shape it does not recognize so the caller
falls back to raw JSON.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

LABEL_MAX = 200
SUMMARY_MAX = 400
QUOTE_MAX = 180
ARTICLE_MAX = 6_000
# A full ingestion chunk is 400-800 words (~5,200 chars); the clip must not defeat
# include_chunks' purpose (verbatim quotes, citations).
CHUNK_MAX = 6_000
RELATIONSHIP_MAX = 40
RENDER_CHAR_BUDGET = 24_000
MIN_RENDER_CHAR_BUDGET = 512
BOUNDED_MARKER_RESERVE = 220
JOBS_RENDER_MAX = 20

# Curation-inbox data has its own surface (merge_candidates); rendering it as
# knowledge confused models with reviewer metadata. Match both wire spellings.
CURATION_EDGE_TYPES = frozenset({"POSSIBLE_DUPLICATE", "PossibleDuplicate"})
# Infra nodes render through their own sections, not as graph knowledge.
INFRA_NODE_TYPES = frozenset({"Chunk", "Document", "Article"})

Rec = dict[str, Any]


@dataclass
class _Section:
    """A heading plus independent items, packed item-wise so one oversized section
    can never blank the output."""

    heading: str
    items: list[str] = field(default_factory=list)


@dataclass
class _State:
    bounded: bool = False
    omitted: int = 0


def _obj(value: Any) -> Optional[Rec]:
    return value if isinstance(value, dict) else None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def js(value: Any) -> str:
    """JavaScript ``String(value)``, so rendered text matches the MCP byte for byte
    where it matters (``confidence 1``, not ``confidence 1.0``)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    if isinstance(value, list):
        return ",".join("" if item is None else js(item) for item in value)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def _round2(value: float) -> float:
    # JS Math.round rounds half up; Python's round() is banker's rounding.
    return math.floor(value * 100 + 0.5) / 100


def _edge_type_name(value: Any) -> Optional[str]:
    """Serde externally tags user-defined variants as ``{Custom: "NAME"}``; treat
    that and the plain string as the same relation."""
    return _str(value) or _str((_obj(value) or {}).get("Custom"))


def render_budget(requested: Optional[float] = None) -> int:
    if _num(requested) is None:
        return RENDER_CHAR_BUDGET
    return min(RENDER_CHAR_BUDGET, max(MIN_RENDER_CHAR_BUDGET, math.floor(requested)))


def _clip(value: Any, limit: int, state: _State) -> Optional[str]:
    text = _str(value)
    if not text:
        return None
    if len(text) <= limit:
        return text
    state.bounded = True
    return f"{text[: limit - 1]}…"


def _is_node_shaped(value: Any) -> bool:
    node = _obj(value)
    # node_type may be externally tagged ({"Custom": "Customer"}) on serde surfaces.
    return bool(
        node
        and _str(node.get("uid"))
        and (_str(node.get("label")) or _str(node.get("node_type")) or _obj(node.get("node_type")))
    )


def node_display_type(node: Rec) -> str:
    """Display type across both wire families: retrieve-context hand-projects a
    plain string with top-level fields, while serde surfaces (ontology) emit a
    tagged node_type and ``_type``-tagged props with the payload under ``data``."""
    props = _obj(node.get("props")) or {}
    plain = _str(node.get("node_type"))
    # A literal "Custom" is the container, not the domain type.
    return (
        (plain if plain and plain != "Custom" else None)
        or _str((_obj(node.get("node_type")) or {}).get("Custom"))
        or _str(props.get("object_type"))
        or _str(props.get("type_name"))
        or _str((_obj(props.get("data")) or {}).get("domain_type"))
        or plain
        or "Node"
    )


def _node_fields(node: Rec) -> Optional[Rec]:
    props = _obj(node.get("props")) or {}
    return _obj(props.get("fields")) or _obj((_obj(props.get("data")) or {}).get("fields"))


def _unwrap_search_result(value: Any) -> Optional[Rec]:
    """/retrieve wraps as ``{node, score}``, /ontology/objects/search as
    ``{object, score}``, structured rows as ``{object, related?}``; unwrap to the
    node, carrying the score when present."""
    if _is_node_shaped(value):
        return value
    wrapper = _obj(value)
    if not wrapper:
        return None
    inner = _obj(wrapper.get("node")) or _obj(wrapper.get("object"))
    if inner and _is_node_shaped(inner):
        score = _num(wrapper.get("score"))
        return {**inner, "retrieval_score": score} if score is not None else inner
    return None


def status_tag(node: Rec) -> str:
    """Epistemics the raw JSON buries; without these a model states refuted or
    superseded knowledge as current."""
    tags: list[str] = []
    if node.get("superseded") is True:
        tags.append(f"SUPERSEDED by {_str(node.get('superseded_by'))}" if node.get("superseded_by") else "SUPERSEDED")
    truth = _str(node.get("truth_status")) or _str((_obj(node.get("props")) or {}).get("truth_status"))
    if truth and truth != "accepted":
        tags.append(f"truth: {truth}")
    if node.get("currently_valid") is False:
        tags.append("OUTSIDE ITS VALIDITY WINDOW")
    if node.get("valid_at_time") is False:
        tags.append("NOT VALID AT THE REQUESTED TIME")
    return f" [{'; '.join(tags)}]" if tags else ""


def _first_quote(node: Rec, state: _State) -> Optional[str]:
    for raw in _list(node.get("source_chunks")):
        chunk = _obj(raw) or {}
        quote = _str(chunk.get("quote")) or _str((_obj(chunk.get("anchor")) or {}).get("exact"))
        if quote:
            return _clip(quote, QUOTE_MAX, state)
    return None


def _source_tag(node: Rec) -> Optional[str]:
    docs = _list(node.get("source_documents"))
    title = _str((_obj(docs[0]) or {}).get("title")) if docs else None
    if not title:
        return None
    extra = f" (+{len(docs) - 1} more)" if len(docs) > 1 else ""
    return f"from: {title}{extra}"


def _layer7_fields(node: Rec, state: _State) -> Optional[str]:
    fields = _node_fields(node)
    if not fields:
        return None
    pairs = [
        f"{key}: {', '.join('' if v is None else js(v) for v in value) if isinstance(value, list) else js(value)}"
        for key, value in fields.items()
        if value is not None and value != ""
    ]
    return _clip("; ".join(pairs), SUMMARY_MAX, state) if pairs else None


def _node_summary_text(node: Rec, state: _State) -> Optional[str]:
    props = _obj(node.get("props")) or {}
    return (
        _clip(node.get("summary"), SUMMARY_MAX, state)
        or _clip(props.get("content"), SUMMARY_MAX, state)
        or _clip(props.get("description"), SUMMARY_MAX, state)
        or _clip(props.get("definition"), SUMMARY_MAX, state)
    )


def _node_lines(node: Rec, state: _State) -> str:
    label = _clip(node.get("label"), LABEL_MAX, state) or "(unlabeled)"
    confidence = _num(node.get("confidence"))
    score = _num(node.get("retrieval_score"))
    parenthetical = ", ".join(
        part
        for part in (
            node_display_type(node),
            f"confidence {js(confidence)}" if confidence is not None else None,
            f"score {js(_round2(score))}" if score is not None else None,
        )
        if part
    )
    head = f"- **{label}** [{_str(node.get('uid')) or '?'}] ({parenthetical}){status_tag(node)}"
    summary = _node_summary_text(node, state)
    lines = [f"{head}: {summary}" if summary and summary != label else head]
    fields = _layer7_fields(node, state)
    if fields:
        lines.append(f"  - fields: {fields}")
    quote = _first_quote(node, state)
    if quote:
        lines.append(f'  - source quote: "{quote}"')
    source = _source_tag(node)
    if source:
        lines.append(f"  - {source}")
    believers = _list(node.get("believed_by"))
    if believers:
        rendered = []
        for raw in believers[:3]:
            believer = _obj(raw) or {}
            conf = _num(believer.get("confidence"))
            rendered.append(f"{_str(believer.get('agent_label')) or '?'}{f' ({js(conf)})' if conf is not None else ''}")
        lines.append(f"  - believed by: {', '.join(rendered)}")
    return "\n".join(lines)


def _grouped_node_sections(nodes: list[Rec], state: _State, heading_prefix: str = "") -> list[_Section]:
    groups: dict[str, list[Rec]] = {}
    for node in nodes:
        groups.setdefault(node_display_type(node), []).append(node)
    return [
        _Section(f"{heading_prefix if index == 0 else ''}### {type_name}", [_node_lines(n, state) for n in group])
        for index, (type_name, group) in enumerate(groups.items())
    ]


def _relationship_items(
    edges: list[Any], label_by_uid: dict[str, str], state: _State, *, fallback_to_uid: bool = False
) -> list[str]:
    lines: list[str] = []
    for raw in edges:
        edge = _obj(raw)
        if not edge:
            continue
        type_name = _edge_type_name(edge.get("edge_type")) or "?"
        source, target = _str(edge.get("from_uid")), _str(edge.get("to_uid"))
        if type_name in CURATION_EDGE_TYPES:
            continue
        if not source or not target or source == target:  # self-loops are data noise
            continue
        # Ontology surfaces reference endpoints outside the object list; fall back
        # to the uid there rather than hiding a real relation.
        from_label = label_by_uid.get(source) or (f"[{source}]" if fallback_to_uid else None)
        to_label = label_by_uid.get(target) or (f"[{target}]" if fallback_to_uid else None)
        if not from_label or not to_label:
            continue
        lines.append(f"- {from_label} —{type_name}→ {to_label}")
    if len(lines) > RELATIONSHIP_MAX:
        state.bounded = True
        extra = len(lines) - RELATIONSHIP_MAX
        state.omitted += extra
        return [*lines[:RELATIONSHIP_MAX], f"- (+{extra} more relationships)"]
    return lines


def _assemble(header: str, sections: list[_Section], state: _State, max_chars: Optional[float] = None) -> str:
    """Pack sections item-wise under the budget: whole items or none, the rest
    counted; later sections still get a chance after an oversized one."""
    budget = render_budget(max_chars)
    # Reserve room for a truthful truncation marker so the hard bound holds even
    # when the last accepted item ends exactly at the cap.
    packing_budget = max(len(header), budget - BOUNDED_MARKER_RESERVE)
    lines = [header]
    used = len(header)
    for section in sections:
        if not section.items and not section.heading:
            continue
        heading_cost = len(section.heading) + 2
        if used + heading_cost > packing_budget:
            state.bounded = True
            state.omitted += max(1, len(section.items))
            continue
        section_used = 0
        kept: list[str] = []
        dropped = 0
        for item in section.items:
            if used + heading_cost + section_used + len(item) + 1 > packing_budget:
                dropped += 1
                continue
            kept.append(item)
            section_used += len(item) + 1
        if not kept and section.items:
            state.bounded = True
            state.omitted += dropped
            continue
        if dropped:
            state.bounded = True
            state.omitted += dropped
            marker = f"(+{dropped} more not shown)"
            if used + heading_cost + section_used + len(marker) + 1 <= packing_budget:
                kept.append(marker)
                section_used += len(marker) + 1
        if not section.items:
            lines.append(section.heading)
        elif section.heading:
            lines.append(section.heading + "\n" + "\n".join(kept))
        else:
            lines.append("\n".join(kept))
        used += heading_cost + section_used
    if state.bounded:
        lines.append(
            f"…[rendered context bounded to {budget} chars; {state.omitted} item(s) omitted — fetch full node "
            'content by uid, narrow the query, raise max_output_chars, or pass format: "json" for the raw response]'
        )
    return "\n\n".join(lines)[:budget]


def _policy_sections(payload: Rec, state: _State) -> list[_Section]:
    policies = [p for p in map(_obj, _list(payload.get("applicable_policies"))) if p]
    if not policies:
        return []
    items = []
    for policy in policies:
        rules = policy.get("prose_rules")
        # prose_rules is Vec<String> on the wire.
        if isinstance(rules, list):
            rules = "; ".join(js(rule) for rule in rules)
        items.append(
            f"- {_str(policy.get('name')) or '(unnamed policy)'}: "
            f"{_clip(rules, SUMMARY_MAX, state) or '(structured rules apply)'}"
        )
    return [_Section("## Applicable policies", items)]


def _hidden_sections(payload: Rec) -> list[_Section]:
    hidden = payload.get("hidden_item_count")
    if hidden is None:
        return []
    return [_Section(f"Note: {js(hidden)} item(s) were hidden by access scoping.")]


def render_context(response: Any, max_chars: Optional[float] = None) -> Optional[str]:
    """Render a /retrieve/context response."""
    payload = _obj(response)
    if payload is None:
        return None
    graph = _obj(payload.get("graph")) or {}
    shaped = [n for n in _list(graph.get("nodes")) if _is_node_shaped(n)]
    nodes = [n for n in shaped if (_str(n.get("node_type")) or "") not in INFRA_NODE_TYPES]
    infra_only = len(shaped) - len(nodes)
    articles = _list(payload.get("articles"))
    chunks = _list(payload.get("chunks"))
    state = _State()
    sections: list[_Section] = []
    if articles:
        sections.append(
            _Section(
                "## Knowledge articles",
                [
                    f"### {_str(a.get('label')) or '(untitled)'} [{_str(a.get('uid')) or '?'}]\n"
                    f"{_clip(a.get('content'), ARTICLE_MAX, state) or ''}"
                    for a in map(_obj, articles)
                    if a
                ],
            )
        )
    if nodes:
        sections.extend(_grouped_node_sections(nodes, state, "## Knowledge graph\n\n"))
        label_by_uid = {n["uid"]: _str(n.get("label")) or "?" for n in nodes}
        relationships = _relationship_items(_list(graph.get("edges")), label_by_uid, state)
        if relationships:
            sections.append(_Section("## Relationships", relationships))
    elif infra_only > 0:
        sections.append(
            _Section(
                f"Note: {infra_only} document/chunk node(s) matched — use action \"document_index\" "
                "or include_chunks for their content."
            )
        )
    if chunks:
        sections.append(
            _Section(
                "## Source excerpts",
                [
                    f"- [{_str(c.get('chunk_uid')) or '?'}] from \"{_str(c.get('document_title')) or 'unknown document'}\": "
                    f"\"{_clip(c.get('content'), CHUNK_MAX, state) or ''}\""
                    for c in map(_obj, chunks)
                    if c
                ],
            )
        )
    sections.extend(_policy_sections(payload, state))
    sections.extend(_hidden_sections(payload))
    if not sections:
        return "No results found for this search."
    if not nodes and not articles and not chunks:
        # Policies, hidden counts and infra notes still render: an access-filtered
        # result must not read as "nothing exists".
        return _assemble("# Retrieved context\n\nNo graph results matched this search.", sections, state, max_chars)
    return _assemble("# Retrieved context", sections, state, max_chars)


def _resume_entry(raw: Any, state: _State, fallback_type: str) -> Optional[str]:
    wrapper = _obj(raw)
    if wrapper is None:
        return None
    value = _obj(wrapper.get("node")) or wrapper
    if _is_node_shaped(value):
        return _node_lines(value, state)
    uid = _str(value.get("uid"))
    props = _obj(value.get("props")) or {}
    label = (
        _clip(value.get("label"), LABEL_MAX, state)
        or _clip(value.get("name"), LABEL_MAX, state)
        or _clip(value.get("title"), LABEL_MAX, state)
        or _clip(value.get("action"), LABEL_MAX, state)
        or fallback_type
    )
    status = _str(value.get("status")) or _str(props.get("status"))
    summary = (
        _clip(value.get("summary"), SUMMARY_MAX, state)
        or _clip(value.get("description"), SUMMARY_MAX, state)
        or _clip(value.get("content"), SUMMARY_MAX, state)
        or _clip(value.get("outcome_summary"), SUMMARY_MAX, state)
        or _clip(props.get("summary"), SUMMARY_MAX, state)
    )
    details = [
        d
        for d in (
            f"status {status}" if status else None,
            f"path {_str(value.get('path'))}" if _str(value.get("path")) else None,
            f"symbol {_str(value.get('symbol'))}" if _str(value.get("symbol")) else None,
        )
        if d
    ]
    detail_text = f" ({', '.join(details)})" if details else ""
    head = f"- **{label}**{f' [{uid}]' if uid else ''}{detail_text}"
    return f"{head}: {summary}" if summary and summary != label else head


def _resume_section(heading: str, values: list[Any], state: _State, fallback_type: str) -> Optional[_Section]:
    items = [entry for entry in (_resume_entry(v, state, fallback_type) for v in values) if entry]
    return _Section(heading, items) if items else None


def render_resume_context(response: Any, max_chars: Optional[float] = None) -> Optional[str]:
    """Render the task-first ``mindgraph_plan(resume_work)`` response, preserving its
    task, lease, blocker and execution order instead of a recency search."""
    payload = _obj(response)
    if payload is None:
        return None
    state = _State()
    if not payload.get("task") and _str(payload.get("status")) == "no_eligible_work":
        scoped_out = len(_list(payload.get("scoped_out_tasks")))
        note = f" {scoped_out} task(s) exist outside the requested scope." if scoped_out > 0 else ""
        return _assemble(
            "# Resume context",
            [_Section(f"No eligible work was found in the requested scope.{note}")],
            state,
            max_chars,
        )
    knowledge = _obj(payload.get("knowledge")) or {}
    candidates = [
        _resume_section("## Current task", [payload.get("task")], state, "Task"),
        _resume_section(
            "## Goal and project", [v for v in (payload.get("goal"), payload.get("project")) if v], state, "Scope"
        ),
        _resume_section("## Plan", [payload.get("plan")], state, "Plan"),
        _resume_section("## Next steps", _list(payload.get("next_steps")), state, "Next step"),
        _resume_section("## Blockers", _list(payload.get("blockers")), state, "Blocker"),
        _resume_section(
            "## Relevant lessons and risks",
            [*_list(knowledge.get("lessons")), *_list(knowledge.get("risks"))],
            state,
            "Knowledge",
        ),
        _resume_section(
            "## Active execution", [v for v in (payload.get("active_execution"),) if v], state, "Execution"
        ),
        _resume_section("## Recent executions", _list(payload.get("recent_executions")), state, "Execution"),
        _resume_section("## Code targets", _list(payload.get("code_targets")), state, "Code target"),
        _resume_section("## Lease", [v for v in (payload.get("lease"),) if v], state, "Lease"),
    ]
    sections = [s for s in candidates if s]
    warning = _clip(payload.get("warning"), SUMMARY_MAX, state)
    if warning:
        sections.append(_Section("## Warning", [f"- {warning}"]))
    selection_reason = _clip(payload.get("selection_reason"), SUMMARY_MAX, state)
    if selection_reason:
        sections.append(_Section("## Selection", [f"- {selection_reason}"]))
    if not sections:
        return None
    return _assemble("# Resume context", sections, state, max_chars)


def render_node_list(
    response: Any, title: str, limit: Optional[int] = None, max_chars: Optional[float] = None
) -> Optional[str]:
    """Render any response that is (or contains) a list of nodes: bare GraphNode
    arrays and SearchResult ``{node, score}`` arrays alike."""
    candidates: list[Any] = []
    if isinstance(response, list):
        candidates = response
    else:
        payload = _obj(response)
        if payload is None:
            return None
        for key in ("nodes", "results", "items", "goals", "questions", "claims", "preferences", "documents"):
            candidate = payload.get(key)
            if isinstance(candidate, list) and any(_unwrap_search_result(e) for e in candidate):
                candidates = candidate
                break
    nodes = [n for n in map(_unwrap_search_result, candidates) if n]
    if not nodes:
        return None
    total = len(nodes)
    state = _State()
    # The server ignores limit for several unscoped structured queries.
    if limit is not None and limit > 0 and len(nodes) > limit:
        state.omitted += len(nodes) - limit
        nodes = nodes[:limit]
        state.bounded = True
    sections = _grouped_node_sections(nodes, state)
    shown = len(nodes)
    count = str(total) if shown == total else f"{shown} of {total}"
    return _assemble(f"# {title} ({count})", sections, state, max_chars)


def render_traversal(response: Any, max_chars: Optional[float] = None) -> Optional[str]:
    """Render a traversal response: steps, paths, and nodes with relationships."""
    direct_steps = response if isinstance(response, list) else None
    payload = _obj(response)
    if payload is None and direct_steps is None:
        return None
    body = payload or {}
    container = _obj(body.get("graph")) or body
    nodes = [n for n in _list(container.get("nodes")) if _is_node_shaped(n)]
    paths = _list(body.get("paths"))
    has_steps = direct_steps is not None or "steps" in body
    raw_steps = direct_steps if direct_steps is not None else _list(body.get("steps"))
    if not nodes and not paths and not has_steps:
        return None
    state = _State()
    sections: list[_Section] = []
    label_by_uid = {n["uid"]: _str(n.get("label")) or "?" for n in nodes}
    if paths:
        items = []
        for index, path in enumerate(p for p in map(_obj, paths) if p):
            uids = [js(u) for u in path["node_uids"]] if isinstance(path.get("node_uids"), list) else []
            if isinstance(path.get("labels"), list):
                labels = [js(label) for label in path["labels"]]
            elif isinstance(path.get("nodes"), list):
                labels = []
                for hop in path["nodes"]:
                    hop_node = _obj(hop) or {}
                    labels.append(
                        _str(hop_node.get("label"))
                        or label_by_uid.get(_str(hop_node.get("uid")) or "")
                        or _str(hop)
                        or "?"
                    )
            else:
                labels = []
            route = " → ".join(labels) if labels else (" → ".join(uids) or "(path)")
            cost = _num(path.get("cost"))
            if cost is None:
                cost = _num(path.get("path_cost"))
            confidence = _num(path.get("path_confidence"))
            meta = [
                m
                for m in (
                    f"cost {js(cost)}" if cost is not None else None,
                    f"confidence {js(confidence)}" if confidence is not None else None,
                )
                if m
            ]
            meta_text = f" ({', '.join(meta)})" if meta else ""
            head = f"{index + 1}. {route}{meta_text}"
            # uids ride along when labels rendered; follow-up calls need them.
            items.append(f"{head}\n   uids: {' → '.join(uids)}" if labels and uids else head)
        sections.append(_Section("## Paths", items))
    if has_steps:
        step_items = []
        for step in (s for s in map(_obj, raw_steps) if s):
            depth = _num(step.get("depth"))
            uid = _str(step.get("node_uid")) or _str(step.get("uid")) or _str(step.get("edge_to_uid")) or "?"
            parent = _str(step.get("parent_uid")) or _str(step.get("edge_from_uid"))
            label = _str(step.get("label")) or "(unlabeled)"
            relation = _edge_type_name(step.get("edge_type"))
            role = _str(step.get("traversal_role"))
            type_name = _str(step.get("node_type")) or _str((_obj(step.get("node_type")) or {}).get("Custom"))
            cost = _num(step.get("path_cost"))
            confidence = _num(step.get("path_confidence"))
            prefix = " ".join(
                p
                for p in (
                    f"depth {js(depth)}" if depth is not None else None,
                    role,
                    f"—{relation}→" if relation else None,
                )
                if p
            )
            meta = ", ".join(
                m
                for m in (
                    type_name,
                    f"parent {parent}" if parent else None,
                    f"cost {js(cost)}" if cost is not None else None,
                    f"confidence {js(confidence)}" if confidence is not None else None,
                )
                if m
            )
            step_items.append(f"- {f'{prefix}: ' if prefix else ''}**{label}** [{uid}]{f' ({meta})' if meta else ''}")
        if step_items:
            sections.append(_Section("## Traversal steps", step_items))
        else:
            start = _str(body.get("start_uid")) or "?"
            end = _str(body.get("end_uid"))
            mode = _str(body.get("mode"))
            sections.append(
                _Section(
                    f"No path found from [{start}] to [{end}]."
                    if mode == "path" and end
                    else f"No traversal steps returned from [{start}]."
                )
            )
    if nodes:
        sections.extend(_grouped_node_sections(nodes, state, "## Nodes\n\n"))
        relationships = _relationship_items(_list(container.get("edges")), label_by_uid, state)
        if relationships:
            sections.append(_Section("## Relationships", relationships))
    mode = _str(body.get("mode"))
    return _assemble(f"# Graph traversal{f' ({mode})' if mode else ''}", sections, state, max_chars)


# Ontology (Layer 7). ``objects`` are full GraphNodes; cognitive_context maps a
# category to NeighborNode[]; provenance distinguishes ``anchor`` (a located
# quotation) from ``chunk_head`` (context that must not be presented as a quote,
# server contract C10).


def _neighbor_line(value: Any) -> Optional[str]:
    node = _obj(value)
    if node is None:
        return None
    label = _str(node.get("label")) or "(unlabeled)"
    uid = _str(node.get("uid"))
    type_name = _str(node.get("node_type"))
    return f"- {label}{f' [{uid}]' if uid else ''}{f' ({type_name})' if type_name else ''}"


def render_ontology_answer(response: Any) -> Optional[str]:
    """Render an /ontology/query (or object-context-shaped) response."""
    payload = _obj(response)
    if payload is None:
        return None
    if isinstance(payload.get("objects"), list):
        objects = [o for o in payload["objects"] if _is_node_shaped(o)]
    elif _is_node_shaped(payload.get("object")):
        objects = [payload["object"]]
    else:
        objects = []
    cognitive = _obj(payload.get("cognitive_context"))
    provenance = _list(payload.get("provenance"))
    has_query_signature = isinstance(payload.get("objects"), list) or _obj(payload.get("confidence")) is not None
    cognitive_empty = not cognitive or all(not isinstance(v, list) or not v for v in cognitive.values())
    if not objects and cognitive_empty and not provenance:
        # A recognized-but-empty result renders honestly; an unknown shape is raw.
        return "No matching domain objects." if has_query_signature else None
    state = _State()
    sections: list[_Section] = []
    if objects:
        sections.extend(_grouped_node_sections(objects, state))
    label_by_uid = {o["uid"]: _str(o.get("label")) or "?" for o in objects}
    neighbors = [*_list((_obj(payload.get("graph")) or {}).get("nodes"))]
    # Cognitive neighbors carry labels too; object_context has no graph key.
    for raw_nodes in (cognitive or {}).values():
        neighbors.extend(_list(raw_nodes))
    for raw in neighbors:
        node = _obj(raw) or {}
        uid = _str(node.get("uid"))
        if uid and uid not in label_by_uid:
            label_by_uid[uid] = _str(node.get("label")) or "?"
    relation_lines = _relationship_items(_list(payload.get("relations")), label_by_uid, state, fallback_to_uid=True)
    if relation_lines:
        sections.append(_Section("## Relations", relation_lines))
    for category, raw_nodes in (cognitive or {}).items():
        if not isinstance(raw_nodes, list) or not raw_nodes:
            continue
        items = [line for line in map(_neighbor_line, raw_nodes) if line]
        if items:
            sections.append(_Section(f"### Cognitive context — {category}", items))
    if provenance:
        items = []
        for entry in (e for e in map(_obj, provenance) if e):
            span = _clip(entry.get("text_span"), QUOTE_MAX, state) or ""
            by = _str(entry.get("ingested_by_name"))
            suffix = f"{f' (ingested by {by})' if by else ''} [source {_str(entry.get('source_uid')) or '?'}]"
            # C10: chunk_head spans are context, never quotations.
            items.append(f'- "{span}"{suffix}' if _str(entry.get("span_kind")) == "anchor" else f"- context: {span}{suffix}")
        sections.append(_Section("## Sources", items))
    confidence = _num((_obj(payload.get("confidence")) or {}).get("overall"))
    notes = []
    if confidence is not None:
        notes.append(f"overall confidence {js(confidence)}")
    if payload.get("has_more") is True:
        notes.append("more results exist (has_more)")
    if payload.get("seed_cap_hit") is True:
        notes.append("seed cap hit — narrow the query for a complete set")
    if notes:
        sections.append(_Section(f"Note: {'; '.join(notes)}."))
    plural = "" if len(objects) == 1 else "s"
    return _assemble(f"# Ontology results ({len(objects)} object{plural})", sections, state)


def render_object_list(response: Any, title: str) -> Optional[str]:
    """Render paged domain-object lists: search, objects and related responses."""
    payload = _obj(response)
    if payload is None:
        return None
    # ``rows`` counts only when its entries unwrap to nodes; tabular select rows are
    # not an object list and fall back to raw.
    if isinstance(payload.get("items"), list):
        raw_items: Optional[list[Any]] = payload["items"]
    elif isinstance(payload.get("rows"), list) and any(_unwrap_search_result(r) for r in payload["rows"]):
        raw_items = payload["rows"]
    else:
        raw_items = None
    items = [n for n in map(_unwrap_search_result, raw_items or []) if n]
    if not items:
        return f"# {title} (0 results)" if raw_items is not None else None
    state = _State()
    sections = _grouped_node_sections(items, state)
    total = _num(payload.get("total_count"))
    truncations = [r for r in _list(payload.get("truncation_reasons")) if isinstance(r, str)]
    notes = []
    if payload.get("has_more") is True:
        notes.append("more results exist")
    if truncations:
        notes.append(f"truncated: {', '.join(truncations)}")
    if notes:
        sections.append(_Section(f"Note: {'; '.join(notes)}."))
    count = f"{len(items)} of {js(total)}" if total is not None and total != len(items) else str(len(items))
    return _assemble(f"# {title} ({count})", sections, state)


def render_jobs(response: Any) -> Optional[str]:
    """Render the ingestion jobs list, newest first, bounded."""
    jobs = response if isinstance(response, list) else (_obj(response) or {}).get("jobs")
    if not isinstance(jobs, list):
        return None
    if not jobs:
        return "No ingestion jobs."
    state = _State()
    ordered = sorted((j for j in map(_obj, jobs) if j), key=lambda j: -(_num(j.get("created_at")) or 0))
    shown = ordered[:JOBS_RENDER_MAX]
    if len(shown) < len(ordered):
        state.bounded = True
    items = []
    for job in shown:
        progress = _obj(job.get("progress")) or {}
        # Preserve the server's terminal reason; legacy text alone never implies an
        # engine code or retry permission.
        failure = _obj(job.get("error_details")) or {}
        message = _str(failure.get("message")) or _str(job.get("error"))
        done = _num(progress.get("processed_chunks"))
        total_chunks = _num(progress.get("total_chunks"))
        nodes_created = _num(progress.get("nodes_created"))
        queue_position = _num(job.get("queue_position"))
        failure_status = _num(failure.get("status"))
        bits = [
            b
            for b in (
                _str(job.get("status")) or "?",
                f"{js(done)}/{js(total_chunks)} chunks" if done is not None and total_chunks is not None else None,
                f"{js(nodes_created)} nodes" if nodes_created is not None else None,
                f"queue #{js(queue_position)}" if queue_position is not None else None,
                f"error: {_clip(message, 160, state)}" if message else None,
                f"code: {_clip(failure.get('code'), 80, state)}" if _str(failure.get("code")) else None,
                f"status: {js(failure_status)}" if failure_status is not None else None,
                f"retriable: {js(failure['retriable'])}" if isinstance(failure.get("retriable"), bool) else None,
            )
            if b
        ]
        items.append(
            f"- [{_str(job.get('id')) or '?'}] {_clip(job.get('title'), 120, state) or '(untitled)'} — {', '.join(bits)}"
        )
    count = f"{len(shown)}{f' of {len(ordered)}' if len(shown) < len(ordered) else ''}"
    return _assemble(f"# Ingestion jobs ({count})", [_Section("", items)], state)


def render_signals(response: Any) -> Optional[str]:
    """Render /synthesis/signals: named arrays of typed signal items."""
    payload = _obj(response)
    if payload is None:
        return None
    state = _State()
    sections: list[_Section] = []
    for key, value in payload.items():
        if not isinstance(value, list) or not value:
            continue
        items = []
        for item in (i for i in map(_obj, value) if i):
            from_label, to_label = _str(item.get("from_label")), _str(item.get("to_label"))
            any_label_key = next((k for k in item if k.endswith("_label") and _str(item[k])), None)
            label = (
                _str(item.get("label"))
                or _str(item.get("title"))
                or _str(item.get("name"))
                or (f"{from_label} ↔ {to_label}" if from_label and to_label else None)
                or (_str(item[any_label_key]) if any_label_key else None)
                or _str(item.get("uid"))
                or _str(item.get("target_uid"))
                or "(item)"
            )
            uid = _str(item.get("uid")) or _str(item.get("target_uid"))
            numbers = [f"{k} {js(_round2(v))}" for k, v in item.items() if _num(v) is not None][:4]
            lists = [f"{k}: {len(v)}" for k, v in item.items() if isinstance(v, list) and v][:2]
            meta = ", ".join([*numbers, *lists])
            items.append(
                f"- {_clip(label, 160, state)}{f' [{uid}]' if uid and uid != label else ''}{f' ({meta})' if meta else ''}"
            )
        if items:
            sections.append(_Section(f"## {key.replace('_', ' ')}", items))
    if not sections:
        return None
    return _assemble("# Synthesis signals", sections, state)
