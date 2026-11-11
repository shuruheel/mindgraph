"""Per-message recall: the query, the relevance floor, the deadline, repeats and scope."""

from __future__ import annotations

import json
import threading

import pytest
from conftest import FakeClient
from hermes_mindgraph_plugin import provider as provider_mod
from hermes_mindgraph_plugin import recall as recall_mod
from hermes_mindgraph_plugin.provider import MindGraphMemoryProvider
from hermes_mindgraph_plugin.recall import (
    RecallConfig,
    RecallEngine,
    RecallQuery,
    build_query,
    content_terms,
    load_config,
    relevant,
    select_items,
    term_overlap,
    workspace_project,
)
from mindgraph import MindGraphError


def node(uid, label, summary=None, kind="Decision", **extra):
    return {"uid": uid, "label": label, "node_type": kind, "summary": summary, "props": {}, **extra}


def response(*nodes):
    return {"graph": {"nodes": list(nodes), "edges": []}, "chunks": [], "articles": []}


def spawn(target, *, name, daemon=True, args=(), kwargs=None):
    return threading.Thread(target=target, name=name, daemon=daemon, args=args, kwargs=kwargs)


# ── Query ──────────────────────────────────────────────────────────────────


def test_a_sentence_is_reduced_to_its_content_terms():
    assert build_query("What did we decide about the Voya pilot pricing?").query == "decide voya pilot pricing"
    assert len(content_terms(" ".join(f"term{i}" for i in range(30)))) == 8


def test_function_words_that_matched_unrelated_memory_are_dropped():
    assert content_terms("Okay, go ahead and keep using the next one without it") == ["ahead"]


def test_accented_and_non_latin_words_stay_whole():
    assert content_terms("Die Größe der Rücklage prüfen") == ["die", "größe", "rücklage", "prüfen"]
    assert content_terms("Какой бюджет пилота?") == ["какой", "бюджет", "пилота"]


def test_function_words_of_other_latin_languages_do_not_fill_the_query():
    question = "¿Cuál fue la decisión sobre el presupuesto del proyecto de la empresa?"
    assert content_terms(question) == ["decisión", "presupuesto", "proyecto", "empresa"]
    query = build_query(question)
    assert not relevant(query, "Notas sobre el clima del lunes"), "two prepositions are not relevance"
    assert relevant(query, "Decisión: el presupuesto del proyecto se aprobó")


def test_a_two_letter_word_is_kept_only_when_it_reads_as_a_name():
    assert content_terms("is CI red on the S3 sync in la paz") == ["ci", "red", "s3", "sync", "paz"]


def test_a_path_that_opens_a_message_is_not_mistaken_for_a_command():
    assert build_query("/Users/me/app/db.py throws on migrate").terms[:2] == ("users/me/app/db.py", "throws")
    assert build_query("/model gpt-5") is None


def test_one_foreign_word_does_not_switch_off_the_query_or_the_floor():
    query = build_query("Fix the flaky deploy test for 東京 region")
    assert query.terms == ("fix", "flaky", "deploy", "test", "region")
    assert query.query == "fix flaky deploy test region 東京", "the run rides along for the vector leg"
    assert not relevant(query, "Totally unrelated cooking recipe")


def test_a_script_without_word_spaces_is_sent_whole_with_no_lexical_floor():
    query = build_query("パイロットの予算はいくらですか")
    assert query.query == "パイロットの予算はいくらですか" and query.terms == ()
    assert relevant(query, "anything at all")


def test_a_message_without_a_subject_borrows_the_previous_messages():
    query = build_query("What did we decide?", previous="Let's talk about the Voya pilot pricing")
    assert query.query == "decide talk voya pilot pricing" and query.borrowed
    assert build_query("why?", previous="The staging deploy failed on migrations").terms == (
        "staging", "deploy", "failed", "migrations",
    )


def test_a_message_with_its_own_subject_does_not_borrow():
    query = build_query("How is the ledger migration going?", previous="Voya pilot pricing")
    assert query.query == "ledger migration" and not query.borrowed


