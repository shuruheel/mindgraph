"""Durable capture: the queue's guarantees, delivery, and the provider's use of both."""

from __future__ import annotations

import json
import sqlite3

import httpx
import pytest
from conftest import FakeClient
from hermes_mindgraph_plugin import capture as capture_mod
from hermes_mindgraph_plugin import provider as provider_mod
from hermes_mindgraph_plugin.capture import (
    Batch,
    CaptureError,
    CaptureQueue,
    Deliverer,
    DeliveryRejected,
    DeliveryUncertain,
    Receipt,
)
from hermes_mindgraph_plugin.provider import MindGraphMemoryProvider, evidence_rows
from mindgraph import MindGraphError


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def queue(tmp_path, clock):
    q = CaptureQueue.open(str(tmp_path / "profile"), clock=clock)
    yield q
    q.close()


def reopen(tmp_path, clock) -> CaptureQueue:
    return CaptureQueue.open(str(tmp_path / "profile"), clock=clock)


# ── The queue ──────────────────────────────────────────────────────────────


def test_a_committed_turn_survives_the_process(tmp_path, clock, queue):
    queue.add_turn("s1", "We chose Postgres.", "Noted.")
    queue.close()  # no seal, no delivery: the process just ends

    survivor = reopen(tmp_path, clock)
    survivor.seal()
    batch = survivor.claim(force=True)
    assert batch.content == "User: We chose Postgres.\n\nAssistant: Noted."
    assert batch.session == "s1"


def test_the_queue_file_is_private_to_the_profile_owner(tmp_path, queue):
    mode = (tmp_path / "profile" / "mindgraph" / "capture.db").stat().st_mode & 0o777
    assert mode == 0o600, "the queue holds transcript text"


def test_sealing_groups_by_conversation_in_turn_order(queue):
    queue.add_turn("a", "a1", "a1r")
    queue.add_turn("b", "b1", "b1r")
    queue.add_turn("a", "a2", "a2r")
    assert len(queue.seal()) == 2
    first, second = queue.claim(force=True), None
    queue.mark_delivered(first.batch_id, Receipt())
    second = queue.claim(force=True)
    assert first.session == "a" and first.content.index("a1") < first.content.index("a2")
    assert second.session == "b" and "a1" not in second.content
    assert queue.seal() == [], "sealed parts are never sealed twice"


def test_a_batch_id_is_stable_for_its_content_and_distinct_otherwise(tmp_path, clock, queue):
    queue.add_turn("s", "same text", "ok")
    (first,) = queue.seal()
    queue.close()
    again = reopen(tmp_path, clock)
    assert again.claim(force=True).batch_id == first, "a restart sees the same batch, so a retry is recognizable"
    again.add_turn("s", "same text", "ok")
    (second,) = again.seal()
    assert second != first, "the same words said again are a different batch"


def test_an_oversized_flush_is_split_at_part_boundaries(queue, monkeypatch):
    monkeypatch.setattr(capture_mod, "MAX_BATCH_CHARS", 25)
    queue.add_turn("s", "u" * 20, "a" * 20)
    queue.add_turn("s", "v" * 20, "b" * 20)
    assert len(queue.seal()) == 4


def test_delivery_keeps_the_receipt_and_forgets_the_text(queue):
    queue.add_turn("s", "secret text", "ok")
    (batch_id,) = queue.seal()
    queue.mark_delivered(batch_id, Receipt(job_id="job-1", document_uid="doc-1"))
    assert queue.claim(force=True) is None
    status = queue.status()
    assert status["delivered_batches"] == 1 and status["pending_batches"] == 0
    assert status["last_delivery"]["job_id"] == "job-1"
    raw = sqlite3.connect(queue.path)
    assert raw.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 0, "the server holds the text now"


def test_a_failed_batch_backs_off_and_holds_the_line(queue, clock):
    queue.add_turn("s", "older", "ok")
    queue.seal()
    queue.add_turn("s", "newer", "ok")
    queue.seal()
    older = queue.claim()
    queue.mark_retry(older.batch_id, "503", uncertain=True)
    assert queue.claim() is None, "the newer batch must not overtake the one that is backing off"
    assert queue.claim(force=True).batch_id == older.batch_id, "a flush point tries again now"
    queue.mark_retry(older.batch_id, "503", uncertain=True)
    clock.now += capture_mod.retry_delay(2) + 1
    due = queue.claim()
    assert due.batch_id == older.batch_id and due.attempts == 2 and due.uncertain


