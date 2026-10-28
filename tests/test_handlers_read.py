"""Read handlers: SDK method + payload per action, ported from mindgraph-mcp
test/dispatch.test.ts, engine-errors.test.ts and regressions.test.ts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hermes_mindgraph_plugin import handlers_read as h

RENDER_READY = (Path(__file__).resolve().parent.parent / "render.py").exists()
needs_render = pytest.mark.skipif(not RENDER_READY, reason="render.py not written yet")


def decoded(result: str):
    return json.loads(result)


def is_error(result: str) -> bool:
    value = decoded(result)
    return isinstance(value, dict) and "error" in value


def only_call(client, method):
    calls = client.called(method)
    assert len(calls) == 1, f"{method} calls: {client.calls}"
    return calls[0]


# ── retrieve ──────────────────────────────────────────────────────────


def test_context_gates_chunks_and_defaults_expansion(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "context", "query": "Kissinger NATO", "format": "json"})
    args, kwargs = only_call(fake_client, "retrieve_context")
    assert args == ("Kissinger NATO",)
    assert kwargs["chunk_limit"] == 0
    assert kwargs["graph_expansion_limit"] == 3
    assert kwargs["graph_max_depth"] == 2
    # General profile: the article leg is not dropped by default.
    assert kwargs["article_limit"] is None


def test_context_include_chunks_uses_limit(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "context", "query": "q", "include_chunks": True, "limit": 3, "format": "json"})
    assert only_call(fake_client, "retrieve_context")[1]["chunk_limit"] == 3


def test_context_include_chunks_without_limit_defaults_to_five(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "context", "query": "q", "include_chunks": True, "format": "json"})
    assert only_call(fake_client, "retrieve_context")[1]["chunk_limit"] == 5


def test_context_forwards_explicit_budgets_and_document_opt_out(runtime, fake_client):
    h.handle_retrieve(runtime, {
        "action": "context", "query": "q", "graph_expansion_limit": 8, "graph_max_depth": 4,
        "include_documents": False, "format": "json",
    })
    kwargs = only_call(fake_client, "retrieve_context")[1]
    assert (kwargs["graph_expansion_limit"], kwargs["graph_max_depth"]) == (8, 4)
    assert kwargs["article_limit"] == 0


def test_context_explicit_article_limit_wins(runtime, fake_client):
    h.handle_retrieve(runtime, {
        "action": "context", "query": "q", "article_limit": 2, "include_documents": False, "format": "json",
    })
    assert only_call(fake_client, "retrieve_context")[1]["article_limit"] == 2


def test_context_without_query_errors(runtime, fake_client):
    assert is_error(h.handle_retrieve(runtime, {"action": "context"}))
    assert fake_client.calls == []


@pytest.mark.parametrize("action,limit_key", [("text", "limit"), ("semantic", "k"), ("hybrid", "k")])
def test_search_actions_route_to_retrieve(runtime, fake_client, action, limit_key):
    h.handle_retrieve(runtime, {"action": action, "query": "q", "limit": 4, "agent_id": "hermes", "format": "json"})
    _, payload = only_call(fake_client, "retrieve")
    assert payload == {"action": action, "query": "q", limit_key: 4, "agent_id": "hermes"}


def test_hybrid_explain_returns_raw_json(runtime, fake_client):
    fake_client.responses["retrieve"] = [{"uid": "n1", "label": "x", "scores": {"fts": 1}}]
    out = h.handle_retrieve(runtime, {"action": "hybrid", "query": "q", "explain": True})
    assert decoded(out) == [{"uid": "n1", "label": "x", "scores": {"fts": 1}}]


@pytest.mark.parametrize("action", [
    "active_goals", "open_questions", "weak_claims", "pending_approvals",
    "unresolved_contradictions", "stale_derivations",
])
def test_structured_retrieves_forward_limit(runtime, fake_client, action):
    h.handle_retrieve(runtime, {"action": action, "limit": 7, "format": "json"})
    _, payload = only_call(fake_client, "retrieve")
    assert payload["action"] == action and payload["limit"] == 7


def test_stale_derivations_sends_no_agent_id(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "stale_derivations", "agent_id": "hermes", "format": "json"})
    assert "agent_id" not in only_call(fake_client, "retrieve")[1]


def test_preferences_with_query_passes_query_and_k(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "preferences", "query": "hotels", "limit": 5, "format": "json"})
    assert only_call(fake_client, "retrieve")[1] == {"action": "preferences", "query": "hotels", "k": 5, "limit": 5}


def test_preferences_without_query_omits_k(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "preferences", "format": "json"})
    assert only_call(fake_client, "retrieve")[1] == {"action": "preferences"}


def test_layer_requires_layer(runtime, fake_client):
    assert is_error(h.handle_retrieve(runtime, {"action": "layer"}))
    h.handle_retrieve(runtime, {"action": "layer", "layer": "reality", "format": "json"})
    assert only_call(fake_client, "retrieve")[1] == {"action": "layer", "layer": "reality"}


def test_recent_passes_filters(runtime, fake_client):
    h.handle_retrieve(runtime, {
        "action": "recent", "limit": 3, "confidence_min": 0.5, "created_after": 10, "format": "json",
    })
    assert only_call(fake_client, "retrieve")[1] == {
        "action": "recent", "limit": 3, "confidence_min": 0.5, "created_after": 10,
    }


def test_document_index_gets_documents(runtime, fake_client):
    h.handle_retrieve(runtime, {"action": "document_index", "format": "json"})
    assert only_call(fake_client, "get_nodes")[1] == {"node_type": "Document", "limit": 100}


def test_neighborhood_and_path_use_start_end_uid(runtime, fake_client):
    h.handle_retrieve(runtime, {
        "action": "neighborhood", "start_uid": "n1", "max_nodes": 42,
        "exclude_edge_types": ["CONTAINS"], "format": "json",
    })
    assert fake_client.called("traverse")[0][1] == {
        "action": "neighborhood", "start_uid": "n1", "max_nodes": 42, "exclude_edge_types": ["CONTAINS"],
    }
    h.handle_retrieve(runtime, {"action": "path", "start_uid": "a", "end_uid": "b", "format": "json"})
    req = fake_client.called("traverse")[1][1]
    assert req == {"action": "path", "start_uid": "a", "end_uid": "b"}


def test_top_k_paths_maps_max_depth_to_max_hops(runtime, fake_client):
    h.handle_retrieve(runtime, {
        "action": "top_k_paths", "start_uid": "a", "end_uid": "b", "k": 3, "max_depth": 4, "format": "json",
    })
    assert only_call(fake_client, "traverse")[1] == {
        "action": "top_k_paths", "start_uid": "a", "end_uid": "b", "k": 3, "max_hops": 4,
    }


@pytest.mark.parametrize("args", [
    {"action": "path", "start_uid": "a"},
    {"action": "neighborhood"},
    {"action": "chain"},
    {"action": "subgraph"},
    {"action": "top_k_paths", "start_uid": "a"},
])
def test_traversal_requires_uids(runtime, fake_client, args):
    assert is_error(h.handle_retrieve(runtime, args))
    assert fake_client.calls == []


def test_unknown_retrieve_action(runtime):
    assert "Unknown retrieve action" in decoded(h.handle_retrieve(runtime, {"action": "bogus"}))["error"]


def test_client_errors_propagate_to_dispatcher(runtime, fake_client):
    fake_client.responses["retrieve"] = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        h.handle_retrieve(runtime, {"action": "active_goals"})


@needs_render
def test_context_renders_text_by_default(runtime, fake_client):
    fake_client.responses["retrieve_context"] = {
        "graph": {"nodes": [{"uid": "n1", "label": "Kissinger", "node_type": "Person", "props": {}}], "edges": []},
    }
    out = decoded(h.handle_retrieve(runtime, {"action": "context", "query": "Kissinger"}))
    assert isinstance(out, dict) and "Kissinger" in out["result"]


# ── series ────────────────────────────────────────────────────────────


def test_series_window_delegates_exact_payload(runtime, fake_client):
    h.handle_series_query(runtime, {"action": "window", "series_uid": "s1", "from": 10, "to": 20, "limit": 5})
    assert only_call(fake_client, "series")[1] == {
        "action": "window", "series_uid": "s1", "from": 10, "to": 20, "limit": 5,
    }


@pytest.mark.parametrize("args", [
    {"action": "append", "series_uid": "s1", "points": []},
    {"action": "aggregate", "series_uid": "s1", "from": 0, "to": 1},
    {"action": "window", "series_uid": "s1", "from": 0},
    {"action": "latest"},
    {"action": "list_for_entity"},
])
def test_series_rejects_writes_and_missing_coordinates(runtime, fake_client, args):
    assert is_error(h.handle_series_query(runtime, args))
    assert fake_client.calls == []


# ── ingest ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("action,method", [
    ("chunk", "ingest_chunk"), ("document", "ingest_document"), ("session", "ingest_session"),
])
def test_ingest_routes_and_requires_content(runtime, fake_client, action, method):
    assert is_error(h.handle_ingest(runtime, {"action": action}))
    assert fake_client.calls == []
    h.handle_ingest(runtime, {"action": action, "content": "text", "title": "T"})
    args, kwargs = only_call(fake_client, method)
    assert args == ("text",)
    assert kwargs.get("label" if action == "chunk" else "title") == "T"


def test_ingest_strips_ontology_layer(runtime, fake_client):
    h.handle_ingest(runtime, {
        "action": "document", "content": "text",
        "layers": ["reality", "epistemic", "ontology"], "ontology_schema_id": "schema-a",
    })
    kwargs = only_call(fake_client, "ingest_document")[1]
    assert kwargs["layers"] == ["reality", "epistemic"]
    assert kwargs["ontology_schema_id"] == "schema-a"
    assert fake_client.called("_request") == []


@pytest.mark.parametrize("action,path", [("document", "/ingest/document"), ("session", "/ingest/session")])
def test_ontology_alone_means_ontology_only(runtime, fake_client, action, path):
    h.handle_ingest(runtime, {
        "action": action, "content": "text", "layers": ["ontology"],
        "ontology_schema_id": "schema-a", "title": "T", "agent_id": "hermes",
    })
    args, _ = only_call(fake_client, "_request")
    method, sent_path, body = args
    assert (method, sent_path) == ("POST", path)
    assert body == {
        "content": "text", "title": "T", "ontology_schema_id": "schema-a",
        "agent_id": "hermes", "ontology_only": True,
    }
    assert "layers" not in body


@pytest.mark.parametrize("action", ["document", "session", "chunk"])
def test_ontology_without_schema_is_refused(runtime, fake_client, action):
    assert is_error(h.handle_ingest(runtime, {"action": action, "content": "text", "layers": ["ontology"]}))
    assert fake_client.calls == []


def test_session_without_ontology_is_untouched(runtime, fake_client):
    h.handle_ingest(runtime, {"action": "session", "content": "text", "layers": ["reality", "memory"]})
    kwargs = only_call(fake_client, "ingest_session")[1]
    assert kwargs["layers"] == ["reality", "memory"]
    assert "ontology_only" not in kwargs


def test_document_source_alias(runtime, fake_client):
    h.handle_ingest(runtime, {"action": "document", "content": "text", "source": "https://x"})
    assert only_call(fake_client, "ingest_document")[1]["source_uri"] == "https://x"


def test_job_status_by_id_and_list(runtime, fake_client):
    h.handle_ingest(runtime, {"action": "job_status", "job_id": "j1"})
    assert only_call(fake_client, "get_job")[0] == ("j1",)
    fake_client.responses["list_jobs"] = [{"id": "j2"}]
    assert decoded(h.handle_ingest(runtime, {"action": "job_status", "format": "json"})) == [{"id": "j2"}]


@needs_render
def test_job_status_renders_typed_failure(runtime, fake_client):
    code, status = "query_timeout", 504
    job = {
        "id": "failed-job", "title": "Example queries", "status": "failed", "created_at": 1,
        "progress": {"processed_chunks": 2, "total_chunks": 5},
        "error": "legacy diagnostic",
        "error_details": {"message": "Safe terminal reason", "code": code, "status": status, "retriable": False},
    }
    fake_client.responses["list_jobs"] = [job]
    out = decoded(h.handle_ingest(runtime, {"action": "job_status"}))["result"]
    assert "[failed-job]" in out
    assert "2/5 chunks" in out
    assert f"error: Safe terminal reason, code: {code}, status: {status}, retriable: false" in out
    assert "legacy diagnostic" not in out


# ── synthesize ────────────────────────────────────────────────────────


def test_signals_requires_project(runtime, fake_client):
    assert is_error(h.handle_synthesize(runtime, {"action": "signals"}))
    h.handle_synthesize(runtime, {"action": "signals", "project_uid": "p1", "signals": "x", "format": "json"})
    assert only_call(fake_client, "signals") == (("p1",), {"signals": "x", "target_types": None})


def test_run_and_job_status(runtime, fake_client):
    h.handle_synthesize(runtime, {"action": "run", "project_uid": "p1"})
    assert only_call(fake_client, "run_synthesis")[0] == ("p1",)
    assert is_error(h.handle_synthesize(runtime, {"action": "job_status"}))
    h.handle_synthesize(runtime, {"action": "job_status", "job_id": "j1"})
    assert only_call(fake_client, "get_job")[0] == ("j1",)


# ── ontology ──────────────────────────────────────────────────────────


def test_schemas_and_schema(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "schemas"})
    only_call(fake_client, "list_ontology_schemas")
    assert is_error(h.handle_ontology(runtime, {"action": "schema"}))
    h.handle_ontology(runtime, {"action": "schema", "schema_id": "s1"})
    assert only_call(fake_client, "get_ontology_schema")[0] == ("s1",)


def test_query_defaults_cognitive_and_sources(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "query", "query": "clients in NY", "schema_id": "s1", "format": "json"})
    assert only_call(fake_client, "query_ontology")[1] == {
        "query": "clients in NY", "schema_id": "s1",
        "include_cognitive_context": True, "include_sources": True,
    }
    assert is_error(h.handle_ontology(runtime, {"action": "query", "query": "x"}))


def test_search_and_objects(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "search", "query": "acme", "limit": 3, "format": "json"})
    assert only_call(fake_client, "search_domain_objects") == (("acme",), {"limit": 3})
    assert is_error(h.handle_ontology(runtime, {"action": "objects"}))
    h.handle_ontology(runtime, {"action": "objects", "schema_id": "s1", "object_type": "Client", "format": "json"})
    assert only_call(fake_client, "list_domain_objects")[1] == {
        "schema_id": "s1", "object_type": "Client", "limit": None,
    }


def test_object_context_depth_only_when_given(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "object_context", "uid": "o1", "format": "json"})
    h.handle_ontology(runtime, {"action": "object_context", "uid": "o1", "depth": 3, "format": "json"})
    assert fake_client.called("get_domain_object_context") == [(("o1",), {}), (("o1",), {"depth": 3})]


def test_proposals_default_pending(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "proposals"})
    assert only_call(fake_client, "list_ontology_proposals")[1]["status"] == "pending"


def test_approve_reject(runtime, fake_client):
    h.handle_ontology(runtime, {"action": "approve", "proposal_id": "p1", "feedback": "ok"})
    assert only_call(fake_client, "approve_ontology_proposal") == (("p1",), {"feedback": "ok"})
    h.handle_ontology(runtime, {"action": "reject", "proposal_id": "p1", "reason": "bad"})
    assert only_call(fake_client, "reject_ontology_proposal")[0] == ("p1", "bad")
    assert is_error(h.handle_ontology(runtime, {"action": "approve"}))


def test_link_requires_endpoints(runtime, fake_client):
    assert is_error(h.handle_ontology(runtime, {"action": "link", "from_uid": "a"}))
    assert fake_client.calls == []
    h.handle_ontology(runtime, {
        "action": "link", "from_uid": "a", "to_uid": "b", "relation_type": "WORKS_AT", "agent_id": "hermes",
    })
    assert only_call(fake_client, "link_domain_objects")[1] == {
        "from_uid": "a", "to_uid": "b", "relation_type": "WORKS_AT", "agent_id": "hermes",
    }


def test_extract_requires_sources(runtime, fake_client):
    assert is_error(h.handle_ontology(runtime, {"action": "extract", "schema_id": "s1"}))
    h.handle_ontology(runtime, {"action": "extract", "schema_id": "s1", "source_uids": ["u1"]})
    assert only_call(fake_client, "extract_ontology")[1] == {"ontology_schema_id": "s1", "source_uids": ["u1"]}
