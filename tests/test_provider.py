"""Hermes lifecycle: profile isolation, recall, capture, mirroring, routing."""

from __future__ import annotations

import json

import pytest
from mindgraph import MindGraphError

import hermes_mindgraph_plugin as plugin
from hermes_mindgraph_plugin import dispatch
from hermes_mindgraph_plugin import provider as provider_mod
from hermes_mindgraph_plugin.governance import GateResult
from hermes_mindgraph_plugin.provider import MindGraphMemoryProvider, builtin_memory_custom_id, topic_query

from conftest import FakeClient


class Ctx:
    def __init__(self) -> None:
        self.providers = []

    def register_memory_provider(self, provider) -> None:
        self.providers.append(provider)


class AllowAll:
    def __init__(self) -> None:
        self.checked = []

    def check(self, name, args):
        self.checked.append((name, args))
        return GateResult(True)


@pytest.fixture
def secrets(monkeypatch):
    values = {"MINDGRAPH_API_KEY": "mg_test"}
    monkeypatch.setattr(provider_mod, "get_secret", lambda name, default=None: values.get(name, default))
    return values


def make_provider(secrets, *, session_id="hermes-sess", **kwargs):
    provider = MindGraphMemoryProvider()
    provider.initialize(session_id, hermes_home="/tmp/profile", platform="cli", **kwargs)
    fake = FakeClient()
    fake.responses["session"] = lambda **body: {"uid": "session-uid-1"} if body["action"] == "open" else {}
    provider._rt.client = fake
    provider._gate = AllowAll()
    return provider, fake


def test_register_hands_hermes_a_new_instance_per_load():
    first, second = Ctx(), Ctx()
    plugin.register(first)
    plugin.register(second)
    assert first.providers[0] is not second.providers[0]


def test_availability_reads_the_profile_secret_without_network(secrets):
    assert MindGraphMemoryProvider().is_available()
    secrets.pop("MINDGRAPH_API_KEY")
    provider = MindGraphMemoryProvider()
    assert not provider.is_available()
    assert "MINDGRAPH_API_KEY" in provider.unavailable_reason()


def test_each_instance_binds_its_own_profile(monkeypatch):
    scopes = iter([{"MINDGRAPH_API_KEY": "key-a", "MINDGRAPH_AGENT_ID": "agent-a"},
                   {"MINDGRAPH_API_KEY": "key-b", "MINDGRAPH_AGENT_ID": "agent-b"}])
    current = {}
    monkeypatch.setattr(provider_mod, "get_secret", lambda name, default=None: current.get(name, default))
    providers = []
    for scope in scopes:
        current.clear()
        current.update(scope)
        provider = MindGraphMemoryProvider()
        provider.initialize("s", hermes_home="/tmp/x", platform="cli")
        providers.append(provider)
    assert [p._rt.api_key for p in providers] == ["key-a", "key-b"]
    assert [p._rt.agent_id for p in providers] == ["agent-a", "agent-b"]
    assert providers[0]._rt.client is not providers[1]._rt.client
    assert providers[0]._gate is not providers[1]._gate


def test_system_prompt_block_is_static_and_makes_no_calls(secrets):
    provider, fake = make_provider(secrets)
    block = provider.system_prompt_block()
    assert block == provider.system_prompt_block()
    assert "orient → answer → preserve" in block
    assert "mindgraph_code" not in block
    assert fake.calls == []


def test_topic_query_keeps_discriminating_terms():
    assert topic_query("What did we decide about the Voya pilot pricing?") == "decide voya pilot pricing"
    assert topic_query("ok") == "ok"
    assert len(topic_query(" ".join(f"term{i}" for i in range(30))).split()) == 8


def test_prefetch_recalls_topic_context_and_the_first_turn_brief(secrets):
    provider, fake = make_provider(secrets)
    fake.responses["plan"] = {"status": "selected", "task": {"uid": "task-1", "label": "Ship B5 probe", "props": {}}}
    fake.responses["retrieve_context"] = {
        "graph": {"nodes": [{"uid": "n1", "label": "Voya pilot", "node_type": "Project", "props": {}}], "edges": []},
        "chunks": [],
        "articles": [],
    }
    first = provider.prefetch("What did we decide about the Voya pilot pricing?", session_id="hermes-sess")
    assert first.startswith("## MindGraph context")
    assert "Voya pilot" in first
    (plan_args, plan_kwargs), = fake.called("plan")
    assert plan_kwargs["action"] == "resume_work"
    ((query,), context_kwargs), = fake.called("retrieve_context")
    assert query == "decide voya pilot pricing"
    assert context_kwargs["node_limit"] == provider_mod.PREFETCH_LIMIT

    provider.prefetch("And the Voya pilot timeline?", session_id="hermes-sess")
    assert len(fake.called("plan")) == 1, "the open-work brief is once per conversation"


