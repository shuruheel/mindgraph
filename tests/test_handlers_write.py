"""Wire-level tests for the write handlers, ported from mindgraph-mcp's
``test/dispatch.test.ts`` and ``test/regressions.test.ts`` (R9): each action must
reach the right SDK method with the TS server-contract payload."""

from __future__ import annotations

import json

import pytest

from hermes_mindgraph_plugin.handlers_write import (
    handle_capture,
    handle_commit,
    handle_plan,
    handle_reason,
    handle_remember,
)


def _is_error(result: str) -> bool:
    return "error" in json.loads(result)


def _only_call(fake_client, method):
    calls = fake_client.called(method)
    assert len(calls) == 1, fake_client.calls
    return calls[0]


# ── mindgraph_remember ───────────────────────────────────────────────


def test_remember_sends_custom_id_as_upsert_key(runtime, fake_client):
    handle_remember(
        runtime,
        {"action": "remember", "text": "User prefers dark mode", "custom_id": "pref:theme", "agent_id": "hermes"},
    )
    args, kwargs = _only_call(fake_client, "remember")
    assert args == ("User prefers dark mode",)
    assert kwargs == {"custom_id": "pref:theme", "agent_id": "hermes"}


def test_remember_never_sends_an_idempotency_key(runtime, fake_client):
    handle_remember(runtime, {"action": "remember", "text": "Deploy target is mg-prod", "idempotency_key": "k"})
    _, kwargs = _only_call(fake_client, "remember")
    assert "idempotency_key" not in kwargs


def test_remember_rejects_blank_text(runtime, fake_client):
    assert _is_error(handle_remember(runtime, {"action": "remember", "text": "  "}))
    assert fake_client.calls == []


def test_remember_forwards_optional_fields(runtime, fake_client):
    handle_remember(
        runtime,
        {
            "action": "remember",
            "text": "t",
            "label": "L",
            "space_uid": "space:1",
            "on_near_duplicate": "create",
            "props": {"k": 1},
        },
    )
    _, kwargs = _only_call(fake_client, "remember")
    assert kwargs == {"label": "L", "space_uid": "space:1", "on_near_duplicate": "create", "props": {"k": 1}}


def test_forget_by_custom_id_with_dry_run(runtime, fake_client):
    handle_remember(runtime, {"action": "forget", "custom_id": "pref:theme", "dry_run": True, "agent_id": "hermes"})
    _, kwargs = _only_call(fake_client, "forget")
    assert kwargs == {"custom_id": "pref:theme", "dry_run": True, "agent_id": "hermes"}


def test_forget_uid_takes_precedence_over_custom_id(runtime, fake_client):
    handle_remember(
        runtime, {"action": "forget", "uid": "n1", "custom_id": "pref:theme", "cascade": False, "reason": "stale"}
    )
    _, kwargs = _only_call(fake_client, "forget")
    assert kwargs == {"uid": "n1", "cascade": False, "reason": "stale"}


def test_forget_without_target_is_an_error(runtime, fake_client):
    assert _is_error(handle_remember(runtime, {"action": "forget"}))
    assert fake_client.calls == []


def test_unknown_remember_action(runtime):
    assert _is_error(handle_remember(runtime, {"action": "recall"}))


# ── mindgraph_capture ────────────────────────────────────────────────


def test_entity_person_creates_with_subtype_and_description(runtime, fake_client):
    handle_capture(
        runtime,
        {
            "action": "entity",
            "entity_type": "person",
            "label": "Henry Kissinger",
            "summary": "Diplomat",
            "agent_id": "hermes",
            "reuse_uid": "n9",
        },
    )
    _, kwargs = _only_call(fake_client, "entity")
    assert kwargs == {
        "action": "create",
        "label": "Henry Kissinger",
        "props": {"description": "Diplomat", "entity_type": "person"},
        "agent_id": "hermes",
        "reuse_uid": "n9",
    }


@pytest.mark.parametrize("entity_type", ["organization", "nation", "event", "place", "concept"])
def test_each_entity_type_reaches_the_entity_resolver(runtime, fake_client, entity_type):
    handle_capture(runtime, {"action": "entity", "entity_type": entity_type, "label": "X"})
    _, kwargs = _only_call(fake_client, "entity")
    assert kwargs["props"] == {"entity_type": entity_type}


