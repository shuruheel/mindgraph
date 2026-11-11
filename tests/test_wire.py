"""The provider over real HTTP: the SDK, the governance client and the capture
queue against a MindGraph stand-in on a socket. No Hermes needed; the same
scenarios run inside real Hermes in ``tests/host``."""

from __future__ import annotations

import json

import pytest
from hermes_mindgraph_plugin.provider import MindGraphMemoryProvider
from support.fake_mindgraph import FakeMindGraph


@pytest.fixture
def server():
    fake = FakeMindGraph().start()
    yield fake
    fake.stop()


@pytest.fixture
def provider(tmp_path, monkeypatch, server):
    monkeypatch.setenv("MINDGRAPH_API_KEY", "mg_wire_test")
    monkeypatch.setenv("MINDGRAPH_BASE_URL", server.url)
    instance = MindGraphMemoryProvider()
    instance.initialize("wire-session", hermes_home=str(tmp_path / "profile"), platform="cli")
    yield instance
    instance.shutdown()


def test_a_turn_is_captured_with_its_session_and_receipt(provider, server):
    provider.sync_turn("We chose Postgres.", "Noted.", session_id="wire-session")
    provider.on_pre_compress([])
    (transcript,) = server.ingested()
    assert transcript["content"] == "User: We chose Postgres.\n\nAssistant: Noted."
    assert transcript["session_uid"] == "session-wire-session"
    assert provider._capture.status()["last_delivery"]["job_id"] == "job-1"
    assert provider._capture.status()["last_delivery"]["document_uid"] == "doc-1"


def test_a_dropped_connection_after_the_server_stored_the_batch_is_reconciled(provider, server):
    server.failures["/ingest/session"] = ["drop"]
    provider.sync_turn("Stored, answer lost.", "ok", session_id="wire-session")
    provider.on_pre_compress([])
    assert provider._capture.status()["pending_batches"] == 1
    provider.on_session_end([])
    assert len(server.ingested()) == 1 and provider._capture.status()["pending_batches"] == 0
    assert provider._capture.status()["last_delivery"]["job_id"] == "job-1"


def test_a_server_error_is_retried_and_delivered_once(provider, server):
    server.failures["/ingest/session"] = [503]
    provider.sync_turn("Retried.", "ok", session_id="wire-session")
    provider.on_pre_compress([])
    provider.on_session_end([])
    assert len(server.ingested()) == 1
    assert len(server.bodies("/ingest/session")) == 2 and len(server.bodies("/jobs")) == 1


def test_a_rejected_batch_is_parked_and_reported(provider, server):
    server.failures["/ingest/session"] = [400]
    provider.sync_turn("Refused.", "ok", session_id="wire-session")
    provider.on_pre_compress([])
    provider.on_session_end([])
    assert len(server.bodies("/ingest/session")) == 1
    status = json.loads(provider.handle_tool_call("mindgraph_memory", {"action": "status"}))
    assert status["capture"]["failed_batches"] == 1
    assert "capture_batches_parked" in {entry["code"] for entry in status["degradation"]}


def test_recall_sends_the_bounded_request_and_injects_relevant_items(provider, server):
    server.context = {
        "graph": {
            "nodes": [
                {"uid": "d1", "label": "Voya pilot budget is $8,000", "node_type": "Decision", "props": {}},
                {"uid": "x1", "label": "Quarterly roadmap", "node_type": "Decision", "props": {}},
            ],
            "edges": [],
        },
        "chunks": [],
        "articles": [],
    }
    text = provider.prefetch("What is the Voya pilot budget?", session_id="wire-session")
    assert "Voya pilot budget is $8,000" in text and "Quarterly roadmap" not in text
    (request,) = server.bodies("/retrieve/context")
    assert request == {
        "query": "voya pilot budget",
        "node_limit": 10,
        "chunk_limit": 0,
        "article_limit": 0,
        "include_graph": True,
        "graph_expansion_limit": 3,
        "graph_max_depth": 2,
    }


def test_a_tool_call_is_governed_then_sent(provider, server):
    result = json.loads(provider.handle_tool_call("mindgraph_remember", {"action": "remember", "text": "Prefers tea"}))
    assert "error" not in result
    paths = [path for _, path, _ in server.requests]
    assert paths.index("/agent/governance") < paths.index("/memory/remember")