def test_a_short_technical_query_is_recalled_on():
    assert build_query("k8s?").query == "k8s"


@pytest.mark.parametrize("message", ["", "   ", "/compress", "why?", "ok so what about it"])
def test_nothing_to_recall_on_means_no_request(message):
    assert build_query(message) is None


# ── Floor ──────────────────────────────────────────────────────────────────


def test_plurals_and_tenses_match_their_stems():
    assert term_overlap(("retention", "policies", "bugs"), "Retention policy: keep bug reports") == (3, 3)
    assert term_overlap(("libraries", "picked"), "Library choice: we pick httpx") == (2, 2)
    assert term_overlap(("stories", "deploys"), "Story: deploy of v2") == (2, 2)
    assert term_overlap(("caches",), "the cache layer") == (1, 1)


def test_a_prefix_is_not_a_match_when_most_of_the_word_is_left_over():
    assert term_overlap(("test", "cart"), "Cartography notes; testament reading list") == (0, 2)
    assert term_overlap(("config",), "configs are in the repo") == (1, 1)


def test_a_borrowed_query_does_not_outvote_the_messages_own_subject():
    query = build_query("What about Postgres?", previous="We were discussing the Redis caching layer")
    assert query.own == ("postgres",) and query.borrowed
    assert relevant(query, "Postgres chosen for the ledger store"), "its own term is enough"
    assert relevant(query, "Redis caching layer evicts at 80%"), "two borrowed terms still pass"
    assert not relevant(query, "Redis licence change"), "one borrowed term does not"
    raw = response(node("r1", "Redis caching layer evicts at 80%"), node("p1", "Postgres chosen for the ledger store"))
    assert [item.uid for item in select_items(raw, query)] == ["p1", "r1"], "the new subject leads"


def test_an_item_needs_two_distinct_query_terms():
    query = RecallQuery("roadmap pricing review", ("roadmap", "pricing", "review"))
    assert relevant(query, "Pricing review moved to Q1 on the roadmap")
    assert not relevant(query, "Book notes: the Roadmap to Serfdom"), "one shared word is not relevance"


def test_a_single_term_query_needs_that_term():
    query = RecallQuery("kubernetes", ("kubernetes",))
    assert relevant(query, "Kubernetes upgrade plan") and not relevant(query, "Docker upgrade plan")


def test_stems_count_and_numbers_and_fragments_do_not():
    assert term_overlap(("updates",), "We update the index nightly") == (1, 1)
    assert term_overlap(("2-4", "n"), "n = 4 items") == (0, 0)
    assert term_overlap(("hook-core.ts",), "the hook runner") == (1, 1)


def test_the_floor_works_in_other_space_delimited_scripts():
    query = build_query("Какой бюджет пилота утвердили?")
    assert relevant(query, "Бюджет пилота — 8000 долларов")
    assert not relevant(query, "Заметки о погоде")


# ── Selection and rendering ────────────────────────────────────────────────

QUERY = RecallQuery("voya pilot budget", ("voya", "pilot", "budget"))
# What /retrieve/context sends for a superseded node: the head of its chain.
SUPERSEDED = {
    "by": ["d2"], "heads": ["d2"], "head_uid": "d2", "head_label": "Voya pilot budget is $12,500",
    "head_stated_at": "2026-11-02",
}


def test_items_carry_type_status_date_and_source():
    raw = response(node(
        "d1", "Voya pilot budget is $8,000", "Agreed with finance for the pilot.",
        superseded=SUPERSEDED, stated_at=["2026-09-01", "2026-10-12T09:00:00Z"],
        source_documents=[{"title": "Voya kickoff notes"}],
    ))
    (item,) = select_items(raw, QUERY)
    assert item.line == (
        "- [Decision] Voya pilot budget is $8,000 [SUPERSEDED by Voya pilot budget is $12,500 (2026-11-02)] "
        "— Agreed with finance for the pilot. (stated 2026-10-12; source: Voya kickoff notes)"
    )


