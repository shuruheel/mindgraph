"""Dispatcher preamble, ported from mindgraph-mcp's handleTool / CallTool tests."""

from __future__ import annotations

import json

from mindgraph import MindGraphError

from hermes_mindgraph_plugin.dispatch import contract, handle_tool
from hermes_mindgraph_plugin.governance import GateResult
from hermes_mindgraph_plugin.memory_tool import MemoryRuntimeConfig

CONFIG = MemoryRuntimeConfig(server_version="1.0.0")


def call(runtime, name, args, gate=None):
    return json.loads(handle_tool(runtime, gate, CONFIG, name, args))


def graph_calls(client):
    """SDK calls other than the (cached) generated-tool manifest lookup."""
    return [c for c in client.calls if c[0] != "list_ontology_tools"]


def test_agent_id_is_injected_when_absent(runtime, fake_client):
    call(runtime, "mindgraph_remember", {"action": "remember", "text": "Prefers tea"})
    (_, kwargs), = fake_client.called("remember")
    assert kwargs["agent_id"] == "hermes"


def test_writes_get_a_turn_scoped_idempotency_key(runtime, fake_client):
    args = {"action": "entity", "label": "Ada Lovelace", "entity_type": "person"}
    call(runtime, "mindgraph_capture", dict(args))
    call(runtime, "mindgraph_capture", dict(args))
    runtime.turn_number = 2
    call(runtime, "mindgraph_capture", dict(args))
    sent = [json.dumps([a, k], default=str) for _, a, k in graph_calls(fake_client)]
    assert len(sent) == 3
    runtime.turn_number = 1
    key_turn_1 = runtime.default_idempotency_key("mindgraph_capture", {**args, "agent_id": "hermes"})
    runtime.turn_number = 2
    key_turn_2 = runtime.default_idempotency_key("mindgraph_capture", {**args, "agent_id": "hermes"})
    assert key_turn_1 != key_turn_2
    assert key_turn_1 in sent[0] and key_turn_1 in sent[1], "a replay inside one turn reuses the key"
    assert key_turn_2 in sent[2], "the next turn is a new write"


def test_an_explicit_idempotency_key_wins(runtime):
    assert runtime.default_idempotency_key("mindgraph_capture", {"idempotency_key": "mine"}) == "mine"


def test_dispositions_are_mutually_exclusive(runtime, fake_client):
    result = call(
        runtime,
        "mindgraph_reason",
        {"action": "claim", "label": "x", "reuse_uid": "a", "supersedes_uid": "b"},
    )
    assert result == {"error": "resolution dispositions are mutually exclusive"}
    assert graph_calls(fake_client) == []


def test_confirm_new_false_is_not_a_disposition(runtime, fake_client):
    result = call(runtime, "mindgraph_reason", {"action": "claim", "label": "x", "reuse_uid": "a", "confirm_new": False})
    assert "error" not in result


def test_unknown_tools_are_refused(runtime):
    assert call(runtime, "mindgraph_code", {"action": "recall"}) == {"error": "Unknown tool: mindgraph_code"}


def test_server_errors_reach_the_model_typed(runtime, fake_client):
    fake_client.responses["remember"] = MindGraphError(
        "Request failed", 503, {"error": "busy", "code": "query_admission_busy", "retriable": False}
    )
    result = call(runtime, "mindgraph_remember", {"action": "remember", "text": "x"})
    assert result["code"] == "query_admission_busy"
    assert result["retriable"] is False
    assert result["status"] == 503


def test_a_denied_call_never_reaches_the_sdk(runtime, fake_client):
    class Deny:
        def check(self, name, args):
            assert args["agent_id"] == "hermes", "governance sees the effective agent"
            return GateResult(False, "Denied by MindGraph governance", decision="deny")

    result = call(runtime, "mindgraph_capture", {"action": "entity", "label": "Ada"}, gate=Deny())
    assert result["error"] == "Denied by MindGraph governance"
    assert result["decision"] == "deny"
    assert graph_calls(fake_client) == []


def test_the_contract_is_the_general_profile():
    names = {tool["name"] for tool in contract()["tools"]}
    assert names == {
        "mindgraph_memory",
        "mindgraph_capture",
        "mindgraph_reason",
        "mindgraph_commit",
        "mindgraph_plan",
        "mindgraph_retrieve",
        "mindgraph_remember",
        "mindgraph_series_query",
        "mindgraph_ingest",
        "mindgraph_synthesize",
        "mindgraph_ontology",
    }
    for tool in contract()["tools"]:
        props = tool["parameters"].get("properties", {})
        assert not {"invocation_context", "code_refs", "repo", "repo_space_uid"} & set(props)