def test_prefetch_injects_nothing_for_an_empty_recall_or_a_failure(secrets):
    provider, fake = make_provider(secrets)
    fake.responses["plan"] = {"status": "no_eligible_work"}
    fake.responses["retrieve_context"] = {"graph": {"nodes": [], "edges": []}, "chunks": [], "articles": []}
    assert provider.prefetch("Tell me about quantum gardening", session_id="hermes-sess") == ""
    fake.responses["retrieve_context"] = MindGraphError("busy", 503, {"code": "query_admission_busy"})
    assert provider.prefetch("Tell me about quantum gardening again", session_id="hermes-sess") == ""


def test_turns_are_buffered_and_ingested_once(secrets):
    provider, fake = make_provider(secrets)
    provider.on_turn_start(1, "hi", model="hermes-4")
    provider.sync_turn("We chose Postgres for the ledger.", "Noted: Postgres for the ledger.", session_id="hermes-sess")
    provider.sync_turn("And Redis for the cache.", "Got it.", session_id="hermes-sess")
    assert fake.called("ingest_session") == []

    provider.on_pre_compress([])
    (opened,) = [kw for _, kw in fake.called("session") if kw["action"] == "open"]
    assert opened["harness"] == "hermes"
    assert opened["harness_session_id"] == "hermes-sess"
    assert opened["model"] == "hermes-4"
    ((content,), kwargs), = fake.called("ingest_session")
    assert "User: We chose Postgres for the ledger." in content
    assert "Assistant: Got it." in content
    assert kwargs["session_uid"] == "session-uid-1"

    provider.on_session_end([])
    assert len(fake.called("ingest_session")) == 1, "nothing new to send"
    assert [kw["action"] for _, kw in fake.called("session")] == ["open", "close"]


def test_a_large_buffer_flushes_without_waiting_for_session_end(secrets):
    provider, fake = make_provider(secrets)
    provider.sync_turn("x" * provider_mod.FLUSH_CHARS, "ok", session_id="hermes-sess")
    assert len(fake.called("ingest_session")) == 1


def test_a_failed_ingest_keeps_the_turns_for_the_next_flush(secrets):
    provider, fake = make_provider(secrets)
    fake.responses["ingest_session"] = MindGraphError("down", 503, {})
    provider.sync_turn("first", "reply", session_id="hermes-sess")
    provider.on_pre_compress([])
    fake.responses["ingest_session"] = {"job_id": "j1"}
    provider.sync_turn("second", "reply", session_id="hermes-sess")
    provider.on_session_end([])
    content = fake.called("ingest_session")[-1][0][0]
    assert content.index("first") < content.index("second")


@pytest.mark.parametrize("context", ["subagent", "cron", "flush"])
def test_non_primary_contexts_never_write(secrets, context):
    provider, fake = make_provider(secrets, agent_context=context)
    provider.sync_turn("secret plan", "ok", session_id="hermes-sess")
    provider.on_memory_write("add", "memory", "User prefers tea")
    provider.on_session_end([])
    assert fake.calls == []


def test_auto_capture_can_be_turned_off(secrets):
    secrets["MINDGRAPH_AUTO_CAPTURE"] = "off"
    provider, fake = make_provider(secrets)
    provider.sync_turn("hello", "hi", session_id="hermes-sess")
    provider.on_session_end([])
    assert fake.called("ingest_session") == []


def test_builtin_memory_writes_are_mirrored_by_content_key(secrets):
    provider, fake = make_provider(secrets)
    provider.on_memory_write("add", "user", "Prefers tea")
    provider.on_memory_write("replace", "user", "Prefers green tea", {"previous_content": "Prefers tea"})
    provider.on_memory_write("remove", "user", "", {"previous_content": "Prefers green tea"})
    provider.on_memory_write("remove", "user", "", {})  # identity unknown: no guessed forget

    remembered = fake.called("remember")
    assert [args[0] for args, _ in remembered] == ["Prefers tea", "Prefers green tea"]
    assert remembered[0][1]["custom_id"] == builtin_memory_custom_id("user", "Prefers tea")
    forgotten = [kw["custom_id"] for _, kw in fake.called("forget")]
    assert forgotten == [
        builtin_memory_custom_id("user", "Prefers tea"),
        builtin_memory_custom_id("user", "Prefers green tea"),
    ]


def test_a_failed_forget_does_not_block_the_replacement(secrets):
    provider, fake = make_provider(secrets)
    fake.responses["forget"] = MindGraphError("not found", 404, {"code": "not_found"})
    provider.on_memory_write("replace", "memory", "new text", {"previous_content": "old text"})
    assert [args[0] for args, _ in fake.called("remember")] == ["new text"]


def test_session_switch_flushes_under_the_old_session_and_rebinds(secrets):
    provider, fake = make_provider(secrets)
    provider.sync_turn("before switch", "ok", session_id="hermes-sess")
    provider.on_session_switch("hermes-sess-2", reset=True)
    assert fake.called("ingest_session")[0][1]["title"] == "Hermes session hermes-sess"
    assert provider._rt.session_id == "hermes-sess-2"
    closes = [kw for _, kw in fake.called("session") if kw["action"] == "close"]
    assert len(closes) == 1, "the old conversation's Session is closed at the switch"
    provider.sync_turn("after switch", "ok", session_id="hermes-sess-2")
    provider.on_session_end([])
    opens = [kw["harness_session_id"] for _, kw in fake.called("session") if kw["action"] == "open"]
    assert opens == ["hermes-sess", "hermes-sess-2"]