def test_supersession_is_read_in_both_shapes_the_server_has_used():
    from hermes_mindgraph_plugin.render import status_tag

    assert status_tag({"superseded": SUPERSEDED}) == " [SUPERSEDED by Voya pilot budget is $12,500 (2026-11-02)]"
    assert status_tag({"superseded": {"head_uid": "d9"}}) == " [SUPERSEDED by d9]"
    assert status_tag({"superseded": True, "superseded_by": "d9"}) == " [SUPERSEDED by d9]"
    assert status_tag({"superseded": True}) == " [SUPERSEDED]"
    assert status_tag({"conflict": {"with": "d3"}}) == " [CONFLICT: unresolved]"
    assert status_tag({"superseded": False}) == "" and status_tag({}) == ""


def test_one_overlong_item_does_not_shut_out_the_shorter_ones_after_it():
    long = recall_mod.Item("a", "- [Decision] " + "x" * 600, "a")
    short = recall_mod.Item("b", "- [Decision] short", "b")
    assert "short" in recall_mod.render_items([long, short], 512)


def test_infrastructure_and_bare_entities_take_no_slot():
    raw = response(
        node("c1", "Voya pilot budget chunk", kind="Chunk"),
        node("s1", "Voya pilot budget session", kind="Session"),
        node("e1", "voya_pilot_budget.py", kind="Entity"),
        node("e2", "Voya", "Energy company running the pilot budget review", kind="Entity"),
    )
    assert [item.uid for item in select_items(raw, QUERY)] == ["e2"]


def test_unrelated_results_are_not_injected():
    raw = response(node("x1", "Quarterly roadmap", "Pilot programme for interns"), node("d1", "Voya pilot budget"))
    assert [item.uid for item in select_items(raw, QUERY)] == ["d1"]
    assert len(select_items(raw, QUERY, floor=False)) == 2


def test_rendering_stops_at_the_character_budget():
    items = select_items(response(*[node(f"d{i}", f"Voya pilot budget note {i}", "x" * 200) for i in range(10)]), QUERY)
    text = recall_mod.render_items(items, 600)
    assert len(text) <= 600 and text.startswith(recall_mod.HEADER) and text.count("\n- ") == 2


# ── Engine ─────────────────────────────────────────────────────────────────


class Fetch:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.queries: list[str] = []
        self.candidates: list[int] = []
        self.gate: threading.Event | None = None

    def __call__(self, query: RecallQuery, candidates: int):
        self.queries.append(query.query)
        self.candidates.append(candidates)
        if self.gate is not None:
            self.gate.wait(5)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply


def engine(fetch, **config):
    return RecallEngine(fetch, RecallConfig(**config), spawn)


BUDGET = response(node("d1", "Voya pilot budget is $8,000"), node("d2", "Voya pilot timeline is six weeks"))


def test_a_live_recall_injects_what_passes_the_floor():
    fetch = Fetch(BUDGET)
    recalled = engine(fetch).recall("s", "What is the Voya pilot budget?")
    assert recalled.source == "live" and recalled.count == 2
    assert "Voya pilot budget is $8,000" in recalled.text
    assert fetch.queries == ["voya pilot budget"]


def test_recall_off_makes_no_request():
    fetch = Fetch(BUDGET)
    assert engine(fetch, enabled=False).recall("s", "What is the Voya pilot budget?").text == ""
    assert fetch.queries == []


def test_an_item_is_injected_once_per_conversation_until_compression():
    eng = engine(Fetch(BUDGET))
    assert eng.recall("s", "What is the Voya pilot budget?").count == 2
    assert eng.recall("s", "Remind me of the Voya pilot timeline?").count == 0
    assert eng.recall("other", "What is the Voya pilot budget?").count == 2, "another conversation has not seen it"
    eng.forget_injected("s")
    assert eng.recall("s", "And the Voya pilot budget again?").count == 2


def test_an_item_whose_status_changed_is_injected_again():
    superseded = response(node("d1", "Voya pilot budget is $8,000", superseded=SUPERSEDED))
    eng = engine(Fetch(BUDGET, superseded))
    eng.recall("s", "What is the Voya pilot budget?")
    again = eng.recall("s", "Is the Voya pilot budget still right?")
    assert again.count == 1 and "SUPERSEDED by Voya pilot budget is $12,500" in again.text