def test_backoff_grows_and_is_capped():
    delays = [capture_mod.retry_delay(n) for n in range(1, 12)]
    assert delays[0] == capture_mod.RETRY_BASE_S and delays == sorted(delays)
    assert delays[-1] == capture_mod.RETRY_MAX_S


def test_another_live_process_keeps_its_lease_until_it_expires(tmp_path, clock, queue):
    queue.add_turn("s", "leased", "ok")
    queue.seal()
    assert queue.claim(force=True) is not None
    other = reopen(tmp_path, clock)
    assert other.claim(force=True) is None, "a live lease is not stolen, even at a flush point"
    clock.now += capture_mod.LEASE_S + 1
    assert other.claim(force=True) is not None, "a crashed process's batch is taken over"


def test_undo_discards_everything_unsent_and_lets_it_be_said_again(queue):
    queue.add_turn("s", "keep?", "ok")
    queue.seal()
    queue.add_turn("s", "my password is hunter2", "noted")
    queue.add_turn("other", "untouched", "ok")
    assert queue.discard_session("s") == 4
    queue.seal()
    assert queue.claim(force=True).session == "other"
    queue.add_evidence("s", [("user", "keep?")])
    queue.seal()
    assert queue.status()["pending_batches"] == 2, "text retracted by an undo is not remembered as seen"


def test_undo_never_reaches_what_the_server_already_has(queue):
    queue.add_turn("s", "already sent", "ok")
    (batch_id,) = queue.seal()
    queue.mark_delivered(batch_id, Receipt(job_id="j"))
    assert queue.discard_session("s") == 0
    assert queue.status()["delivered_batches"] == 1


def test_the_bound_drops_oldest_undelivered_batches_and_says_so(queue, monkeypatch, caplog):
    monkeypatch.setattr(capture_mod, "MAX_PENDING_CHARS", 30)
    queue.add_turn("s", "o" * 20, "")
    queue.seal()
    queue.add_turn("s", "n" * 20, "")
    queue.seal()
    status = queue.status()
    assert status["dropped_batches"] == 1 and status["pending_batches"] == 1
    assert "n" * 20 in queue.claim(force=True).content, "the newest text is what is kept"
    assert "dropped undelivered batch" in caplog.text


def test_a_parked_batch_keeps_its_text_and_returns_on_request(queue):
    queue.add_turn("s", "refused", "ok")
    (batch_id,) = queue.seal()
    queue.mark_failed(batch_id, "400 bad request")
    assert queue.claim(force=True) is None
    assert queue.status()["failed_batches"] == 1
    assert queue.status()["last_error"]["state"] == "parked"
    assert queue.retry_failed() == 1
    assert "refused" in queue.claim(force=True).content


def test_pruning_forgets_old_receipts_but_never_undelivered_text(queue, clock):
    queue.add_turn("s", "delivered long ago", "ok")
    (done,) = queue.seal()
    queue.mark_delivered(done, Receipt(job_id="j"))
    queue.add_turn("s", "still waiting", "ok")
    queue.seal()
    clock.now += capture_mod.RETENTION_S + 10
    queue.prune()
    status = queue.status()
    assert status["delivered_batches"] == 0 and status["pending_batches"] == 1


def test_an_unwritable_profile_falls_back_to_memory_and_says_so(tmp_path, caplog):
    blocker = tmp_path / "profile"
    blocker.write_text("a file where the profile directory should be")
    q = CaptureQueue.open(str(blocker))
    assert q.durable is False and q.status()["durable"] is False
    q.add_turn("s", "still captured", "ok")
    q.seal()
    assert "still captured" in q.claim(force=True).content
    assert "held in memory only" in caplog.text


def test_a_write_that_cannot_commit_raises(queue):
    queue.close()
    with pytest.raises(CaptureError):
        queue.add_turn("s", "lost?", "ok")


# ── The ledgers ────────────────────────────────────────────────────────────


def test_a_checkpoint_archives_only_rows_no_turn_delivered(queue):
    queue.add_turn("s", "What port?", "5432.")
    transcript = [("user", "What port?"), ("assistant", "Checking the config first."), ("assistant", "5432.")]
    assert queue.add_evidence("s", transcript) == 1
    queue.seal()
    batch = queue.claim(force=True)
    assert batch.content.count("What port?") == 1
    assert "Checking the config first." in batch.content


