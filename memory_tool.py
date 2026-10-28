"""``mindgraph_memory``: the read-only orient surface, ported from mindgraph-mcp's
memory-tool.ts.

``status`` reports what this integration actually does; ``context`` returns
bounded topic context (``/retrieve/context``) or authoritative task-first work
state (``resume_work``) as rendered text plus a compact structured envelope.
The tool never writes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Optional

from .render import render_context, render_resume_context
from .results import err, ok, text, tool_error
from .runtime import Runtime

RESULT_SCHEMA_VERSION = "mindgraph.memory.result.v1"
DEFAULT_OUTPUT_CHARS = 8_000
MIN_OUTPUT_CHARS = 512
MAX_OUTPUT_CHARS = 24_000
HIDDEN_CONTEXT_NODE_TYPES = frozenset({"Chunk", "Document", "Article"})
HIDDEN_CONTEXT_EDGE_TYPES = frozenset({"POSSIBLE_DUPLICATE", "PossibleDuplicate"})
_TIMESTAMP_KEYS = ("updated_at", "created_at", "completed_at", "started_at", "observed_at")

Rec = dict[str, Any]


@dataclass
class MemoryRuntimeConfig:
    server_version: Optional[str] = None
    base_url: Optional[str] = None
    profile: str = "general"
    harness: str = "hermes"
    org_id: Optional[str] = None
    agent_id: Optional[str] = None
    # What the provider really does, so ``status`` never overclaims: Hermes calls
    # the provider's sync_turn/on_session_end (capture) and prefetch (delivery).
    automatic_capture: bool = False
    automatic_delivery: bool = False


def _obj(value: Any) -> Optional[Rec]:
    return value if isinstance(value, dict) else None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _stable_json(value: Any) -> str:
    """Key-sorted JSON that drops ``None`` members (memory-tool.ts ``stableJson``)."""
    if isinstance(value, list):
        return "[" + ",".join(_stable_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{_stable_json(value[key])}"
            for key in sorted(value)
            if value[key] is not None
        ) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _output_budget(value: Any) -> int:
    if _number(value) is None:
        return DEFAULT_OUTPUT_CHARS
    return min(MAX_OUTPUT_CHARS, max(MIN_OUTPUT_CHARS, math.floor(value)))


def _defined(values: Rec) -> Rec:
    return {key: value for key, value in values.items() if value is not None}


def _strings(value: Any) -> Optional[list[str]]:
    return [str(item) for item in value] if isinstance(value, list) else None


def memory_status(config: MemoryRuntimeConfig) -> Rec:
    capture, delivery = config.automatic_capture, config.automatic_delivery
    degradation: list[Rec] = []
    if not capture:
        degradation.append(
            {
                "code": "automatic_capture_unavailable",
                "message": "This integration does not observe host lifecycle events; explicit typed write tools remain available.",
            }
        )
    degradation.append(
        {
            "code": "delivery_unverified",
            "message": (
                "The provider hands prefetched context to Hermes each turn but cannot verify that the model used it."
                if delivery
                else "A successful read does not prove that the host injected or used the returned context."
            ),
        }
    )
    degradation.append(
        {
            "code": "curator_disabled",
            "message": "Curator proposals and autonomous mutation are not enabled.",
        }
    )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "action": "status",
        # The cumulative M-profile claim needs per-application qualification; the
        # provider's automatic behavior is stated below instead of upgrading it.
        "profile": "M0",
        "server": _defined(
            {"name": "mindgraph-hermes", "version": config.server_version or "unknown", "base_url": config.base_url}
        ),
        "integration": {
            "adapter_state": "provider_lifecycle" if capture or delivery else "model_controlled",
            "harness": config.harness or "generic",
            "configured_tool_profile": config.profile or "general",
            "automatic_capture": capture,
            "automatic_delivery": delivery,
            "delivery_verification": "unsupported",
            "curator_mode": "disabled",
        },
        "scope": _defined({"org_id": config.org_id, "agent_id": config.agent_id}),
        "capabilities": {
            "status": True,
            "topic_context": True,
            "authoritative_resume_context": True,
            "bounded_rendering": True,
            "structured_content": True,
            "typed_explicit_writes": True,
            "lifecycle_event_ingest": capture,
            "automatic_context_injection": delivery,
            "curator_mutation": False,
        },
        "degradation": degradation,
    }


def _node_type(node: Rec) -> str:
    raw = node.get("node_type")
    if isinstance(raw, str):
        return raw
    return _text((_obj(raw) or {}).get("Custom")) or "Node"


def _compact_item(raw: Any, fallback_type: Optional[str] = None) -> Optional[Rec]:
    wrapper = _obj(raw)
    if wrapper is None:
        return None
    value = _obj(wrapper.get("node")) or _obj(wrapper.get("object")) or wrapper
    uid = _text(value.get("uid")) or _text(value.get("chunk_uid"))
    if not uid:
        return None
    depth = value.get("retrieval_depth")
    return _defined(
        {
            "uid": uid,
            "type": fallback_type or _node_type(value),
            "label": _text(value.get("label")) or _text(value.get("document_title")),
            "truth_status": _text(value.get("truth_status")) or _text((_obj(value.get("props")) or {}).get("truth_status")),
            "superseded": True if value.get("superseded") is True else None,
            "currently_valid": False if value.get("currently_valid") is False else None,
            "valid_at_time": False if value.get("valid_at_time") is False else None,
            "retrieval_origin": _text(value.get("retrieval_origin")),
            "retrieval_depth": depth if _number(depth) is not None else None,
        }
    )


def _topic_candidates(raw: Any) -> list[Rec]:
    payload = _obj(raw)
    if payload is None:
        return []
    graph = _obj(payload.get("graph")) or {}
    items = [i for i in (_compact_item(a, "Article") for a in _list(payload.get("articles"))) if i]
    labels: dict[str, str] = {}
    for node in _list(graph.get("nodes")):
        item = _compact_item(node)
        if not item or item.get("type") in HIDDEN_CONTEXT_NODE_TYPES:
            continue
        items.append(item)
        if item.get("label"):
            labels[item["uid"]] = item["label"]
    for raw_edge in _list(graph.get("edges")):
        edge = _obj(raw_edge) or {}
        from_uid, to_uid = _text(edge.get("from_uid")), _text(edge.get("to_uid"))
        edge_type = _text(edge.get("edge_type")) or _text((_obj(edge.get("edge_type")) or {}).get("Custom"))
        if (
            not from_uid
            or not to_uid
            or not edge_type
            or edge_type in HIDDEN_CONTEXT_EDGE_TYPES
            or from_uid not in labels
            or to_uid not in labels
        ):
            continue
        items.append(
            {
                "type": "Relationship",
                "from_uid": from_uid,
                "to_uid": to_uid,
                "edge_type": edge_type,
                "from_label": labels[from_uid],
                "to_label": labels[to_uid],
            }
        )
    items.extend(i for i in (_compact_item(c, "SourceExcerpt") for c in _list(payload.get("chunks"))) if i)
    return items


def _resume_candidates(raw: Any) -> list[Rec]:
    payload = _obj(raw)
    if payload is None:
        return []
    items: list[Rec] = []
    for key in ("task", "goal", "project", "plan", "active_execution", "lease"):
        item = _compact_item(payload.get(key), key)
        if item:
            items.append(item)
    for key in ("next_steps", "recent_executions", "blockers", "code_targets"):
        items.extend(i for i in (_compact_item(v, key.removesuffix("s")) for v in _list(payload.get(key))) if i)
    knowledge = _obj(payload.get("knowledge")) or {}
    for key in ("lessons", "risks"):
        items.extend(i for i in (_compact_item(v, key.removesuffix("s")) for v in _list(knowledge.get(key))) if i)
    return items


def _visible_items(candidates: list[Rec], rendered: str) -> list[Rec]:
    """Only items the rendered text actually shows count as returned."""
    seen: set[str] = set()
    visible: list[Rec] = []
    for item in candidates:
        uid = _text(item.get("uid"))
        if uid:
            if uid in seen or f"[{uid}]" not in rendered:
                continue
            seen.add(uid)
            visible.append(item)
        elif item.get("type") == "Relationship":
            source, target, edge_type = item.get("from_label"), item.get("to_label"), item.get("edge_type")
            if not source or not target or not edge_type:
                continue
            key = f"{item.get('from_uid')}:{edge_type}:{item.get('to_uid')}"
            if key in seen or f"{source} —{edge_type}→ {target}" not in rendered:
                continue
            seen.add(key)
            visible.append(item)
    return visible


def _parse_time(value: str) -> Optional[float]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _latest_timestamp(value: Any) -> Optional[str]:
    latest: Optional[str] = None
    latest_at = -math.inf

    def visit(current: Any) -> None:
        nonlocal latest, latest_at
        if isinstance(current, list):
            for item in current:
                visit(item)
            return
        if not isinstance(current, dict):
            return
        for key, item in current.items():
            if key in _TIMESTAMP_KEYS and isinstance(item, str):
                at = _parse_time(item)
                if at is not None and (latest is None or at > latest_at):
                    latest, latest_at = item, at
            visit(item)

    visit(value)
    return latest


def _context_warnings(raw: Any, rendered: str, available: int, returned: int) -> list[Rec]:
    warnings: list[Rec] = [
        {
            "code": "delivery_unverified",
            "message": "The MindGraph provider returned this context but cannot verify that the host injected or used it.",
        }
    ]
    serialized = json.dumps(raw, separators=(",", ":"), default=str)
    if available > returned or "item(s) omitted" in rendered:
        warnings.append(
            {
                "code": "context_bounded",
                "message": f"{max(0, available - returned)} structured item(s) were omitted from the rendered context.",
            }
        )
    if '"superseded":true' in serialized:
        warnings.append({"code": "superseded_items_present", "message": "Some retrieved items are superseded."})
    if re.search(r'"currently_valid":false|"valid_at_time":false', serialized):
        warnings.append(
            {
                "code": "validity_warning",
                "message": "Some retrieved items are outside their current or requested validity window.",
            }
        )
    payload = _obj(raw) or {}
    truncation = _obj(payload.get("truncation"))
    if payload.get("truncated") is True or (truncation and any(truncation.values())):
        warnings.append({"code": "source_truncated", "message": "The authoritative source reported truncated fields."})
    if _text(payload.get("warning")):
        warnings.append({"code": "source_warning", "message": payload["warning"]})
    return warnings


def handle_memory_tool(rt: Runtime, args: Rec, config: MemoryRuntimeConfig) -> str:
    try:
        return _handle(rt, args, config)
    except Exception as exc:
        return tool_error(exc)


def _handle(rt: Runtime, args: Rec, config: MemoryRuntimeConfig) -> str:
    action = _text(args.get("action"))
    agent_id = _text(args.get("agent_id")) or config.agent_id
    if action == "status":
        return ok(memory_status(replace(config, agent_id=agent_id)))
    if action != "context":
        return err("action must be 'status' or 'context'")

    mode = _text(args.get("mode")) or ("topic" if _text(args.get("query")) else None)
    if mode not in ("topic", "continuity", "resume"):
        return err("action='context' requires mode='topic', 'continuity', or 'resume'")
    budget = _output_budget(args.get("max_output_chars"))
    query = _text(args.get("query"))
    project_uid = _text(args.get("project_uid"))

    if mode == "topic":
        if not query:
            return err("mode='topic' requires a non-empty query of 1-3 discriminating keywords")
        limit = args.get("limit")
        limit = min(50, max(1, math.floor(limit))) if _number(limit) is not None else 8
        raw = rt.client.retrieve_context(
            query,
            **_defined(
                {
                    "project_uid": project_uid,
                    "node_limit": limit,
                    "node_types": _strings(args.get("node_types")),
                    "layer": _text(args.get("layer")),
                    "chunk_limit": limit if args.get("include_chunks") is True else 0,
                    "article_limit": limit if args.get("include_documents") is True else 0,
                    "valid_at": _text(args.get("valid_at")),
                    "include_graph": True,
                    "graph_expansion_limit": args["graph_expansion_limit"]
                    if _number(args.get("graph_expansion_limit")) is not None
                    else 3,
                    "graph_max_depth": args["graph_max_depth"] if _number(args.get("graph_max_depth")) is not None else 2,
                }
            ),
        )
        rendered = render_context(raw, budget) or "No results found for this search."
        strategy = "retrieve_context"
        candidates = _topic_candidates(raw)
    else:
        scope_uids = list(dict.fromkeys([*(_strings(args.get("scope_uids")) or []), *([project_uid] if project_uid else [])]))
        raw = rt.client.plan(
            **_defined(
                {
                    "action": "resume_work",
                    "task_uid": _text(args.get("task_uid")),
                    "session_uid": _text(args.get("session_uid")),
                    "scope_uids": scope_uids or None,
                    "limit": 1,
                    "agent_id": agent_id,
                }
            )
        )
        rendered = render_resume_context(raw, budget) or "No eligible work was found in the requested scope."
        strategy = "resume_work"
        candidates = _resume_candidates(raw)

    items = _visible_items(candidates, rendered)
    rendered_hash = _sha256(rendered)
    scope = _defined(
        {
            "org_id": config.org_id,
            "agent_id": agent_id,
            "harness": config.harness or "generic",
            "project_uid": project_uid,
            "task_uid": _text(args.get("task_uid")),
            "session_uid": _text(args.get("session_uid")),
            "scope_uids": _strings(args.get("scope_uids")),
        }
    )
    context_id = "ctx_" + _sha256(
        _stable_json(
            {"mode": mode, "scope": scope, "strategy": strategy, "query": query, "rendered_hash": rendered_hash}
        )
    )[:24]
    omitted = max(0, len(candidates) - len(items))
    structured = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "action": "context",
        "context_id": context_id,
        "mode": mode,
        "rendered_hash": rendered_hash,
        "retrieval_trace": _defined(
            {
                "strategy": strategy,
                "query": query,
                "project_uid": project_uid,
                "task_uid": _text(args.get("task_uid")),
                "session_uid": _text(args.get("session_uid")),
                "node_types": _strings(args.get("node_types")),
                "graph_expansion_limit": args.get("graph_expansion_limit", 3) if mode == "topic" else None,
                "graph_max_depth": args.get("graph_max_depth", 2) if mode == "topic" else None,
                "available_items": len(candidates),
                "returned_items": len(items),
                "omitted_items": omitted,
            }
        ),
        "budget": {
            "unit": "characters",
            "requested_chars": budget,
            "used_chars": len(rendered),
            "available_items": len(candidates),
            "returned_items": len(items),
            "omitted_items": omitted,
            "bounded": len(candidates) > len(items) or "item(s) omitted" in rendered,
        },
        "freshness": _defined({"valid_at": _text(args.get("valid_at")), "latest_source_timestamp": _latest_timestamp(raw)}),
        "warnings": _context_warnings(raw, rendered, len(candidates), len(items)),
    }
    return text(rendered, structured=structured)