def test_the_limit_caps_what_is_shown_not_what_is_remembered_as_shown():
    many = response(*[node(f"d{i}", f"Voya pilot budget note {i}") for i in range(8)])
    eng = engine(Fetch(many), limit=3)
    assert eng.recall("s", "Voya pilot budget?").count == 3
    assert eng.recall("s", "More on the Voya pilot budget?").count == 3, "the next three, not the same three"


def test_a_recall_past_its_deadline_does_not_hold_the_turn_and_is_kept():
    fetch = Fetch(BUDGET)
    fetch.gate = threading.Event()
    eng = engine(fetch, deadline_s=0.05)
    assert eng.recall("s", "What is the Voya pilot budget?").text == ""
    fetch.gate.set()
    for thread in threading.enumerate():
        if thread.name == "mindgraph-recall":
            thread.join(5)
    fetch.gate = None
    kept = eng.recall("s", "What is the Voya pilot budget?")
    assert kept.source == "cached" and kept.count == 2 and len(fetch.queries) == 1


def test_a_failed_recall_falls_back_to_the_conversations_last_one_when_on_topic():
    eng = engine(Fetch(response(node("d2", "Voya pilot timeline is six weeks", "Budget review in week three")),
                       MindGraphError("busy", 503, {})))
    eng.recall("s", "What is the Voya pilot timeline?")
    eng.forget_injected("s")
    stale = eng.recall("s", "Does the Voya pilot timeline include a budget review?")
    assert stale.source == "stale" and stale.count == 1


def test_the_fallback_is_not_used_for_a_different_subject():
    eng = engine(Fetch(BUDGET, MindGraphError("busy", 503, {})))
    eng.recall("s", "What is the Voya pilot budget?")
    eng.forget_injected("s")
    assert eng.recall("s", "How do I rotate the signing key?").text == ""


def test_a_failed_recall_is_retried_after_the_turn_and_a_healthy_one_costs_nothing():
    fetch = Fetch(MindGraphError("busy", 503, {}), BUDGET)
    eng = engine(fetch)
    assert eng.recall("s", "What is the Voya pilot budget?").text == ""
    eng.after_turn("s").join(5)
    assert len(fetch.queries) == 2, "the retry ran off the turn path"
    assert eng.recall("s", "What is the Voya pilot budget?").source == "cached"
    assert eng.after_turn("s") is None
    assert len(fetch.queries) == 2, "nothing failed, so nothing is refetched"


def test_the_retry_does_not_hold_the_caller():
    fetch = Fetch(MindGraphError("busy", 503, {}), BUDGET)
    eng = engine(fetch)
    eng.recall("s", "What is the Voya pilot budget?")
    fetch.gate = threading.Event()  # the server stalls
    thread = eng.after_turn("s")
    assert thread.is_alive(), "Hermes's worker has already moved on"
    assert eng.after_turn("s") is None, "one retry at a time"
    fetch.gate.set()
    thread.join(5)


def test_a_steady_topic_asks_for_candidates_beyond_the_ones_already_shown():
    many = response(*[node(f"d{i}", f"Voya pilot budget note {i}") for i in range(30)])
    fetch = Fetch(many)
    eng = engine(fetch)
    counts = [eng.recall("s", f"Voya pilot budget for {week}?").count for week in ("January", "February", "March")]
    assert fetch.candidates == [10, 15, 20]
    assert counts == [5, 5, 5], "the third message still gets new items"


def test_the_same_question_again_is_asked_wider_once_the_kept_answer_is_used_up():
    asked: list[int] = []

    def fetch(query, candidates):  # a server that honours the candidate count
        asked.append(candidates)
        return response(*[node(f"d{i}", f"Voya pilot budget note {i}") for i in range(candidates)])

    eng = engine(fetch)
    counts = [eng.recall("s", "Voya pilot budget?").count for _ in range(4)]
    assert counts == [5, 5, 5, 5]
    assert asked == [10, 20], "the kept ten serve two messages, then the question is asked wider"