def test_a_checkpoint_is_idempotent_for_the_same_and_a_grown_transcript(queue):
    transcript = [("user", "first"), ("assistant", "one")]
    assert queue.add_evidence("s", transcript) == 2
    assert queue.add_evidence("s", transcript) == 0
    assert queue.add_evidence("s", [*transcript, ("user", "second")]) == 1


def test_a_turn_the_checkpoint_ran_ahead_of_is_not_sent_twice(queue):
    # Compression interrupts a turn: its user message is archived before the turn completes.
    queue.add_evidence("s", [("user", "Deploy to staging")])
    queue.add_turn("s", "Deploy to staging", "Done.")
    queue.seal()
    batch = queue.claim(force=True)
    assert batch.content.count("Deploy to staging") == 1 and "Done." in batch.content


def test_the_same_words_in_two_turns_are_both_captured(queue):
    queue.add_turn("s", "yes", "Proceeding with A.")
    queue.add_turn("s", "yes", "Proceeding with B.")
    queue.seal()
    assert queue.claim(force=True).content.count("User: yes") == 2


def test_whitespace_differences_do_not_make_a_row_new(queue):
    queue.add_turn("s", "line one\nline two", "ok")
    assert queue.add_evidence("s", [("user", "  line one   line two ")]) == 0


# ── Delivery ───────────────────────────────────────────────────────────────


class Server:
    """A scriptable stand-in for the two calls delivery makes."""

    def __init__(self) -> None:
        self.sent: list[Batch] = []
        self.jobs: list[str] = []  # tags the server already holds
        self.script: list = []
        self.finds = 0

    def send(self, batch: Batch) -> Receipt:
        self.sent.append(batch)
        outcome = self.script.pop(0) if self.script else None
        if isinstance(outcome, BaseException):
            raise outcome
        return Receipt(job_id=f"job-{len(self.sent)}")

    def find(self, batch: Batch):
        self.finds += 1
        return Receipt(job_id="found") if batch.tag in self.jobs else None


@pytest.fixture
def server():
    return Server()


def loaded(queue, *turns):
    for index, text in enumerate(turns):
        queue.add_turn(f"s{index}", text, "ok")
        queue.seal()


def test_a_drain_delivers_everything_in_order(queue, server):
    loaded(queue, "one", "two", "three")
    result = Deliverer(queue, server.send, server.find).drain(force=True)
    assert result.delivered == 3 and result.blocked is None
    assert ["one" in b.content for b in server.sent[:1]] == [True]
    assert [b.session for b in server.sent] == ["s0", "s1", "s2"]


def test_a_failure_stops_the_drain_and_keeps_every_batch(queue, server):
    loaded(queue, "one", "two")
    server.script = [RuntimeError("connection refused")]
    result = Deliverer(queue, server.send, server.find).drain(force=True)
    assert result.delivered == 0 and "connection refused" in result.blocked
    assert queue.status()["pending_batches"] == 2
    assert queue.status()["last_error"]["state"] == "retrying"


def test_an_attempt_that_landed_is_recognized_not_resent(queue, server):
    loaded(queue, "landed despite the timeout")
    server.script = [DeliveryUncertain("read timeout")]
    deliverer = Deliverer(queue, server.send, server.find)
    deliverer.drain(force=True)
    server.jobs.append(server.sent[0].tag)  # the server did create the job

    result = deliverer.drain(force=True)
    assert result.reconciled == 1 and len(server.sent) == 1, "no second /ingest/session"
    assert queue.status()["last_delivery"]["job_id"] == "found"


def test_an_attempt_that_did_not_land_is_sent_again(queue, server):
    loaded(queue, "lost in transit")
    server.script = [DeliveryUncertain("read timeout")]
    deliverer = Deliverer(queue, server.send, server.find)
    deliverer.drain(force=True)
    result = deliverer.drain(force=True)
    assert result.delivered == 1 and len(server.sent) == 2 and server.finds == 1


def test_a_certain_failure_is_resent_without_asking_the_server(queue, server):
    loaded(queue, "never connected")
    server.script = [RuntimeError("connection refused")]
    deliverer = Deliverer(queue, server.send, server.find)
    deliverer.drain(force=True)
    deliverer.drain(force=True)
    assert server.finds == 0


def test_when_the_earlier_attempt_cannot_be_verified_nothing_is_resent_yet(queue, server):
    loaded(queue, "unknown outcome")
    server.script = [DeliveryUncertain("502")]
    deliverer = Deliverer(queue, server.send, lambda batch: (_ for _ in ()).throw(RuntimeError("jobs unavailable")))
    deliverer.drain(force=True)
    result = deliverer.drain(force=True)
    assert len(server.sent) == 1 and "jobs unavailable" in result.blocked


