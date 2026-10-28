"""Tool routing, ported from mindgraph-mcp's ``CallTool`` handler (index.ts) and the
``handleTool`` preamble (tools.ts): default ``agent_id``, governance checkpoint,
then default write idempotency and disposition checks.

The MCP server's generated per-object-type ontology tools are not exposed: Hermes
routes provider tools by the names listed before ``initialize()``, which precedes
any manifest fetch. ``mindgraph_ontology`` covers the same reads.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

from .governance import GovernanceGate
from .handlers_read import handle_ingest, handle_ontology, handle_retrieve, handle_series_query, handle_synthesize
from .handlers_write import handle_capture, handle_commit, handle_plan, handle_reason, handle_remember
from .memory_tool import MemoryRuntimeConfig, handle_memory_tool
from .results import dumps, err, tool_error
from .runtime import Runtime

_CONTRACT = Path(__file__).with_name("mcp_contract.json")
_IDEMPOTENT_WRITE_TOOLS = ("mindgraph_capture", "mindgraph_reason", "mindgraph_commit")
_DISPOSITIONS = ("reuse_uid", "supersedes_uid", "contradicts_uid", "confirm_new", "on_near_duplicate")

_HANDLERS: dict[str, Callable[[Runtime, dict[str, Any]], str]] = {
    "mindgraph_capture": handle_capture,
    "mindgraph_reason": handle_reason,
    "mindgraph_commit": handle_commit,
    "mindgraph_plan": handle_plan,
    "mindgraph_retrieve": handle_retrieve,
    "mindgraph_remember": handle_remember,
    "mindgraph_series_query": handle_series_query,
    "mindgraph_ingest": handle_ingest,
    "mindgraph_synthesize": handle_synthesize,
    "mindgraph_ontology": handle_ontology,
}


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    """The mindgraph-mcp general-profile snapshot; immutable, so safe to share."""
    return json.loads(_CONTRACT.read_text(encoding="utf-8"))


def static_tool_schemas() -> list[dict[str, Any]]:
    return [dict(tool) for tool in contract()["tools"]]


def handle_tool(
    rt: Runtime,
    gate: Optional[GovernanceGate],
    memory_config: MemoryRuntimeConfig,
    name: str,
    args: Optional[dict[str, Any]],
) -> str:
    tool_args = dict(args or {})
    if not tool_args.get("agent_id"):
        tool_args["agent_id"] = rt.agent_id

    if gate is not None:
        verdict = gate.check(name, tool_args)
        if not verdict.allowed:
            return dumps(verdict.payload())

    try:
        if name in _IDEMPOTENT_WRITE_TOOLS and tool_args.get("action") != "get_open_decisions":
            key = rt.default_idempotency_key(name, tool_args)
            if key:
                tool_args["idempotency_key"] = key
            chosen = [
                tool_args[key]
                for key in _DISPOSITIONS
                if tool_args.get(key) is not None and (key != "confirm_new" or tool_args[key] is True)
            ]
            if len(chosen) > 1:
                return err("resolution dispositions are mutually exclusive")

        if name == "mindgraph_memory":
            return handle_memory_tool(rt, tool_args, memory_config)
        handler = _HANDLERS.get(name)
        if handler is None:
            return err(f"Unknown tool: {name}")
        return handler(rt, tool_args)
    except Exception as exc:  # every failure reaches the model as a typed error, never a crash
        return tool_error(exc)