def test_entity_defaults_to_concept_and_type_overrides_props(runtime, fake_client):
    handle_capture(runtime, {"action": "entity", "label": "Entropy", "props": {"entity_type": "x", "k": 1}})
    _, kwargs = _only_call(fake_client, "entity")
    assert kwargs["props"] == {"entity_type": "concept", "k": 1}


def test_concept_capture_creates_concept_entity(runtime, fake_client):
    handle_capture(runtime, {"action": "concept", "label": "Justice", "summary": "fairness"})
    _, kwargs = _only_call(fake_client, "entity")
    assert kwargs == {
        "action": "create",
        "label": "Justice",
        "props": {"entity_type": "concept", "description": "fairness"},
    }


def test_journal_posts_session_journal_body(runtime, fake_client):
    handle_capture(
        runtime,
        {
            "action": "journal",
            "label": "Note",
            "content": "felt good",
            "mood": "happy",
            "tags": ["a", "b"],
            "agent_id": "hermes",
            "idempotency_key": "k1",
        },
    )
    _, kwargs = _only_call(fake_client, "session")
    assert kwargs == {
        "action": "journal",
        "label": "Note",
        "props": {"content": "felt good", "mood": "happy", "tags": ["a", "b"]},
        "agent_id": "hermes",
        "idempotency_key": "k1",
    }


def test_journal_without_content_calls_nothing(runtime, fake_client):
    assert _is_error(handle_capture(runtime, {"action": "journal", "label": "Note"}))
    assert fake_client.calls == []


def test_lesson_distills_the_monolithic_lesson_contract(runtime, fake_client):
    handle_capture(
        runtime,
        {
            "action": "lesson",
            "label": "Retry the parser after normalizing input",
            "summary": "Normalization fixed the failing parse.",
            "session_uid": "session-1",
            "summarizes_uids": ["execution-1", "task-1"],
            "confidence": 0.9,
            "agent_id": "hermes",
        },
    )
    _, kwargs = _only_call(fake_client, "distill")
    assert kwargs == {
        "label": "Retry the parser after normalizing input",
        "output_type": "lesson",
        "summary": "Normalization fixed the failing parse.",
        "confidence": 0.9,
        "session_uid": "session-1",
        "summarizes_uids": ["execution-1", "task-1"],
        "agent_id": "hermes",
    }


def test_skill_distills_caller_authored_props_with_provenance(runtime, fake_client):
    handle_capture(
        runtime,
        {
            "action": "skill",
            "label": "Capture parser recovery",
            "summary": "Reusable parser recovery procedure",
            "name": "parser-recovery",
            "description": "Recover a parser after malformed input.",
            "content": "# Parser recovery\n\nNormalize input, then retry.",
            "license": "MIT",
            "session_uid": "session-1",
            "summarizes_uids": ["project-1"],
            "agent_id": "hermes",
            "reuse_uid": "dropped-for-skills",
        },
    )
    _, kwargs = _only_call(fake_client, "distill")
    assert kwargs == {
        "label": "Capture parser recovery",
        "output_type": "skill",
        "summary": "Reusable parser recovery procedure",
        "session_uid": "session-1",
        "summarizes_uids": ["project-1"],
        "props": {
            "name": "parser-recovery",
            "description": "Recover a parser after malformed input.",
            "content": "# Parser recovery\n\nNormalize input, then retry.",
            "license": "MIT",
        },
        "agent_id": "hermes",
    }


def test_skill_without_provenance_is_rejected(runtime, fake_client):
    result = handle_capture(
        runtime,
        {
            "action": "skill",
            "label": "Capture parser recovery",
            "name": "parser-recovery",
            "description": "Recover a parser after malformed input.",
            "content": "# Parser recovery",
        },
    )
    assert "at least one of session_uid" in json.loads(result)["error"]
    assert fake_client.calls == []


def test_observation_captures(runtime, fake_client):
    handle_capture(runtime, {"action": "observation", "label": "Sky is blue", "confidence": 0.9, "source_uid": "s"})
    _, kwargs = _only_call(fake_client, "capture")
    assert kwargs == {"action": "observation", "label": "Sky is blue", "confidence": 0.9}


