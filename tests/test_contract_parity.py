"""Every parameter the MCP contract advertises must be read by the Python handler.

``mcp_contract.json`` is regenerated from mindgraph-mcp, so a new schema property
lands in the tools Hermes shows the model even when no handler forwards it; the
model then sets a knob that silently does nothing (``as_of`` and
``retrieval_mode`` arrived this way in MCP 0.25). Handlers read arguments by
name (``args.get("x")``, field tuples such as ``_PLAN_FIELDS``), so a property
counts as consumed when it occurs as a string literal in the tool's handler
function or in any module-level function or constant that function reaches.
"""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# tool -> (module file, handler function), mirroring dispatch._HANDLERS.
HANDLERS = {
    "mindgraph_capture": ("handlers_write.py", "handle_capture"),
    "mindgraph_reason": ("handlers_write.py", "handle_reason"),
    "mindgraph_commit": ("handlers_write.py", "handle_commit"),
    "mindgraph_plan": ("handlers_write.py", "handle_plan"),
    "mindgraph_remember": ("handlers_write.py", "handle_remember"),
    "mindgraph_retrieve": ("handlers_read.py", "handle_retrieve"),
    "mindgraph_series_query": ("handlers_read.py", "handle_series_query"),
    "mindgraph_ingest": ("handlers_read.py", "handle_ingest"),
    "mindgraph_synthesize": ("handlers_read.py", "handle_synthesize"),
    "mindgraph_ontology": ("handlers_read.py", "handle_ontology"),
    "mindgraph_memory": ("memory_tool.py", "handle_memory_tool"),
}

# Properties consumed without their name appearing in the handler. Each entry is a
# claim; keep it short and say why.
ALLOWED = {
    # handle_series_query validates, then forwards the whole argument dict
    # (``client.series(**_compact(args))``), exactly as the MCP does.
    "mindgraph_series_query": {"cursor", "fill", "limit"},
    # Deliberately ignored, as in the MCP's handleSynthesize: the synthesis
    # endpoints take no agent id (the shared schema advertises it on every tool).
    "mindgraph_synthesize": {"agent_id"},
}


@lru_cache(maxsize=None)
def _definitions(module: str) -> dict[str, ast.AST]:
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defs[node.target.id] = node
    return defs


def consumed_literals(module: str, function: str) -> set[str]:
    """String literals in ``function`` and every module-level definition it reaches."""
    defs = _definitions(module)
    seen: set[str] = set()
    pending = [function]
    literals: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen or name not in defs:
            continue
        seen.add(name)
        for node in ast.walk(defs[name]):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.add(node.value)
            elif isinstance(node, ast.Name):
                pending.append(node.id)
    return literals


def _contract() -> dict:
    return json.loads((REPO_ROOT / "mcp_contract.json").read_text(encoding="utf-8"))


def test_every_contract_tool_has_a_handler():
    assert {tool["name"] for tool in _contract()["tools"]} == set(HANDLERS)


def test_instructions_include_guidance_after_escaped_backtick_semicolon():
    instructions = _contract()["instructions"]
    assert "`hybrid`; use `document_index`" in instructions
    assert "## Comprehensive read tools" in instructions
    assert "## When to WRITE" in instructions
    assert "## Tool tips" in instructions
    assert not instructions.endswith("\\")
    assert "mindgraph_code" not in instructions


@pytest.mark.parametrize("tool", _contract()["tools"], ids=lambda tool: tool["name"])
def test_every_advertised_property_is_consumed(tool):
    module, function = HANDLERS[tool["name"]]
    literals = consumed_literals(module, function) | ALLOWED.get(tool["name"], set())
    dropped = sorted(set(tool["parameters"].get("properties", {})) - literals)
    assert not dropped, f"{tool['name']} advertises {dropped} but {module}:{function} never reads them"


def test_allowlist_has_no_stale_entries():
    properties = {tool["name"]: set(tool["parameters"].get("properties", {})) for tool in _contract()["tools"]}
    for name, allowed in ALLOWED.items():
        assert allowed <= properties[name], f"{name}: allowlisted but no longer advertised: {allowed - properties[name]}"