def test_a_late_answer_never_replaces_a_newer_one():
    slow, fast = threading.Event(), threading.Event()
    fast.set()

    def fetch(query, candidates):
        (slow if "budget" in query.query else fast).wait(5)
        return response(node("d1", f"Voya pilot {query.query.split()[-1]} note"))

    eng = engine(fetch, deadline_s=0.05)
    eng.recall("s", "Voya pilot budget?")  # passes its deadline, still running
    eng.recall("s", "Voya pilot timeline?")
    slow.set()
    for thread in threading.enumerate():
        if thread.name == "mindgraph-recall":
            thread.join(5)
    assert eng._conversations["s"].kept.key == "voya pilot timeline"


def test_an_undo_forgets_what_the_undone_turns_were_shown():
    eng = engine(Fetch(BUDGET))
    assert eng.recall("s", "What is the Voya pilot budget?").count == 2
    eng.rewound("s")
    assert eng.recall("s", "What is the Voya pilot budget?").count == 2, "the model no longer has them"
    eng.rewound("s")
    assert build_query("why?", eng._conversations["s"].last_message) is None, "nor is there a message to borrow from"


def test_hermes_record_of_the_previous_message_outranks_this_process_own():
    fetch = Fetch(BUDGET)
    eng = engine(fetch)
    eng.recall("s", "Tune the Redis caching layer")
    eng.recall("s", "why?", previous="The Stripe invoice webhook keeps failing")
    assert fetch.queries[-1] == "stripe invoice webhook keeps failing"


def test_a_follow_up_borrows_from_the_previous_message_of_its_own_conversation():
    fetch = Fetch(BUDGET)
    eng = engine(fetch)
    eng.recall("a", "Let's review the Voya pilot budget")
    eng.recall("b", "Unrelated: rotate the signing key")
    eng.recall("a", "What did we decide?")
    assert fetch.queries[-1] == "decide review voya pilot budget"


def test_a_resumed_conversation_borrows_from_the_transcripts_previous_message():
    fetch = Fetch(BUDGET)
    engine(fetch).recall("s", "why?", previous="The Voya pilot budget was cut")
    assert fetch.queries == ["voya pilot budget cut"]


def test_a_conversation_continued_under_a_new_id_keeps_its_state():
    eng = engine(Fetch(BUDGET))
    eng.recall("old", "What is the Voya pilot budget?")
    eng.rebind("old", "new")
    assert eng.recall("new", "Tell me the Voya pilot budget").count == 0, "already shown under the old id"


# ── Configuration and scope ────────────────────────────────────────────────


def test_settings_are_read_from_the_profile_and_clamped():
    values = {
        "MINDGRAPH_RECALL_LIMIT": "500",
        "MINDGRAPH_RECALL_MAX_CHARS": "10",
        "MINDGRAPH_RECALL_DEADLINE_MS": "1200",
        "MINDGRAPH_RECALL_FLOOR": "off",
        "MINDGRAPH_RECALL_RERANK": "on",
        "MINDGRAPH_PROJECT_UID": " proj-1 ",
    }
    config = load_config(lambda name, default="": values.get(name, default))
    assert (config.limit, config.max_chars, config.deadline_s) == (20, 512, 1.2)
    slowest = load_config(lambda name, default="": {"MINDGRAPH_RECALL_DEADLINE_MS": "60000"}.get(name, default))
    assert slowest.deadline_s == 6.0, "kept under Hermes's own 8 s prefetch timeout"
    assert config.floor is False and config.rerank is True and config.project_uid == "proj-1"
    garbage = load_config(lambda name, default="": "" if name == "MINDGRAPH_PROJECT_UID" else "garbage")
    assert garbage == RecallConfig(), "an unreadable value is the default, never an error"
    assert load_config(lambda name, default="": {"MINDGRAPH_RECALL": "off"}.get(name, default)).enabled is False