def test_snippet_carries_source_uid(runtime, fake_client):
    handle_capture(runtime, {"action": "snippet", "label": "quote", "source_uid": "src-1"})
    _, kwargs = _only_call(fake_client, "capture")
    assert kwargs == {"action": "snippet", "label": "quote", "source_uid": "src-1"}


# ── mindgraph_reason ─────────────────────────────────────────────────


def test_claim_argues_with_structured_claim_and_evidence_array(runtime, fake_client):
    handle_reason(
        runtime,
        {
            "action": "claim",
            "claim": {"label": "X causes Y", "confidence": 0.8},
            "evidence": [{"label": "study A"}, {"label": "study B"}],
            "warrant": {"label": "because"},
            "argument": {"label": "top"},
            "agent_id": "hermes",
        },
    )
    _, kwargs = _only_call(fake_client, "argue")
    assert fake_client.called("inquire") == []
    assert "action" not in kwargs
    assert kwargs == {
        "claim": {"label": "X causes Y", "confidence": 0.8},
        "evidence": [{"label": "study A"}, {"label": "study B"}],
        "warrant": {"label": "because"},
        "argument": {"label": "top"},
        "agent_id": "hermes",
    }


def test_claim_falls_back_to_top_level_label(runtime, fake_client):
    handle_reason(runtime, {"action": "claim", "label": "Implicit claim", "confidence": 0.6})
    _, kwargs = _only_call(fake_client, "argue")
    assert kwargs["claim"] == {"label": "Implicit claim", "confidence": 0.6}


def test_claim_maps_prose_into_props(runtime, fake_client):
    """R9: a top-level ``content`` key is silently dropped by serde."""
    handle_reason(
        runtime,
        {
            "action": "claim",
            "claim": {"label": "L7 resolver is fragile", "content": "detailed prose", "confidence": 0.9},
            "evidence": [{"label": "audit", "description": "seen in prod"}],
            "warrant": {"label": "warrant", "content": "because"},
        },
    )
    _, kwargs = _only_call(fake_client, "argue")
    assert kwargs["claim"]["props"] == {"content": "detailed prose"}
    assert kwargs["evidence"] == [{"label": "audit", "props": {"description": "seen in prod"}}]
    assert kwargs["warrant"] == {"label": "warrant", "props": {"content": "because"}}


def test_claim_without_claim_or_label_is_an_error(runtime, fake_client):
    assert _is_error(handle_reason(runtime, {"action": "claim"}))
    assert fake_client.calls == []


@pytest.mark.parametrize("action", ["open_question", "hypothesis", "theory", "anomaly", "assumption"])
def test_inquiry_actions_pass_through(runtime, fake_client, action):
    handle_reason(runtime, {"action": action, "label": "Q", "supersedes_uid": "q0"})
    _, kwargs = _only_call(fake_client, "inquire")
    assert kwargs == {"action": action, "label": "Q", "supersedes_uid": "q0"}


def test_inquiry_without_label_calls_nothing(runtime, fake_client):
    assert _is_error(handle_reason(runtime, {"action": "hypothesis"}))
    assert fake_client.calls == []


# ── mindgraph_commit ─────────────────────────────────────────────────


@pytest.mark.parametrize("action", ["goal", "project", "milestone"])
def test_commitments_pass_action_through(runtime, fake_client, action):
    handle_commit(runtime, {"action": action, "label": "L", "parent_uid": "p1"})
    _, kwargs = _only_call(fake_client, "commit")
    assert kwargs == {"action": action, "label": "L", "parent_uid": "p1"}


def test_open_decision_posts_deliberation_with_resolution(runtime, fake_client):
    handle_commit(
        runtime, {"action": "open_decision", "label": "DB choice", "summary": "pg vs sqlite", "idempotency_key": "k"}
    )
    _, kwargs = _only_call(fake_client, "deliberate")
    assert kwargs == {"action": "open_decision", "label": "DB choice", "summary": "pg vs sqlite", "idempotency_key": "k"}


def test_add_option(runtime, fake_client):
    handle_commit(runtime, {"action": "add_option", "decision_uid": "d1", "label": "Postgres"})
    _, kwargs = _only_call(fake_client, "deliberate")
    assert kwargs == {"action": "add_option", "decision_uid": "d1", "label": "Postgres"}


