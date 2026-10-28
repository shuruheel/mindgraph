"""``mindgraph_memory`` contract, ported from mindgraph-mcp test/memory-tool.test.ts."""

from __future__ import annotations

import hashlib
import json
import re

from hermes_mindgraph_plugin.memory_tool import MemoryRuntimeConfig, handle_memory_tool, memory_status


def call(runtime, args, config=None) -> dict:
    return json.loads(handle_memory_tool(runtime, args, config or MemoryRuntimeConfig()))


def test_status_reports_capabilities_without_network(runtime, fake_client):
    config = MemoryRuntimeConfig(
        server_version="0.test", base_url="https://api.example.test", harness="hermes", org_id="org-1"
    )
    status = call(runtime, {"action": "status", "agent_id": "agent-1"}, config)
    assert status == memory_status(
        MemoryRuntimeConfig(
            server_version="0.test",
            base_url="https://api.example.test",
            harness="hermes",
            org_id="org-1",
            agent_id="agent-1",
        )
    )
    assert status["schema_version"] == "mindgraph.memory.result.v1"
    assert status["integration"]["automatic_capture"] is False
    assert status["integration"]["automatic_delivery"] is False
    assert status["integration"]["delivery_verification"] == "unsupported"
    assert status["integration"]["curator_mode"] == "disabled"
    assert status["scope"] == {"org_id": "org-1", "agent_id": "agent-1"}
    assert fake_client.calls == []


def test_status_states_provider_lifecycle_truthfully(runtime):
    status = call(
        runtime, {"action": "status"}, MemoryRuntimeConfig(automatic_capture=True, automatic_delivery=True)
    )
    assert status["integration"]["adapter_state"] == "provider_lifecycle"
    assert status["integration"]["automatic_capture"] is True
    assert status["capabilities"]["lifecycle_event_ingest"] is True
    assert status["capabilities"]["automatic_context_injection"] is True
    codes = [entry["code"] for entry in status["degradation"]]
    assert "automatic_capture_unavailable" not in codes
    # Hermes injecting prefetched context still does not prove the model used it.
    assert "delivery_unverified" in codes


def test_topic_context_is_a_stable_hashed_envelope(runtime, fake_client):
    fake_client.responses["retrieve_context"] = {
        "graph": {
            "nodes": [
                {
                    "uid": "claim-1",
                    "node_type": "Claim",
                    "label": "Graph state aids continuation",
                    "summary": "A scoped claim.",
                    "confidence": 0.8,
                    "updated_at": "2026-09-03T12:00:00Z",
                },
                {
                    "uid": "evidence-1",
                    "node_type": "Observation",
                    "label": "Observed continuation result",
                    "summary": "A bounded observation.",
                },
            ],
            "edges": [{"from_uid": "evidence-1", "to_uid": "claim-1", "edge_type": "SUPPORTS"}],
        },
        "articles": [],
        "chunks": [],
    }
    args = {
        "action": "context",
        "mode": "topic",
        "query": "graph continuation",
        "project_uid": "project-1",
        "max_output_chars": 2_000,
        "agent_id": "agent-1",
    }
    config = MemoryRuntimeConfig(org_id="org-1")
    first, second = call(runtime, args, config), call(runtime, args, config)

    (query,), kwargs = fake_client.called("retrieve_context")[0]
    assert query == "graph continuation"
    assert kwargs == {
        "project_uid": "project-1",
        "node_limit": 8,
        "chunk_limit": 0,
        "article_limit": 0,
        "include_graph": True,
        "graph_expansion_limit": 3,
        "graph_max_depth": 2,
    }
    rendered, envelope = first["result"], first["structured"]
    assert envelope["mode"] == "topic"
    assert envelope["rendered_hash"] == hashlib.sha256(rendered.encode()).hexdigest()
    assert envelope["retrieval_trace"]["strategy"] == "retrieve_context"
    assert envelope["retrieval_trace"]["available_items"] == 3
    assert envelope["retrieval_trace"]["returned_items"] == 3
    assert envelope["retrieval_trace"]["omitted_items"] == 0
    assert envelope["budget"]["requested_chars"] == 2_000
    assert envelope["budget"]["used_chars"] == len(rendered)
    assert envelope["budget"]["bounded"] is False
    assert envelope["freshness"]["latest_source_timestamp"] == "2026-09-03T12:00:00Z"
    assert "items" not in envelope  # compact: the rendered text already carries them
    assert re.fullmatch(r"ctx_[a-f0-9]{24}", envelope["context_id"])
    assert second["structured"]["context_id"] == envelope["context_id"]
    assert any(w["code"] == "delivery_unverified" for w in envelope["warnings"])


def test_resume_and_continuity_use_resume_work(runtime, fake_client):
    fake_client.responses["plan"] = {
        "action": "resume_work",
        "selection_reason": "explicit task scope",
        "task": {"uid": "task-1", "node_type": "Task", "label": "Implement M0", "summary": "Add the portable read workflow."},
        "next_steps": [{"uid": "step-1", "node_type": "Step", "label": "Run conformance tests"}],
        "blockers": [],
        "knowledge": {"lessons": [], "risks": []},
        "recent_executions": [],
        "code_targets": [],
        "truncation": {"steps": False, "executions": False},
    }
    for mode in ("resume", "continuity"):
        result = call(
            runtime,
            {"action": "context", "mode": mode, "task_uid": "task-1", "project_uid": "project-1", "agent_id": "agent-1"},
        )
        assert "# Resume context" in result["result"]
        assert "[task-1]" in result["result"]
        assert result["structured"]["mode"] == mode
        assert result["structured"]["retrieval_trace"]["strategy"] == "resume_work"
    _, kwargs = fake_client.called("plan")[0]
    assert kwargs == {
        "action": "resume_work",
        "task_uid": "task-1",
        "scope_uids": ["project-1"],
        "limit": 1,
        "agent_id": "agent-1",
    }
    assert fake_client.called("retrieve_context") == []


def test_hard_output_bound_reports_omitted_items(runtime, fake_client):
    nodes = [{"uid": f"claim-{i}", "node_type": "Claim", "label": f"Claim {i}", "summary": "x" * 390} for i in range(20)]
    fake_client.responses["retrieve_context"] = {"graph": {"nodes": nodes, "edges": []}}
    result = call(runtime, {"action": "context", "mode": "topic", "query": "claims", "max_output_chars": 512})
    assert len(result["result"]) <= 512
    assert result["structured"]["budget"]["bounded"] is True
    assert any(w["code"] == "context_bounded" for w in result["structured"]["warnings"])


def test_actionable_errors_for_missing_or_invalid_intent(runtime, fake_client):
    assert "requires a non-empty query" in call(runtime, {"action": "context", "mode": "topic"})["error"]
    assert "requires mode" in call(runtime, {"action": "context"})["error"]
    assert "status" in call(runtime, {"action": "observe"})["error"]
    assert fake_client.calls == []


def test_server_errors_keep_code_and_retriable(runtime, fake_client):
    from mindgraph import MindGraphError

    fake_client.responses["retrieve_context"] = MindGraphError(
        "Query deadline exceeded", 504, {"error": "Query deadline exceeded", "code": "query_timeout", "retriable": False}
    )
    result = call(runtime, {"action": "context", "mode": "topic", "query": "x"})
    assert result["code"] == "query_timeout"
    assert result["retriable"] is False
    assert result["status"] == 504