def test_a_workspace_maps_to_its_project_by_longest_prefix(tmp_path):
    home = tmp_path / "profile"
    (home / "mindgraph").mkdir(parents=True)
    (home / "mindgraph" / "workspaces.json").write_text(json.dumps({
        str(tmp_path / "code"): "proj-all", str(tmp_path / "code" / "voya"): "proj-voya", "/elsewhere": "proj-x",
    }))
    assert workspace_project(str(home), str(tmp_path / "code" / "voya" / "src")) == "proj-voya"
    assert workspace_project(str(home), str(tmp_path / "code" / "other")) == "proj-all"
    assert workspace_project(str(home), str(tmp_path / "unmapped")) is None
    assert workspace_project(str(home), None) is None
    assert workspace_project(str(tmp_path / "no-such-profile"), str(tmp_path / "code")) is None
    link = tmp_path / "link-to-voya"
    link.symlink_to(tmp_path / "code" / "voya", target_is_directory=True)
    (tmp_path / "code" / "voya").mkdir(parents=True)
    assert workspace_project(str(home), str(link)) == "proj-voya", "a symlinked workspace is the same workspace"


# ── The provider ───────────────────────────────────────────────────────────


@pytest.fixture
def secrets(monkeypatch):
    values = {"MINDGRAPH_API_KEY": "mg_test"}
    monkeypatch.setattr(provider_mod, "get_secret", lambda name, default=None: values.get(name, default))
    return values


def start(tmp_path, **kwargs):
    provider = MindGraphMemoryProvider()
    provider.initialize("hermes-sess", hermes_home=str(tmp_path / "profile"), platform="cli", **kwargs)
    fake = FakeClient()
    fake.responses["plan"] = {"status": "no_eligible_work"}
    provider._rt.client = fake
    provider._gate = None
    return provider, fake


def join(name: str) -> None:
    for thread in threading.enumerate():
        if thread.name == name:
            thread.join(5)


def test_recall_is_unscoped_by_default_and_scoped_when_the_profile_says_so(secrets, tmp_path):
    provider, fake = start(tmp_path)
    fake.responses["retrieve_context"] = BUDGET
    provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert "project_uid" not in fake.called("retrieve_context")[0][1]

    secrets["MINDGRAPH_PROJECT_UID"] = "proj-voya"
    scoped, scoped_fake = start(tmp_path)
    scoped.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert scoped_fake.called("retrieve_context")[0][1]["project_uid"] == "proj-voya"


def test_the_workspace_of_the_conversation_selects_its_project(secrets, tmp_path):
    (tmp_path / "profile" / "mindgraph").mkdir(parents=True)
    (tmp_path / "profile" / "mindgraph" / "workspaces.json").write_text(json.dumps({str(tmp_path / "repo"): "proj-repo"}))
    provider, fake = start(tmp_path, cwd=str(tmp_path / "repo" / "src"))
    provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert fake.called("retrieve_context")[0][1]["project_uid"] == "proj-repo"


def test_the_recall_indicator_counts_what_was_injected(secrets, tmp_path, monkeypatch):
    monkeypatch.setattr(provider_mod, "RecallStatus", lambda provider_label, count: count)
    provider, fake = start(tmp_path)
    fake.responses["retrieve_context"] = response(
        node("d1", "Voya pilot budget is $8,000"), node("x1", "Unrelated roadmap note"),
    )
    text = provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert "Unrelated roadmap note" not in text
    assert provider.recall_status() == 1


def test_a_follow_up_in_a_resumed_process_uses_hermes_previous_message(secrets, tmp_path):
    provider, fake = start(tmp_path)
    provider.on_turn_start(7, "why?", previous_message="The Voya pilot budget was cut")
    provider.prefetch("why?", session_id="hermes-sess")
    assert fake.called("retrieve_context")[0][0] == ("voya pilot budget cut",)


def test_queue_prefetch_retries_only_a_failed_recall(secrets, tmp_path):
    provider, fake = start(tmp_path)
    fake.responses["retrieve_context"] = MindGraphError("busy", 503, {})
    assert provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess") == ""
    fake.responses["retrieve_context"] = BUDGET
    provider.queue_prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    join("mindgraph-recall-retry")
    assert len(fake.called("retrieve_context")) == 2
    assert "Voya pilot budget is $8,000" in provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    provider.queue_prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert len(fake.called("retrieve_context")) == 2