def test_add_option_without_decision_uid_calls_nothing(runtime, fake_client):
    assert _is_error(handle_commit(runtime, {"action": "add_option", "label": "x"}))
    assert fake_client.calls == []


def test_add_constraint(runtime, fake_client):
    handle_commit(runtime, {"action": "add_constraint", "decision_uid": "d1", "label": "budget"})
    _, kwargs = _only_call(fake_client, "deliberate")
    assert kwargs == {"action": "add_constraint", "label": "budget", "decision_uid": "d1"}


def test_resolve_decision_forwards_provenance(runtime, fake_client):
    handle_commit(
        runtime,
        {
            "action": "resolve_decision",
            "decision_uid": "d1",
            "chosen_option_uid": "o1",
            "informs_uid": ["ctx1"],
            "as_of_date": "2026-07-17",
            "session_id": "session7",
            "retrieval_trace_id": "trace7",
        },
    )
    _, kwargs = _only_call(fake_client, "deliberate")
    assert kwargs == {
        "action": "resolve",
        "decision_uid": "d1",
        "chosen_option_uid": "o1",
        "informs_uid": ["ctx1"],
        "as_of_date": "2026-07-17",
        "session_id": "session7",
        "retrieval_trace_id": "trace7",
    }


def test_resolve_decision_requires_chosen_option(runtime, fake_client):
    assert _is_error(handle_commit(runtime, {"action": "resolve_decision", "decision_uid": "d1"}))
    assert fake_client.calls == []


def test_get_open_decisions(runtime, fake_client):
    fake_client.responses["get_open_decisions"] = [{"uid": "d1"}]
    assert json.loads(handle_commit(runtime, {"action": "get_open_decisions"})) == [{"uid": "d1"}]


# ── mindgraph_plan ───────────────────────────────────────────────────

_PLAN_ARGS = {
    "label": "L",
    "summary": "S",
    "confidence": 0.8,
    "salience": 0.7,
    "goal_uid": "goal-1",
    "task_uid": "task-1",
    "plan_uid": "plan-1",
    "target_uid": "target-1",
    "depends_on_uids": ["step-0"],
    "related_uids": ["code-1"],
    "status": "in_progress",
    "props": {"order": 1},
    "agent_id": "hermes",
}


@pytest.mark.parametrize("action", ["create_task", "create_plan", "add_step", "update_status", "get_plan"])
def test_plan_actions_forward_every_contract_field(runtime, fake_client, action):
    handle_plan(runtime, {"action": action, **_PLAN_ARGS})
    _, kwargs = _only_call(fake_client, "plan")
    assert kwargs == {"action": action, **_PLAN_ARGS}


def test_plan_lease_fields_are_forwarded(runtime, fake_client):
    lease = {"task_uid": "t", "lease_epoch": 3, "lease_ttl_secs": 600, "expected_version": 7, "allow_takeover": True}
    handle_plan(runtime, {"action": "claim_task", **lease})
    _, kwargs = _only_call(fake_client, "plan")
    assert kwargs == {"action": "claim_task", **lease}


def test_create_task_with_repo_is_refused_without_the_code_adapter(runtime, fake_client):
    assert _is_error(handle_plan(runtime, {"action": "create_task", "label": "L", "repo": "mindgraph-rs"}))
    assert fake_client.calls == []


def test_start_execution_uses_plan_uid(runtime, fake_client):
    handle_plan(
        runtime,
        {
            "action": "start_execution",
            "label": "Attempt 1",
            "summary": "Run the focused test",
            "plan_uid": "plan-1",
            "task_uid": "ignored",
            "executor_uid": "agent-node-1",
            "affordance_uid": "affordance-1",
            "related_uids": ["task-1", "symbol-1"],
            "input_snapshot": {"command": "npm test"},
            "props": {"branch": "feature"},
            "agent_id": "hermes",
        },
    )
    _, kwargs = _only_call(fake_client, "execution")
    assert kwargs == {
        "action": "start",
        "label": "Attempt 1",
        "summary": "Run the focused test",
        "plan_uid": "plan-1",
        "executor_uid": "agent-node-1",
        "affordance_uid": "affordance-1",
        "related_uids": ["task-1", "symbol-1"],
        "input_snapshot": {"command": "npm test"},
        "props": {"branch": "feature"},
        "agent_id": "hermes",
    }


