"""Governance checkpoint, ported from mindgraph-mcp test/governance.test.ts."""

from __future__ import annotations

import json

import httpx
import pytest
from hermes_mindgraph_plugin.governance import GovernanceGate, governance_target, tool_mutability


class Server:
    """Scripted ``httpx.post`` stand-in: each reply is a Response or an exception."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def __call__(self, url, *, headers, content, timeout):
        self.requests.append({"url": url, "headers": headers, "body": json.loads(content)})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply


def response(status: int, body) -> httpx.Response:
    text = body if isinstance(body, str) else json.dumps(body)
    return httpx.Response(status, text=text, request=httpx.Request("POST", "https://mg.test/agent/governance"))


def decision(verdict: str, **extra):
    return response(200, {"decision": verdict, "obligations": [], "fired_policies": [], **extra})


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def gate(server, **kwargs) -> GovernanceGate:
    return GovernanceGate(
        base_url="https://mg.test/",
        api_key="mg_test",
        agent_id="hermes",
        post=server,
        sleep=lambda _: None,
        retry_delays=(0, 0),
        **kwargs,
    )


def test_classifies_mixed_tool_actions_conservatively():
    assert tool_mutability("mindgraph_plan", "get_plan") == "read"
    assert tool_mutability("mindgraph_plan", "get_executions") == "read"
    assert tool_mutability("mindgraph_plan", "create_task") == "write"
    assert tool_mutability("mindgraph_plan", None) == "write"
    assert tool_mutability("mindgraph_retrieve", "context") == "read"
    assert tool_mutability("mindgraph_memory", "status") == "read"
    assert tool_mutability("mindgraph_remember", "remember") == "write"
    assert tool_mutability("mindgraph_remember", "forget") == "write"
    assert tool_mutability("customer_search", None) == "read"
    assert tool_mutability("mindgraph_capture", "entity") == "write"


def test_builds_action_aware_target_with_deduplicated_uids():
    assert governance_target(
        "mindgraph_plan",
        {
            "action": "checkpoint_iteration",
            "task_uid": "task-1",
            "execution_uid": "execution-1",
            "related_uids": ["task-1", "symbol-1"],
        },
    ) == {
        "tool_name": "mindgraph_plan",
        "action": "checkpoint_iteration",
        "mutability": "write",
        "target_uids": ["task-1", "execution-1", "symbol-1"],
    }


def test_sends_the_checkpoint_request():
    server = Server(decision("permit"))
    result = gate(server, org_id="org-1").check(
        "mindgraph_plan",
        {"action": "complete_execution", "execution_uid": "execution-1", "produces_node_uid": "lesson-1"},
    )
    assert result.allowed
    request = server.requests[0]
    assert request["url"] == "https://mg.test/agent/governance"
    assert request["headers"]["x-mindgraph-org"] == "org-1"
    assert request["body"]["action"] == "check"
    assert request["body"]["act"] == "tool_invoke"
    assert request["body"]["tier"] == "checkpoint"
    assert request["body"]["agent_id"] == "hermes"
    assert request["body"]["context"] == {"adapter": "mindgraph-hermes"}
    assert request["body"]["target"] == {
        "tool_name": "mindgraph_plan",
        "action": "complete_execution",
        "mutability": "write",
        "target_uids": ["execution-1", "lesson-1"],
    }


def test_governance_less_server_permits_and_caches_the_probe():
    server = Server(response(400, "unknown action"))
    checker = gate(server)
    assert checker.check("mindgraph_retrieve", {}).allowed
    assert checker.check("mindgraph_capture", {}).allowed
    assert len(server.requests) == 1


def test_surfaces_the_policy_name_on_deny():
    server = Server(decision("deny", fired_policies=[{"name": "No external writes"}]))
    result = gate(server).check("mindgraph_capture", {})
    assert not result.allowed
    assert result.decision == "deny"
    assert result.policy == "No external writes"
    assert result.payload()["error"] == "Denied by MindGraph governance policy No external writes"


def test_returns_approval_details_without_parking():
    server = Server(
        response(
            200,
            {
                "decision": "conditional",
                "approval_uid": "approval-1",
                "obligations": [{"duty": "require_approval"}],
                "fired_policies": [{"name": "PII egress"}],
            },
        )
    )
    result = gate(server).check("mindgraph_ingest", {})
    assert not result.allowed
    assert result.decision == "conditional"
    assert result.approval_uid == "approval-1"
    assert "approval-1" in result.message


def test_reprobes_after_the_unsupported_lease_expires():
    clock = Clock()
    server = Server(response(400, "unknown action"), decision("deny"))
    checker = gate(server, clock=clock)
    assert checker.check("mindgraph_retrieve", {}).allowed
    assert checker.check("mindgraph_retrieve", {}).allowed
    assert len(server.requests) == 1
    clock.now += 6 * 60
    assert not checker.check("mindgraph_retrieve", {}).allowed
    assert len(server.requests) == 2


def test_retries_a_transient_failure_then_permits():
    server = Server(response(503, "upstream"), decision("permit"))
    assert gate(server).check("mindgraph_retrieve", {}).allowed
    assert len(server.requests) == 2


def test_fails_closed_with_a_connectivity_message_after_retries():
    server = Server(httpx.ConnectError("ECONNRESET"))
    result = gate(server).check("mindgraph_retrieve", {})
    assert not result.allowed
    assert len(server.requests) == 3
    assert "unreachable" in result.message
    assert "not a governance denial" in result.message
    assert "MINDGRAPH_GOVERNANCE=off" not in result.message


def test_refused_credential_is_not_a_governance_less_server():
    server = Server(response(403, "forbidden"))
    checker = gate(server)
    result = checker.check("mindgraph_retrieve", {})
    assert not result.allowed
    assert "not permitted to evaluate" in result.message
    checker.check("mindgraph_retrieve", {})
    assert len(server.requests) == 2


@pytest.mark.parametrize("duty", ["notify", "redact"])
def test_fails_closed_on_an_obligation_it_cannot_enforce(duty):
    server = Server(response(200, {"decision": "conditional", "obligations": [{"duty": duty}], "fired_policies": []}))
    result = gate(server).check("mindgraph_capture", {})
    assert not result.allowed
    assert "cannot safely enforce" in result.message


def test_disabled_gate_makes_no_request():
    server = Server(decision("deny"))
    assert gate(server, disabled=True).check("mindgraph_capture", {}).allowed
    assert server.requests == []


def test_invalid_decision_body_refuses():
    server = Server(response(200, "not json"))
    result = gate(server).check("mindgraph_capture", {})
    assert not result.allowed
    assert "invalid decision" in result.message


def test_gates_are_independent_per_instance():
    """Multiplexing: one profile's unsupported verdict must not leak to another."""
    unsupported = gate(Server(response(404, "missing")))
    governed = gate(Server(decision("deny")))
    assert unsupported.check("mindgraph_capture", {}).allowed
    assert not governed.check("mindgraph_capture", {}).allowed
