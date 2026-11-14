"""Outbox ordering, crash recovery, and cross-instance delivery ownership."""

import threading

import pytest
from hermes_mindgraph_plugin.capture import CaptureError, CaptureQueue
from hermes_mindgraph_plugin.mirroring import MemoryOutbox
from mindgraph import MindGraphError


@pytest.fixture
def store(tmp_path):
    queue = CaptureQueue(tmp_path / "capture.db")
    yield queue
    queue.close()


def test_failed_replacement_preserves_old_entry_and_replays_after_restart(store):
    remote = {"old": "old text"}
    fail = [True]
    calls = []

    def send(action, payload):
        calls.append((action, payload["custom_id"]))
        if fail[0]:
            raise MindGraphError("offline", 503, {})
        if action == "remember":
            remote[payload["custom_id"]] = payload["text"]
        else:
            remote.pop(payload["custom_id"], None)

    outbox = MemoryOutbox(store, send)
    outbox.enqueue([("remember", {"custom_id": "new", "text": "new text"}), ("forget", {"custom_id": "old"})])
    outbox._drain(force=True)
    assert remote == {"old": "old text"}
    assert outbox.status()["pending_operations"] == 2 and outbox.status()["last_error"]
    path = store.path
    store.close()
    restored = CaptureQueue(path)
    fail[0] = False
    survivor = MemoryOutbox(restored, send)
    survivor._drain(force=True)
    assert remote == {"new": "new text"}
    assert calls == [("remember", "new"), ("remember", "new"), ("forget", "old")]
    assert survivor.status()["pending_operations"] == 0
    restored.close()


def test_lost_forget_reply_does_not_let_a_later_add_overtake_removal(store):
    calls = []
    failures = [503, 404]

    def send(action, payload):
        calls.append(action)
        if action == "forget" and failures:
            raise MindGraphError("lost response or already absent", failures.pop(0), {})

    outbox = MemoryOutbox(store, send)
    outbox.enqueue([("forget", {"custom_id": "same"}), ("remember", {"custom_id": "same", "text": "again"})])
    outbox._drain(force=True)
    assert calls == ["forget"] and outbox.status()["pending_operations"] == 2
    outbox._drain(force=True)
    assert calls == ["forget", "forget", "remember"] and outbox.status()["pending_operations"] == 0


def test_live_peer_lease_prevents_out_of_order_delivery(store):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def send(action, payload):
        calls.append(payload["custom_id"])
        entered.set()
        assert release.wait(5)

    first = MemoryOutbox(store, send)
    first.enqueue([("remember", {"custom_id": "one"}), ("forget", {"custom_id": "two"})])
    peer_store = CaptureQueue(store.path)
    peer = MemoryOutbox(peer_store, lambda action, payload: calls.append("overtook"))
    worker = threading.Thread(target=first._drain, kwargs={"force": True})
    worker.start()
    try:
        assert entered.wait(5)
        peer._drain(force=True)
        assert calls == ["one"]
    finally:
        release.set()
        worker.join(5)
        peer_store.close()
    assert calls == ["one", "two"]


def test_enqueue_is_atomic_at_capacity(store, monkeypatch):
    from hermes_mindgraph_plugin import mirroring
    monkeypatch.setattr(mirroring, "MAX_OUTBOX_CHARS", 20)
    outbox = MemoryOutbox(store, lambda *a: None)
    with pytest.raises(CaptureError, match="capacity exceeded"):
        outbox.enqueue([("remember", {"text": "x" * 30}), ("forget", {"custom_id": "old"})])
    assert outbox.status()["pending_operations"] == 0
    assert outbox.status()["enqueue_failures"] == 1
    survivor = MemoryOutbox(store, lambda *a: None)
    assert survivor.status()["enqueue_failures"] == 1 and "capacity exceeded" in survivor.status()["enqueue_error"]


def test_enqueue_failure_is_visible_even_if_sqlite_cannot_record_it(store):
    outbox = MemoryOutbox(store, lambda *a: None)
    store.close()
    with pytest.raises(CaptureError):
        outbox.enqueue([("remember", {"text": "missed native change"})])
    assert outbox.status()["enqueue_failures"] == 1
    assert outbox.status()["enqueue_error"] and outbox.status()["pending_operations"] is None