def test_complete_execution_forwards_terminal_evidence(runtime, fake_client):
    handle_plan(
        runtime,
        {
            "action": "complete_execution",
            "execution_uid": "execution-1",
            "produces_node_uid": "lesson-1",
            "output_snapshot": {"exit_code": 0},
            "side_effects": ["updated src/tools.ts"],
            "outcome": "tests passed",
        },
    )
    _, kwargs = _only_call(fake_client, "execution")
    assert kwargs == {
        "action": "complete",
        "execution_uid": "execution-1",
        "produces_node_uid": "lesson-1",
        "output_snapshot": {"exit_code": 0},
        "side_effects": ["updated src/tools.ts"],
        "outcome": "tests passed",
    }


def test_fail_execution_forwards_error_evidence(runtime, fake_client):
    handle_plan(
        runtime,
        {"action": "fail_execution", "execution_uid": "execution-1", "outcome": "failed", "error": "assertion mismatch"},
    )
    _, kwargs = _only_call(fake_client, "execution")
    assert kwargs == {"action": "fail", "execution_uid": "execution-1", "outcome": "failed", "error": "assertion mismatch"}


def test_register_agent_and_get_executions(runtime, fake_client):
    handle_plan(runtime, {"action": "register_agent", "label": "Hermes", "props": {"model": "x"}})
    handle_plan(runtime, {"action": "get_executions", "filter_plan_uid": "plan-1"})
    assert [kwargs for _, kwargs in fake_client.called("execution")] == [
        {"action": "register_agent", "label": "Hermes", "props": {"model": "x"}},
        {"action": "get_executions", "filter_plan_uid": "plan-1"},
    ]


def test_governance_read_uses_canonical_action(runtime, fake_client):
    handle_plan(runtime, {"action": "get_pending", "label": "L", "task_uid": "t1"})
    _, kwargs = _only_call(fake_client, "governance")
    assert kwargs == {"action": "get_pending"}


@pytest.mark.parametrize("forbidden", ["create_policy", "request_approval", "resolve_approval"])
def test_governance_writes_are_refused(runtime, fake_client, forbidden):
    """C33: the enum is advisory to the model; dispatch is the actual boundary."""
    result = handle_plan(runtime, {"action": forbidden, "label": "L", "task_uid": "t1", "props": {"approved": True}})
    assert _is_error(result)
    assert fake_client.calls == []


def test_governance_writes_are_not_advertised():
    from pathlib import Path

    contract = json.loads((Path(__file__).resolve().parent.parent / "mcp_contract.json").read_text())
    plan = next(tool for tool in contract["tools"] if tool["name"] == "mindgraph_plan")
    actions = set(plan["parameters"]["properties"]["action"]["enum"])
    assert not actions & {"create_policy", "request_approval", "resolve_approval"}


def test_add_procedure_step_remaps_to_add_step(runtime, fake_client):
    handle_plan(runtime, {"action": "add_procedure_step", "label": "S", "target_uid": "f1"})
    _, kwargs = _only_call(fake_client, "procedure")
    assert kwargs == {"action": "add_step", "label": "S", "target_uid": "f1"}


@pytest.mark.parametrize("action", ["create_flow", "add_affordance", "add_control"])
def test_procedure_actions_pass_through(runtime, fake_client, action):
    handle_plan(runtime, {"action": action, "label": "L"})
    _, kwargs = _only_call(fake_client, "procedure")
    assert kwargs == {"action": action, "label": "L"}


def test_risk_actions(runtime, fake_client):
    handle_plan(runtime, {"action": "assess_risk", "label": "R", "target_uid": "x"})
    handle_plan(runtime, {"action": "get_assessments", "target_uid": "x"})
    assert [kwargs for _, kwargs in fake_client.called("risk")] == [
        {"action": "assess", "label": "R", "target_uid": "x"},
        {"action": "get_assessments", "target_uid": "x"},
    ]


def test_unknown_plan_action(runtime):
    assert _is_error(handle_plan(runtime, {"action": "teleport"}))