def test_the_brief_and_the_recall_run_side_by_side(secrets, tmp_path):
    provider, fake = start(tmp_path)
    both_running = threading.Barrier(2, timeout=5)

    def brief(**_):
        both_running.wait()
        return {"status": "selected", "task": {"uid": "t1", "label": "Ship the Voya pilot", "props": {}}}

    def context(*_, **__):
        both_running.wait()
        return BUDGET

    fake.responses["plan"], fake.responses["retrieve_context"] = brief, context
    text = provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert "Ship the Voya pilot" in text and "Voya pilot budget is $8,000" in text


def test_a_brief_that_misses_the_deadline_is_used_by_the_next_message(secrets, tmp_path):
    secrets["MINDGRAPH_RECALL_DEADLINE_MS"] = "250"
    provider, fake = start(tmp_path)
    release = threading.Event()

    def slow_brief(**_):
        release.wait(5)
        return {"status": "selected", "task": {"uid": "t1", "label": "Ship the Voya pilot", "props": {}}}

    fake.responses["plan"] = slow_brief
    fake.responses["retrieve_context"] = response()
    assert provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess") == ""
    release.set()
    for thread in threading.enumerate():
        if thread.name == "mindgraph-brief":
            thread.join(5)
    assert "Ship the Voya pilot" in provider.prefetch("And the timeline for it?", session_id="hermes-sess")
    assert len(fake.called("plan")) == 1, "the late answer is used, not asked for again"


def test_recall_off_is_reported_and_makes_no_request(secrets, tmp_path):
    secrets["MINDGRAPH_RECALL"] = "off"
    provider, fake = start(tmp_path)
    fake.responses["plan"] = {"status": "selected", "task": {"uid": "t1", "label": "Open work", "props": {}}}
    assert provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess") == ""
    assert fake.called("retrieve_context") == [] and fake.called("plan") == [], "no automatic injection at all"
    status = json.loads(provider.handle_tool_call("mindgraph_memory", {"action": "status"}))
    assert status["integration"]["automatic_delivery"] is False


def brief_task(fake) -> None:
    fake.responses["plan"] = {"status": "selected", "task": {"uid": "t1", "label": "Ship the Voya pilot", "props": {}}}


def test_compression_keeps_the_conversations_recall_state_and_does_not_brief_it_again(secrets, tmp_path):
    provider, fake = start(tmp_path)
    brief_task(fake)
    fake.responses["retrieve_context"] = BUDGET
    first = provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    assert "Ship the Voya pilot" in first and "Voya pilot budget is $8,000" in first
    provider.on_session_switch("hermes-sess-2", parent_session_id="hermes-sess", reset=False, reason="compression")
    after = provider.prefetch("And the Voya pilot budget once more?", session_id="hermes-sess-2")
    assert "Ship the Voya pilot" not in after and len(fake.called("plan")) == 1
    assert after == "", "the same conversation: nothing it was already shown"


def test_resuming_another_conversation_inherits_nothing_from_the_one_left(secrets, tmp_path):
    provider, fake = start(tmp_path)
    fake.responses["retrieve_context"] = BUDGET
    provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    provider.on_session_switch("resumed", reset=False, reason="resume")
    provider.on_turn_start(4, "why?", previous_message="The Voya pilot budget was cut")
    resumed = provider.prefetch("why?", session_id="resumed")
    assert "Voya pilot budget is $8,000" in resumed, "this conversation was never shown it"
    assert fake.called("retrieve_context")[-1][0] == ("voya pilot budget cut",), "and it borrows from its own history"


def test_an_undo_lets_the_same_question_recall_again(secrets, tmp_path):
    provider, fake = start(tmp_path)
    fake.responses["retrieve_context"] = BUDGET
    assert provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
    provider.on_session_switch("hermes-sess", rewound=True)
    assert "Voya pilot budget is $8,000" in provider.prefetch("What is the Voya pilot budget?", session_id="hermes-sess")