def test_tool_calls_pass_the_governance_gate(secrets):
    provider, fake = make_provider(secrets)
    provider._gate = type("Deny", (), {"check": lambda self, n, a: GateResult(False, "Denied by policy X")})()
    result = json.loads(provider.handle_tool_call("mindgraph_capture", {"action": "entity", "label": "Ada"}))
    assert result["error"] == "Denied by policy X"
    assert fake.calls == []


def test_tool_schemas_are_the_mcp_general_profile(secrets):
    provider, _ = make_provider(secrets)
    names = [schema["name"] for schema in provider.get_tool_schemas()]
    assert names[:11] == [tool["name"] for tool in dispatch.contract()["tools"]]
    assert "mindgraph_code" not in names and "mindgraph_sync" not in names
    for schema in provider.get_tool_schemas():
        assert set(schema) >= {"name", "description", "parameters"}
        assert "invocation_context" not in schema["parameters"].get("properties", {})


def test_tool_list_is_fixed_before_initialize(secrets):
    """Hermes routes by the names listed before initialize(); the list must not change after."""
    provider = MindGraphMemoryProvider()
    before = [schema["name"] for schema in provider.get_tool_schemas()]
    provider.initialize("s", hermes_home="/tmp/profile", platform="cli")
    assert [schema["name"] for schema in provider.get_tool_schemas()] == before


def test_undo_drops_unflushed_turns_so_retracted_text_never_persists(secrets):
    provider, fake = make_provider(secrets)
    provider.sync_turn("keep me?", "ok", session_id="hermes-sess")
    provider.sync_turn("my password is hunter2", "noted", session_id="hermes-sess")
    provider.on_session_switch("hermes-sess", rewound=True)
    provider.on_session_end([])
    assert fake.called("ingest_session") == []


def test_a_turn_queued_before_a_switch_stays_with_its_own_conversation(secrets):
    provider, fake = make_provider(secrets)
    provider.on_session_switch("hermes-sess-2")
    # The manager worker runs the old conversation's sync_turn after the switch.
    provider.sync_turn("late turn", "ok", session_id="hermes-sess")
    provider.sync_turn("new turn", "ok", session_id="hermes-sess-2")
    provider.on_session_end([])
    by_title = {kw["title"]: args[0] for args, kw in fake.called("ingest_session")}
    assert "late turn" in by_title["Hermes session hermes-sess"]
    assert "late turn" not in by_title["Hermes session hermes-sess-2"]
    opened = [kw["harness_session_id"] for _, kw in fake.called("session") if kw["action"] == "open"]
    closed = [kw["session_uid"] for _, kw in fake.called("session") if kw["action"] == "close"]
    assert sorted(opened) == ["hermes-sess", "hermes-sess-2"]
    assert len(closed) == 2, "every Session this provider opened is closed"


def test_a_late_prefetch_cannot_overwrite_the_next_turns_recall_status(secrets, monkeypatch):
    provider, fake = make_provider(secrets)
    monkeypatch.setattr(provider_mod, "RecallStatus", lambda provider_label, count: count)
    fake.responses["plan"] = {"status": "no_eligible_work"}
    fake.responses["retrieve_context"] = {"graph": {"nodes": [], "edges": []}, "chunks": [], "articles": []}

    hit = {"graph": {"nodes": [{"uid": "n1", "label": "Hit", "node_type": "Project", "props": {}}], "edges": []},
           "chunks": [], "articles": []}
    empty = {"graph": {"nodes": [], "edges": []}, "chunks": [], "articles": []}
    overtaken = []

    def slow_then_overtaken(*args, **kwargs):
        if not overtaken:  # the newer turn's prefetch runs (and finds nothing) while this one is in flight
            overtaken.append(True)
            assert provider.prefetch("a newer message arrives meanwhile", session_id="hermes-sess") == ""
            return hit
        return empty

    fake.responses["retrieve_context"] = slow_then_overtaken
    stale = provider.prefetch("the slow original message", session_id="hermes-sess")
    assert "Hit" in stale, "the late call still returns its own text to its own caller"
    assert provider.recall_status() is None, "but it cannot publish over the newer turn's status"


def test_a_failed_open_work_brief_is_retried(secrets):
    provider, fake = make_provider(secrets)
    fake.responses["plan"] = MindGraphError("timeout", 504, {"code": "query_timeout"})
    provider.prefetch("first message here", session_id="hermes-sess")
    fake.responses["plan"] = {"status": "no_eligible_work"}
    provider.prefetch("second message here", session_id="hermes-sess")
    provider.prefetch("third message here", session_id="hermes-sess")
    assert len(fake.called("plan")) == 2