def test_a_rejected_batch_is_parked_and_the_queue_moves_on(queue, server):
    loaded(queue, "malformed", "fine")
    server.script = [DeliveryRejected("400 content invalid")]
    result = Deliverer(queue, server.send, server.find).drain(force=True)
    assert result.parked == 1 and result.delivered == 1
    assert queue.status()["failed_batches"] == 1


def test_a_batch_that_keeps_failing_is_parked_so_it_cannot_block_forever(queue, server, clock):
    loaded(queue, "poison", "healthy")
    deliverer = Deliverer(queue, server.send, server.find)
    server.script = [RuntimeError("500")] * capture_mod.MAX_ATTEMPTS
    for _ in range(capture_mod.MAX_ATTEMPTS):
        deliverer.drain(force=True)
    status = queue.status()
    assert status["failed_batches"] == 1 and status["delivered_batches"] == 1


def test_a_drain_stops_at_its_budget_and_leaves_the_rest_queued(queue, server):
    loaded(queue, "one", "two", "three")
    ticks = iter([0.0, 0.0, 5.0, 11.0, 12.0])
    result = Deliverer(queue, server.send, server.find, clock=lambda: next(ticks)).drain(force=True, budget_s=10.0)
    assert result.delivered == 2 and queue.status()["pending_batches"] == 1


# ── The provider ───────────────────────────────────────────────────────────


@pytest.fixture
def secrets(monkeypatch):
    values = {"MINDGRAPH_API_KEY": "mg_test"}
    monkeypatch.setattr(provider_mod, "get_secret", lambda name, default=None: values.get(name, default))
    return values


@pytest.fixture
def home(tmp_path):
    return str(tmp_path / "profile")


def start(home, *, session_id="hermes-sess", client=None, **kwargs):
    provider = MindGraphMemoryProvider()
    fake = client or FakeClient()
    fake.responses.setdefault("session", lambda **body: {"uid": "session-uid-1"} if body["action"] == "open" else {})
    # The client is swapped before initialize() can start a recovery thread.
    original = provider_mod.Runtime

    def runtime(**fields):
        return original(**fields, client=fake)

    provider_mod.Runtime = runtime
    try:
        provider.initialize(session_id, hermes_home=home, platform="cli", **kwargs)
    finally:
        provider_mod.Runtime = original
    provider._gate = None  # governance has its own tests; these make no policy calls
    return provider, fake


def settle(provider) -> None:
    """Wait for a startup recovery thread, if one was started."""
    import threading

    for thread in threading.enumerate():
        if thread.name == "mindgraph-capture-recovery":
            thread.join(5)


def test_turns_left_by_a_crashed_process_are_delivered_by_the_next(secrets, home):
    crashed, fake = start(home)
    crashed.sync_turn("We agreed to ship Friday.", "Friday it is.", session_id="hermes-sess")
    assert fake.called("ingest_session") == []
    crashed._capture.close()  # the process dies: no session end, no shutdown

    survivor, fresh = start(home, session_id="hermes-sess-2")
    settle(survivor)
    ((content,), kwargs), = fresh.called("ingest_session")
    assert "We agreed to ship Friday." in content
    assert kwargs["title"].startswith("Hermes session hermes-sess · "), "delivered under its own conversation"
    assert survivor._capture.status()["pending_batches"] == 0


