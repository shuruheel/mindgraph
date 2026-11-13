"""The plugin inside real Hermes: its loader, its MemoryProvider ABC and its
MemoryManager, talking HTTP to a MindGraph stand-in.

Run with a hermes-agent checkout installed and ``HERMES_HOST_TESTS=1`` (the
``host`` CI job pins the commit). Everything here goes through the manager,
the way an agent does; nothing calls the provider's methods directly except
to simulate a process that died.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_HOST_TESTS") != "1", reason="needs a real Hermes checkout (HERMES_HOST_TESTS=1)"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILES = ("*.py", "plugin.yaml", "mcp_contract.json", "pyproject.toml", "py.typed")


def install_plugin(home: Path) -> None:
    """What ``hermes plugins install`` leaves behind: the plugin's files under the profile."""
    target = home / "plugins" / "mindgraph"
    target.mkdir(parents=True, exist_ok=True)
    for pattern in PLUGIN_FILES:
        for source in REPO_ROOT.glob(pattern):
            shutil.copy2(source, target / source.name)


@pytest.fixture
def server():
    from support.fake_mindgraph import FakeMindGraph

    fake = FakeMindGraph().start()
    yield fake
    fake.stop()


@pytest.fixture
def home(tmp_path, monkeypatch, server):
    profile = tmp_path / "hermes-home"
    profile.mkdir()
    install_plugin(profile)
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.setenv("MINDGRAPH_API_KEY", "mg_host_test_key")
    monkeypatch.setenv("MINDGRAPH_BASE_URL", server.url)
    for name in ("MINDGRAPH_AUTO_CAPTURE", "MINDGRAPH_GOVERNANCE", "MINDGRAPH_RECALL", "MINDGRAPH_PROJECT_UID",
                 "MINDGRAPH_RECALL_DEADLINE_MS", "MINDGRAPH_ORG_ID", "MINDGRAPH_AGENT_ID"):
        monkeypatch.delenv(name, raising=False)
    return profile


def boot(home: Path, session_id: str = "host-session", **init):
    """A fresh agent's memory stack: Hermes loads the provider, the manager binds it."""
    from agent.memory_manager import MemoryManager
    from plugins.memory import load_memory_provider

    provider = load_memory_provider("mindgraph")
    assert provider is not None, "Hermes's loader did not find or could not load the plugin"
    manager = MemoryManager()
    manager.add_provider(provider)
    manager.initialize_all(session_id=session_id, platform="cli", hermes_home=str(home), **init)
    return manager, provider


def queue_counts(home: Path) -> dict[str, int]:
    db = sqlite3.connect(home / "mindgraph" / "capture.db")
    try:
        counts = dict(db.execute("SELECT state, COUNT(*) FROM batches GROUP BY state").fetchall())
        counts["open_parts"] = db.execute("SELECT COUNT(*) FROM parts WHERE batch_id IS NULL").fetchone()[0]
        return counts
    finally:
        db.close()


def node(uid, label, summary=None, kind="Decision", **extra):
    return {"uid": uid, "label": label, "node_type": kind, "summary": summary, "props": {}, **extra}


def graph(*nodes):
    return {"graph": {"nodes": list(nodes), "edges": []}, "chunks": [], "articles": []}


# ── Loading and contract ───────────────────────────────────────────────────


def test_hermes_loads_the_plugin_and_it_satisfies_the_real_contract(home):
    from agent.memory_provider import PRE_COMPRESS_CHECKPOINT_API_VERSION, MemoryProvider

    manager, provider = boot(home)
    assert isinstance(provider, MemoryProvider), "a subclass of the real ABC, with every abstract method"
    assert provider.name == "mindgraph" and provider.is_available()
    assert len(manager.get_all_tool_names()) == 11
    assert all(manager.has_tool(name) for name in ("mindgraph_memory", "mindgraph_retrieve", "mindgraph_remember"))
    assert "orient → answer → preserve" in manager.build_system_prompt()
    assert manager.supports_pre_compress_checkpoint(PRE_COMPRESS_CHECKPOINT_API_VERSION)
    manager.shutdown_all()