def test_an_outage_delays_capture_and_recovery_delivers_it_in_order(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = MindGraphError("unavailable", 503, {})
    provider.sync_turn("first", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    provider.sync_turn("second", "ok", session_id="hermes-sess")
    provider.on_session_end([])
    assert provider._capture.status()["pending_batches"] == 2
    provider._capture.close()

    survivor, fresh = start(home)
    settle(survivor)
    sent = [args[0] for args, _ in fresh.called("ingest_session")]
    assert len(sent) == 2 and "first" in sent[0] and "second" in sent[1]
    assert len(fresh.called("list_jobs")) == 1, "only the batch a 503 answered is checked before resending"


def test_a_timeout_that_landed_is_not_ingested_twice(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = httpx.ReadTimeout("timed out")
    provider.sync_turn("slow but successful", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    title = fake.called("ingest_session")[0][1]["title"]

    fake.responses["ingest_session"] = {"job_id": "never-called"}
    fake.responses["list_jobs"] = [{"id": "job-77", "title": f"Session Transcript: {title}", "status": "processing"}]
    provider.on_session_end([])
    assert len(fake.called("ingest_session")) == 1
    assert provider._capture.status()["last_delivery"]["job_id"] == "job-77"


def test_a_refused_connection_is_retried_without_a_lookup(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = httpx.ConnectError("refused")
    provider.sync_turn("offline", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    fake.responses["ingest_session"] = {"job_id": "j1"}
    provider.on_session_end([])
    assert len(fake.called("ingest_session")) == 2 and fake.called("list_jobs") == []


def test_a_request_the_server_rejects_is_parked_not_retried_forever(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = MindGraphError("bad", 400, {"code": "invalid_request"})
    provider.sync_turn("rejected", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    provider.on_session_end([])
    assert len(fake.called("ingest_session")) == 1
    assert provider._capture.status()["failed_batches"] == 1


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_credential_or_rate_problem_keeps_the_batch_queued(secrets, home, status):
    provider, fake = start(home)
    fake.responses["ingest_session"] = MindGraphError("no", status, {})
    provider.sync_turn("waiting on a key", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    queue = provider._capture.status()
    assert queue["pending_batches"] == 1 and queue["failed_batches"] == 0


def test_a_vanished_session_is_reopened_on_the_next_attempt(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = MindGraphError("Session not found", 404, {"code": "not_found"})
    provider.sync_turn("orphaned", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    fake.responses["ingest_session"] = {"job_id": "j1"}
    provider.on_session_end([])
    opens = [kw for _, kw in fake.called("session") if kw["action"] == "open"]
    assert len(opens) == 2 and len(fake.called("ingest_session")) == 2


def test_the_receipt_records_the_job_and_document(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = {"job_id": "job-9", "document_uid": "doc-9"}
    provider.sync_turn("receipted", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    assert provider._capture.status()["last_delivery"] == {
        "at": provider._capture.status()["last_delivery"]["at"],
        "job_id": "job-9",
        "document_uid": "doc-9",
    }


def test_status_reports_the_queue_and_what_became_of_deliveries(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = {"job_id": "job-1"}
    provider.sync_turn("delivered", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    fake.responses["ingest_session"] = MindGraphError("unavailable", 503, {})
    provider.sync_turn("stuck", "ok", session_id="hermes-sess")
    provider.on_pre_compress([])
    fake.responses["get_job"] = {"id": "job-1", "status": "failed", "error_details": {"message": "provider refusal"}}

    status = json.loads(provider.handle_tool_call("mindgraph_memory", {"action": "status"}))
    queue = status["capture"]
    assert queue["durable"] is True
    assert queue["pending_batches"] == 1 and queue["delivered_batches"] == 1
    assert queue["failed_extraction_jobs"] == 1
    codes = {entry["code"] for entry in status["degradation"]}
    assert {"capture_delivery_delayed", "capture_extraction_failed"} <= codes
    assert fake.called("get_job") == [(("job-1",), {})]

    provider.handle_tool_call("mindgraph_memory", {"action": "status"})
    assert len(fake.called("get_job")) == 1, "a settled job is not polled again"


def test_status_is_quiet_when_capture_is_healthy(secrets, home):
    provider, fake = start(home)
    status = json.loads(provider.handle_tool_call("mindgraph_memory", {"action": "status"}))
    assert status["capture"]["pending_batches"] == 0
    assert not {e["code"] for e in status["degradation"]} & {
        "capture_delivery_delayed", "capture_batches_parked", "capture_batches_dropped", "capture_not_durable",
    }


def test_capture_off_opens_no_queue_and_reports_none(secrets, home, tmp_path):
    secrets["MINDGRAPH_AUTO_CAPTURE"] = "off"
    provider, fake = start(home)
    provider.sync_turn("not captured", "ok", session_id="hermes-sess")
    provider.on_session_end([])
    assert not (tmp_path / "profile" / "mindgraph").exists()
    assert "capture" not in json.loads(provider.handle_tool_call("mindgraph_memory", {"action": "status"}))


# ── The pre-compress checkpoint (Hermes checkpoint API v2) ─────────────────


def test_the_provider_advertises_v2_only_when_it_can_commit_to_disk(secrets, home, tmp_path):
    assert MindGraphMemoryProvider().pre_compress_checkpoint_api_version == 1, "nothing is bound before initialize"
    durable, _ = start(home)
    assert durable.pre_compress_checkpoint_api_version == 2

    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    in_memory, _ = start(str(blocker))
    assert in_memory.pre_compress_checkpoint_api_version == 1

    secrets["MINDGRAPH_AUTO_CAPTURE"] = "off"
    off, _ = start(str(tmp_path / "off"))
    assert off.pre_compress_checkpoint_api_version == 1


def test_a_required_checkpoint_commits_the_transcript_before_returning(secrets, home):
    provider, fake = start(home)
    fake.responses["ingest_session"] = MindGraphError("unavailable", 503, {})
    transcript = [
        {"role": "user", "content": "Rotate the signing key tonight."},
        {"role": "assistant", "content": "Scheduling the rotation."},
    ]
    assert provider.on_pre_compress(transcript, require_checkpoint=True) == ""
    queue = provider._capture.status()
    assert queue["pending_batches"] == 1, "MindGraph is down, and the evidence is on disk all the same"
    provider._capture.close()

    survivor, fresh = start(home)
    settle(survivor)
    assert "Rotate the signing key tonight." in fresh.called("ingest_session")[0][0][0]


def test_a_required_checkpoint_that_cannot_commit_raises(secrets, home):
    provider, _ = start(home)
    provider._capture.close()
    with pytest.raises(CaptureError):
        provider.on_pre_compress([{"role": "user", "content": "evidence"}], require_checkpoint=True)


def test_a_required_checkpoint_refuses_a_queue_that_is_not_on_disk(secrets, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    provider, _ = start(str(blocker))
    with pytest.raises(CaptureError):
        provider.on_pre_compress([{"role": "user", "content": "evidence"}], require_checkpoint=True)


def test_a_required_checkpoint_with_capture_off_raises(secrets, home):
    secrets["MINDGRAPH_AUTO_CAPTURE"] = "off"
    provider, _ = start(home)
    with pytest.raises(RuntimeError, match="capture is off"):
        provider.on_pre_compress([{"role": "user", "content": "evidence"}], require_checkpoint=True)
    assert provider.on_pre_compress([{"role": "user", "content": "evidence"}]) == ""


def test_a_required_checkpoint_saves_in_a_fork(secrets, home):
    """Hermes loads the provider into a subagent only to checkpoint its compaction."""
    provider, fake = start(home, agent_context="subagent", session_id="fork-1")
    provider.sync_turn("a fork's turn", "ok", session_id="fork-1")
    assert provider._capture.status()["buffered_parts"] == 0, "a fork's turns are still never captured"
    provider.on_pre_compress([{"role": "user", "content": "fork evidence"}], require_checkpoint=True)
    ((content,), kwargs), = fake.called("ingest_session")
    assert "fork evidence" in content
    assert kwargs["title"].startswith("Hermes subagent session fork-1 · ")


@pytest.mark.parametrize("context", ["subagent", "cron", "flush"])
def test_without_the_requirement_a_non_primary_context_writes_nothing(secrets, home, context):
    provider, fake = start(home, agent_context=context)
    provider.on_pre_compress([{"role": "user", "content": "not archived"}])
    assert fake.calls == [] and provider._capture.status()["pending_batches"] == 0


def test_an_unrequired_checkpoint_sends_turns_not_the_transcript(secrets, home):
    provider, fake = start(home)
    provider.sync_turn("the completed turn", "its answer", session_id="hermes-sess")
    provider.on_pre_compress([
        {"role": "user", "content": "the completed turn"},
        {"role": "assistant", "content": "thinking aloud between tool calls"},
    ])
    ((content,), _), = fake.called("ingest_session")
    assert "thinking aloud" not in content and "its answer" in content


def test_a_repeated_required_checkpoint_adds_nothing(secrets, home):
    provider, fake = start(home)
    transcript = [{"role": "user", "content": "same transcript"}]
    provider.on_pre_compress(transcript, require_checkpoint=True)
    provider.on_pre_compress(transcript, require_checkpoint=True)
    assert len(fake.called("ingest_session")) == 1


def test_evidence_keeps_direct_text_only():
    rows = evidence_rows([
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "plain question"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "t1"}]},
        {"role": "tool", "content": "tool output", "tool_call_id": "t1"},
        {"role": "assistant", "content": "prose beside a call", "tool_calls": [{"id": "t2"}]},
        {"role": "assistant", "content": "an earlier summary", "_compressed_summary": True},
        {"role": "user", "content": [{"type": "text", "text": "with an image"}, {"type": "image_url", "image_url": {}}]},
        "not-a-dict",
    ])
    assert rows == [
        ("user", "plain question"),
        ("assistant", "prose beside a call"),
        ("user", "with an image"),
    ]