def test_each_load_is_a_new_instance_bound_to_its_own_profile(home, tmp_path, server, monkeypatch):
    other = tmp_path / "second-home"
    other.mkdir()
    install_plugin(other)
    first, first_provider = boot(home, "session-a")
    first.sync_all("Profile A: the ledger is on Postgres.", "Noted.", session_id="session-a")
    assert first.flush_pending(10)

    # Hermes runs a profile's hooks only from that profile's home.
    monkeypatch.setenv("HERMES_HOME", str(other))
    second, second_provider = boot(other, "session-b")
    assert first_provider is not second_provider
    second.sync_all("Profile B: the cache is Redis.", "Noted.", session_id="session-b")
    assert second.flush_pending(10)
    assert queue_counts(home)["open_parts"] == 2 and queue_counts(other)["open_parts"] == 2
    second.shutdown_all()

    monkeypatch.setenv("HERMES_HOME", str(home))
    first.shutdown_all()
    titles = sorted(body["title"].split(" · ")[0] for body in server.ingested())
    assert titles == ["Hermes session session-a", "Hermes session session-b"]
    assert "Redis" not in (home / "mindgraph" / "capture.db").read_bytes().decode(errors="ignore")


# ── A conversation ─────────────────────────────────────────────────────────


def test_a_turn_recalls_captures_and_reports_through_the_manager(home, server):
    server.context = graph(
        node("d1", "Voya pilot budget is $8,000", "Agreed with finance.", stated_at=["2026-10-12"]),
        node("x1", "Quarterly roadmap", "Unrelated planning note"),
    )
    server.work = {"status": "selected", "task": {"uid": "t1", "label": "Ship the Voya pilot", "props": {}}}
    manager, _ = boot(home)

    manager.on_turn_start(1, "What is the Voya pilot budget?", model="hermes-4")
    context = manager.prefetch_all("What is the Voya pilot budget?", session_id="host-session")
    assert "Voya pilot budget is $8,000" in context and "stated 2026-10-12" in context
    assert "Ship the Voya pilot" in context, "the open-work brief rides the first message"
    assert "Quarterly roadmap" not in context, "below the relevance floor"
    assert "recalled 2 memories" in manager.describe_recall()
    (request,) = server.bodies("/retrieve/context")
    assert request["query"] == "voya pilot budget"

    manager.sync_all("What is the Voya pilot budget?", "It is $8,000.", session_id="host-session")
    assert manager.flush_pending(10)
    assert server.ingested() == [], "a turn is queued, not sent, until a flush point"
    manager.on_pre_compress([{"role": "user", "content": "What is the Voya pilot budget?"}])
    (transcript,) = server.ingested()
    assert transcript["content"] == "User: What is the Voya pilot budget?\n\nAssistant: It is $8,000."
    assert transcript["session_uid"] == "session-host-session"
    assert transcript["agent_id"] == "hermes"
    opened = [body for body in server.bodies("/memory/session") if body["action"] == "open"]
    assert opened[0]["harness"] == "hermes" and opened[0]["model"] == "hermes-4"

    manager.on_session_end([])
    manager.shutdown_all()
    assert len(server.ingested()) == 1, "nothing is sent twice"
    assert [b["action"] for b in server.bodies("/memory/session")] == ["open", "close"]
    assert queue_counts(home) == {"delivered": 1, "open_parts": 0}


def test_secrets_hermes_redacts_never_reach_the_queue_or_the_server(home, server):
    manager, _ = boot(home)
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"
    manager.sync_all(f"Use the key {secret} for the deploy.", "Stored for this session.", session_id="host-session")
    assert manager.flush_pending(10)
    raw = (home / "mindgraph" / "capture.db").read_bytes()
    assert secret.encode() not in raw, "Hermes scrubs provider egress before sync_turn"
    manager.on_session_end([])
    manager.shutdown_all()
    assert secret not in json.dumps(server.ingested())


def test_a_slash_skill_turn_captures_the_instruction_not_the_skill_body(home, server):
    manager, _ = boot(home)
    manager.sync_all("ok", "Sure.", session_id="host-session")
    manager.sync_all("Plan the Voya rollout for March.", "Drafted the plan.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    assert "Plan the Voya rollout for March." in server.ingested()[0]["content"]


def test_a_follow_up_without_a_subject_recalls_on_the_conversation(home, server):
    manager, _ = boot(home)
    manager.prefetch_all("Let's review the Voya pilot budget", session_id="host-session")
    manager.on_turn_start(2, "What did we decide?", previous_message="Let's review the Voya pilot budget")
    manager.prefetch_all("What did we decide?", session_id="host-session")
    queries = [body["query"] for body in server.bodies("/retrieve/context")]
    assert queries == ["review voya pilot budget", "decide review voya pilot budget"]
    manager.shutdown_all()


def test_trivial_and_fork_prompts_cost_no_request(home, server):
    manager, _ = boot(home, agent_context="subagent")
    assert manager.prefetch_all("What is the Voya pilot budget?", session_id="host-session") == ""
    manager.sync_all("A fork's turn", "ok", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    assert server.bodies("/retrieve/context") == [] and server.ingested() == []


def test_a_slow_recall_does_not_hold_the_turn(home, server, monkeypatch):
    monkeypatch.setenv("MINDGRAPH_RECALL_DEADLINE_MS", "300")
    server.context = graph(node("d1", "Voya pilot budget is $8,000"))
    server.delays["/retrieve/context"] = 1.5
    manager, _ = boot(home)
    started = time.monotonic()
    assert manager.prefetch_all("What is the Voya pilot budget?", session_id="host-session") == ""
    assert time.monotonic() - started < 1.2, "bounded by the recall deadline, not Hermes's 8 s timeout"
    server.delays.clear()
    time.sleep(1.6)  # the late answer lands and is kept
    kept = manager.prefetch_all("What is the Voya pilot budget?", session_id="host-session")
    assert "Voya pilot budget is $8,000" in kept
    assert len(server.bodies("/retrieve/context")) == 1, "served from the kept answer"
    manager.shutdown_all()


def test_a_failed_recall_is_retried_by_hermes_background_prefetch(home, server):
    server.context = graph(node("d1", "Voya pilot budget is $8,000"))
    server.failures["/retrieve/context"] = [503, 503]  # the SDK retries a read once
    manager, _ = boot(home)
    assert manager.prefetch_all("What is the Voya pilot budget?", session_id="host-session") == ""
    manager.queue_prefetch_all("What is the Voya pilot budget?", session_id="host-session")
    assert manager.flush_pending(10)
    assert server.wait_for(lambda: len(server.bodies("/retrieve/context")) == 3), "the retry ran, on its own thread"
    time.sleep(0.2)
    assert "Voya pilot budget is $8,000" in manager.prefetch_all(
        "What is the Voya pilot budget?", session_id="host-session"
    )
    assert len(server.bodies("/retrieve/context")) == 3, "answered from the retry's kept result"
    manager.shutdown_all()


# ── Durability ─────────────────────────────────────────────────────────────


def test_turns_survive_a_process_that_dies_without_shutting_down(home, server):
    manager, provider = boot(home, "crashed-session")
    manager.sync_all("We agreed to ship on Friday.", "Friday it is.", session_id="crashed-session")
    assert manager.flush_pending(10)
    assert server.ingested() == []
    provider._capture.close()  # the process is gone: no session end, no shutdown, no flush

    survivor, _ = boot(home, "next-session")
    assert server.wait_for(lambda: len(server.ingested()) == 1), "the next start delivers what was left"
    (transcript,) = server.ingested()
    assert "We agreed to ship on Friday." in transcript["content"]
    assert transcript["title"].startswith("Hermes session crashed-session · ")
    survivor.shutdown_all()


def test_an_outage_delays_capture_and_loses_nothing(home, server):
    manager, _ = boot(home)
    server.failures["/ingest/session"] = [503, 503]
    manager.sync_all("First decision: Postgres.", "Noted.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_pre_compress([])
    manager.sync_all("Second decision: Redis.", "Noted.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_pre_compress([])
    assert server.ingested() == [] and queue_counts(home)["sealed"] == 2

    manager.on_session_end([])  # the server is back
    manager.shutdown_all()
    contents = [body["content"] for body in server.ingested()]
    assert len(contents) == 2 and "First decision" in contents[0] and "Second decision" in contents[1]
    assert queue_counts(home) == {"delivered": 2, "open_parts": 0}


def test_a_request_that_landed_but_lost_its_answer_is_not_ingested_twice(home, server):
    manager, _ = boot(home)
    server.failures["/ingest/session"] = ["drop"]
    manager.sync_all("Stored despite the dropped connection.", "ok", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_pre_compress([])
    assert len(server.ingested()) == 1 and queue_counts(home)["sealed"] == 1, "the server has it; the client cannot know"

    manager.on_session_end([])
    manager.shutdown_all()
    assert len(server.ingested()) == 1, "found among the server's jobs by its tag, so not resent"
    assert queue_counts(home) == {"delivered": 1, "open_parts": 0}
    assert len(server.bodies("/jobs")) == 1


def test_a_server_restart_between_the_send_and_the_retry_does_not_duplicate(home, server):
    manager, _ = boot(home)
    server.failures["/ingest/session"] = ["drop"]
    manager.sync_all("Stored, then the server was redeployed.", "ok", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_pre_compress([])
    server.restart()  # its in-memory job list is gone; the transcript Document is not
    manager.on_session_end([])
    manager.shutdown_all()
    assert len(server.ingested()) == 1
    assert queue_counts(home) == {"delivered": 1, "open_parts": 0}


def test_a_turn_is_committed_while_an_earlier_one_is_still_being_sent(home, server):
    server.delays["/ingest/session"] = 1.5
    manager, _ = boot(home)
    manager.sync_all("x" * 24_000, "A turn big enough to flush on its own.", session_id="host-session")
    manager.sync_all("The turn right behind it.", "ok", session_id="host-session")
    started = time.monotonic()
    assert manager.flush_pending(10)
    assert time.monotonic() - started < 1.0, "Hermes's one background worker is not held by the send"
    assert queue_counts(home)["open_parts"] == 2
    server.delays.clear()
    manager.on_session_end([])
    manager.shutdown_all()
    assert len(server.ingested()) == 2


def test_compression_does_not_archive_the_same_turns_under_the_new_session_id(home, server):
    manager, _ = boot(home, "before-compression")
    manager.sync_all("Rotate the signing key tonight.", "Scheduled for 23:00.", session_id="before-compression")
    assert manager.flush_pending(10)
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    manager.on_session_switch(
        "after-compression", parent_session_id="before-compression", reset=False, reason="compression"
    )
    # The next compression is handed the tail the last one kept verbatim.
    manager.on_pre_compress(TRANSCRIPT[-1:], evidence_messages=evidence(TRANSCRIPT[-1:]), require_checkpoint=True)
    manager.on_session_end([])
    manager.shutdown_all()
    everything = "\n".join(body["content"] for body in server.ingested())
    assert everything.count("Scheduled for 23:00.") == 1 and everything.count("Rotate the signing key tonight.") == 1


def test_status_tells_the_model_what_is_queued(home, server):
    manager, _ = boot(home)
    server.failures["/ingest/session"] = [503]
    manager.sync_all("Waiting on the server.", "ok", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_pre_compress([])
    status = json.loads(manager.handle_tool_call("mindgraph_memory", {"action": "status"}))
    assert status["capture"]["durable"] is True and status["capture"]["pending_batches"] == 1
    assert "capture_delivery_delayed" in {entry["code"] for entry in status["degradation"]}
    assert status["integration"]["automatic_capture"] and status["integration"]["automatic_delivery"]
    manager.shutdown_all()


def test_undo_keeps_retracted_turns_from_ever_being_sent(home, server):
    manager, _ = boot(home)
    manager.sync_all("My password is hunter2-do-not-store", "Noted.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_switch("host-session", rewound=True)
    manager.on_session_end([])
    manager.shutdown_all()
    assert server.ingested() == []


def test_undo_wins_even_when_hermes_runs_it_before_the_turns_own_sync(home, server):
    """Hermes calls the rewind hook inline and does not drain its worker first."""
    manager, _ = boot(home)
    manager.on_turn_start(1, "My password is hunter2-do-not-store")
    manager.on_session_switch("host-session", rewound=True)
    manager.sync_all("My password is hunter2-do-not-store", "Noted.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    assert server.ingested() == []


def test_queued_pre_undo_turn_is_rejected_after_a_fast_new_turn_starts(home, server):
    manager, _ = boot(home)
    entered, release = threading.Event(), threading.Event()

    def hold_worker():
        entered.set()
        assert release.wait(5)

    manager._submit_background(hold_worker)
    assert entered.wait(5)
    try:
        manager.on_turn_start(1, "Repeat this")
        manager.sync_all("Repeat this", "obsolete response", session_id="host-session")
        manager.on_session_switch("host-session", rewound=True)
        manager.on_turn_start(1, "Repeat this")
        manager.sync_all("Repeat this", "corrected response", session_id="host-session")
    finally:
        release.set()
    assert manager.flush_pending(5)
    manager.on_session_end([])
    manager.shutdown_all()
    content = "\n".join(body["content"] for body in server.ingested())
    assert "corrected response" in content and "obsolete response" not in content


def test_delegation_and_multiple_authors_reach_the_server(home, server):
    manager, _ = boot(home)
    manager.on_turn_start(1, "I prefer tea", author_id="alice", author_name="Alice", author_is_bot=False)
    manager.sync_all("I prefer tea", "Noted", session_id="host-session",
                     turn_author={"id": "alice", "name": "Alice", "is_bot": False})
    manager.on_turn_start(2, "I prefer coffee", author_id="bob", author_name="Bob", author_is_bot=False)
    manager.sync_all("I prefer coffee", "Noted", session_id="host-session",
                     turn_author={"id": "bob", "name": "Bob", "is_bot": False})
    manager.on_delegation("Inspect backups", "Last backup verified", child_session_id="child-1")
    assert manager.flush_pending(5)
    manager.on_session_end([])
    manager.shutdown_all()
    content = "\n".join(body["content"] for body in server.ingested())
    assert '"id": "alice"' in content and '"id": "bob"' in content
    assert 'child_session_id="child-1"' in content and "Delegated result: " in content
    assert "Last backup verified" in content


def test_required_checkpoint_overflow_blocks_the_host_and_preserves_prior_evidence(home, server, monkeypatch):
    manager, provider = boot(home)
    import importlib
    capture = importlib.import_module(provider.__class__.__module__.rsplit(".", 1)[0] + ".capture")
    monkeypatch.setattr(capture, "MAX_PENDING_CHARS", 30)
    monkeypatch.setattr(provider, "_drain", lambda *a, **kw: None)
    first = [{"role": "user", "content": "a" * 20}]
    second = [{"role": "user", "content": "b" * 20}]
    manager.on_pre_compress(first, evidence_messages=evidence(first), require_checkpoint=True)
    with pytest.raises(RuntimeError, match="capacity exceeded"):
        manager.on_pre_compress(second, evidence_messages=evidence(second), require_checkpoint=True)
    assert provider._capture.claim(force=True).content == "User: " + "a" * 20
    manager.shutdown_all()


def test_memory_mirroring_retries_after_outage_even_with_transcript_capture_off(home, server, monkeypatch):
    monkeypatch.setenv("MINDGRAPH_AUTO_CAPTURE", "off")
    manager, provider = boot(home)
    server.failures["/memory/remember"] = [503] * 20
    manager.on_memory_write("replace", "user", "new preference", metadata={"previous_content": "old preference"})
    manager.on_session_end([])
    status = json.loads(manager.handle_tool_call("mindgraph_memory", {"action": "status"}))
    assert status["memory_mirror"]["pending_operations"] == 2
    assert server.bodies("/memory/forget") == [], "new content must be saved before old content is removed"
    server.failures.clear()
    manager.on_session_end([])
    assert provider._outbox.status()["pending_operations"] == 0
    assert len(server.bodies("/memory/forget")) == 1
    assert server.ingested() == []
    manager.shutdown_all()


def test_real_isolated_host_reports_capture_limit_and_keeps_memory_mirroring(home, server):
    from hermes_cli.plugin_isolation import user_plugin_host
    (home / "config.yaml").write_text("plugins:\n  isolation: host\nmemory:\n  provider: mindgraph\n")
    # The child binds profile secrets from disk, not the parent's test environment.
    (home / ".env").write_text(f"MINDGRAPH_API_KEY=mg_host_test_key\nMINDGRAPH_BASE_URL={server.url}\n")
    manager = None
    try:
        manager, _ = boot(home)
        manager.on_turn_start(1, "ordinary turn")
        manager.sync_all("ordinary turn", "reply", session_id="host-session")
        assert manager.flush_pending(5)
        manager.on_memory_write("add", "memory", "explicit memory")
        manager.on_session_end([])
        status = json.loads(manager.handle_tool_call("mindgraph_memory", {"action": "status"}))
        assert not status["integration"]["automatic_capture"]
        assert any("isolated plugin-host" in item["message"] for item in status["degradation"])
        assert server.ingested() == [] and len(server.bodies("/memory/remember")) == 1
        transcript = [{"role": "user", "content": "required checkpoint evidence"}]
        manager.on_pre_compress(transcript, evidence_messages=evidence(transcript), require_checkpoint=True)
        assert "required checkpoint evidence" in server.ingested()[0]["content"]
    finally:
        if manager:
            manager.shutdown_all()
        host = user_plugin_host()
        if host:
            host.shutdown()


def test_a_new_conversation_flushes_the_old_one_under_its_own_id(home, server):
    manager, _ = boot(home, "conversation-1")
    manager.sync_all("Belongs to the first conversation.", "ok", session_id="conversation-1")
    manager.commit_session_boundary_async([], new_session_id="conversation-2")
    manager.sync_all("Belongs to the second conversation.", "ok", session_id="conversation-2")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    by_title = {body["title"].split(" · ")[0]: body["content"] for body in server.ingested()}
    assert "first conversation" in by_title["Hermes session conversation-1"]
    assert "second conversation" in by_title["Hermes session conversation-2"]
    assert "first conversation" not in by_title["Hermes session conversation-2"]


# ── The pre-compress checkpoint, as Hermes's compressor calls it ───────────


TRANSCRIPT = [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "Rotate the signing key tonight."},
    {"role": "assistant", "content": "Checking the runbook.", "tool_calls": [{"id": "t1", "function": {"name": "x"}}]},
    {"role": "tool", "content": "RUNBOOK CONTENTS", "tool_call_id": "t1"},
    {"role": "assistant", "content": "Scheduled for 23:00."},
]


def evidence(messages):
    from agent.conversation_compression import _direct_messages_for_pre_compress_memory

    return _direct_messages_for_pre_compress_memory(messages)


def test_a_required_checkpoint_commits_evidence_while_mindgraph_is_down(home, server):
    manager, _ = boot(home)
    server.failures["/ingest/session"] = [503]
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    assert server.ingested() == [] and queue_counts(home)["sealed"] == 1, "committed to disk; compression may proceed"

    manager.on_session_end([])
    manager.shutdown_all()
    (transcript,) = server.ingested()
    assert "Rotate the signing key tonight." in transcript["content"]
    assert "Checking the runbook." in transcript["content"] and "Scheduled for 23:00." in transcript["content"]
    assert "RUNBOOK CONTENTS" not in transcript["content"] and "system prompt" not in transcript["content"]


def test_a_required_checkpoint_that_cannot_commit_blocks_compression(home, server):
    manager, provider = boot(home)
    provider._capture.close()  # the queue is unusable
    with pytest.raises(RuntimeError):  # the plugin's CaptureError, re-raised by the manager
        manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT))  # unrequired: best effort
    assert server.ingested() == []


def test_a_retried_checkpoint_and_the_turn_it_interrupted_add_nothing_twice(home, server):
    manager, _ = boot(home)
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    manager.sync_all("Rotate the signing key tonight.", "Scheduled for 23:00.", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    everything = "\n".join(body["content"] for body in server.ingested())
    assert everything.count("Rotate the signing key tonight.") == 1
    assert everything.count("Scheduled for 23:00.") == 1


def test_a_fork_checkpoints_when_required_and_writes_nothing_otherwise(home, server):
    manager, _ = boot(home, "fork-1", agent_context="subagent")
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT))
    assert server.ingested() == []
    manager.on_pre_compress(TRANSCRIPT, evidence_messages=evidence(TRANSCRIPT), require_checkpoint=True)
    (transcript,) = server.ingested()
    assert transcript["title"].startswith("Hermes subagent session fork-1 · ")
    manager.shutdown_all()


def test_capture_off_means_no_checkpoint_capability(home, server, monkeypatch):
    monkeypatch.setenv("MINDGRAPH_AUTO_CAPTURE", "off")
    manager, _ = boot(home)
    assert not manager.supports_pre_compress_checkpoint()
    manager.sync_all("Not captured.", "ok", session_id="host-session")
    assert manager.flush_pending(10)
    manager.on_session_end([])
    manager.shutdown_all()
    assert server.ingested() == []
    assert queue_counts(home)["open_parts"] == 0, "the database remains available for built-in memory mirroring"


# ── Tools and the built-in memory mirror ───────────────────────────────────


def test_a_tool_call_passes_governance_then_reaches_the_api(home, server):
    manager, _ = boot(home)
    result = json.loads(manager.handle_tool_call(
        "mindgraph_remember", {"action": "remember", "text": "Prefers green tea", "custom_id": "pref:tea"}
    ))
    assert "error" not in result
    paths = [path for _, path, _ in server.requests]
    assert paths.index("/agent/governance") < paths.index("/memory/remember")
    (remembered,) = server.bodies("/memory/remember")
    assert remembered["text"] == "Prefers green tea" and remembered["custom_id"] == "pref:tea"
    manager.shutdown_all()


def test_a_governance_denial_stops_the_call(home, server):
    server.governance = {"decision": "deny", "fired_policies": [{"name": "no-writes"}]}
    manager, _ = boot(home)
    result = json.loads(manager.handle_tool_call("mindgraph_remember", {"action": "remember", "text": "blocked"}))
    assert "no-writes" in result["error"] and server.bodies("/memory/remember") == []
    manager.shutdown_all()


def test_retrieve_context_asks_for_the_servers_rendering(home, server):
    server.context = {**graph(), "context_text": "As of: 2026-11-10\n[2026-10-12] Decision — budget is $8,000 [current]"}
    manager, _ = boot(home)
    result = json.loads(manager.handle_tool_call(
        "mindgraph_retrieve", {"action": "context", "query": "pilot budget", "as_of": "2026-11-01"}
    ))
    assert result["result"].startswith("As of: 2026-11-10")
    (request,) = server.bodies("/retrieve/context")
    assert request["format"] == "text" and request["as_of"] == "2026-11-01" and request["max_tokens"] == 6000
    manager.shutdown_all()


def test_builtin_memory_writes_are_mirrored(home, server):
    manager, _ = boot(home)
    manager.on_memory_write("add", "user", "Prefers green tea")
    manager.on_memory_write("replace", "user", "Prefers oolong", metadata={"previous_content": "Prefers green tea"})
    manager.on_session_end([])
    remembered = [body["text"] for body in server.bodies("/memory/remember")]
    assert remembered == ["Prefers green tea", "Prefers oolong"]
    assert len(server.bodies("/memory/forget")) == 1
    manager.shutdown_all()
