"""The outcome suite's own correctness: scoring, and an end-to-end offline run.

The offline run uses a scripted server, so it measures the harness, not memory."""

from __future__ import annotations

import pytest

from evals.offline import oracle
from evals.run import render, run_suite, score
from evals.scenarios import SCENARIOS

BY_NAME = {scenario.name: scenario for scenario in SCENARIOS}
CODE = "ZephyrABC123"


def test_an_expected_phrase_must_be_present():
    scenario = BY_NAME["cross_session_decision"]
    good = score(scenario, f"- [Decision] {CODE} session cache: Redis, chosen for per-key expiry", CODE)
    assert good.passed and good.injected_items == 1 and good.irrelevant_items == 0
    bad = score(scenario, f"- [Decision] {CODE} session cache: Memcached", CODE)
    assert not bad.passed and any("Redis" in failure for failure in bad.failures)


def test_a_stale_fact_passes_only_when_marked_or_inside_its_correction():
    scenario = BY_NAME["corrected_fact"]
    current = f"- [Claim] {CODE} pilot budget is $12,500"
    assert score(scenario, f"{current}\n- [Claim] {CODE} pilot budget is $8,000 [SUPERSEDED by c2]", CODE).passed
    assert score(scenario, f"- [Claim] {CODE} pilot budget is $12,500, corrected from $8,000", CODE).passed
    shown_as_current = score(scenario, f"{current}\n- [Claim] {CODE} pilot budget is $8,000", CODE)
    assert not shown_as_current.passed and "stale shown as current" in shown_as_current.failures[0]


def test_forbidden_text_fails_wherever_it_appears():
    scenario = BY_NAME["deletion"]
    assert score(scenario, "", CODE).passed
    assert not score(scenario, f"- [Observation] The {CODE} door code is 4417-ELM [SUPERSEDED]", CODE).passed


def test_an_unrelated_message_tolerates_the_brief_but_no_recalled_item():
    scenario = BY_NAME["unrelated_project"]
    assert score(scenario, "## MindGraph context\n\nOpen work: Migrate the ledger", CODE).passed
    leaked = score(scenario, f"- [Claim] {CODE} launch pricing is $49 per seat", CODE)
    assert not leaked.passed and leaked.irrelevant_items == 1


@pytest.fixture
def eval_env(monkeypatch, tmp_path):
    # run_suite writes these; set them here so the test restores them afterwards.
    monkeypatch.setenv("MINDGRAPH_API_KEY", "mg_offline")
    monkeypatch.setenv("MINDGRAPH_BASE_URL", "http://unused")
    home = tmp_path / "hermes-home"
    home.mkdir()
    return home


def test_the_offline_run_drives_every_scenario_end_to_end(eval_env):
    with oracle() as server:
        report = run_suite(base_url=server.url, api_key="mg_offline", home=eval_env, wait_s=10.0)
        ingested = server.ingested()
    assert report["passed"] == report["total"] == len(SCENARIOS), render(report)
    assert report["problems"] == []
    capture = report["capture"]
    assert capture["rows_accepted"] == capture["rows_synced"] and capture["rows_undelivered"] == 0
    assert set(report["extraction"]["statuses"].values()) == {"completed"}
    assert any("backfill is still pending" in body["content"] for body in ingested), "the crashed turn was recovered"
    assert "scenarios passed" in render(report)


def test_a_poor_memory_fails_the_scenarios_it_should(eval_env):
    with oracle(flawed=True) as server:
        report = run_suite(base_url=server.url, api_key="mg_offline", home=eval_env, wait_s=10.0)
    failed = {outcome["scenario"] for outcome in report["outcomes"] if not outcome["passed"]}
    assert failed == {"preference_change", "corrected_fact", "interrupted_work", "unrelated_project", "deletion"}


def test_unfinished_extraction_blocks_all_scoring(eval_env):
    with oracle() as server:
        route = server._route

        def pending(method, path, body):
            if path.startswith('/jobs/'):
                return 200, {'id': path.rsplit('/', 1)[-1], 'status': 'processing'}
            return route(method, path, body)

        server._route = pending
        report = run_suite(base_url=server.url, api_key='mg_offline', home=eval_env, wait_s=0.1)
    assert not report['input_ready']
    assert report['passed'] == 0
    assert all(o['failures'] == ['not measured: input prerequisites failed'] for o in report['outcomes'])


def test_delete_requires_a_real_matching_acknowledgement(eval_env):
    with oracle() as server:
        route = server._route

        def no_ack(method, path, body):
            if path == '/memory/forget':
                return 200, {'uid': 'different-entry', 'action': 'forgotten'}
            return route(method, path, body)

        server._route = no_ack
        report = run_suite(base_url=server.url, api_key='mg_offline', home=eval_env, wait_s=2, only='deletion')
    assert not report['input_ready'] and report['passed'] == 0
    assert any('matching delete receipt' in p for p in report['problems'])


def test_expected_phrases_in_an_unrelated_resume_brief_do_not_pass_topic_recall():
    assert not score(BY_NAME['cross_session_decision'], '# Resume context\nRedis cache expiry review', CODE).passed
    assert not score(BY_NAME['corrected_fact'], '- [Claim] Other project budget $12,500', CODE).passed


def test_empty_recall_after_a_server_error_does_not_pass_deletion(eval_env):
    with oracle() as server:
        route = server._route

        def broken(method, path, body):
            if path == '/retrieve/context':
                return 500, {'error': 'corrupted index'}
            return route(method, path, body)

        server._route = broken
        report = run_suite(base_url=server.url, api_key='mg_offline', home=eval_env, wait_s=3, only='deletion')
    assert report['input_ready']
    assert report['passed'] == 0
    assert report['outcomes'][0]['retrieval_outcome'] == 'error'


def test_empty_recall_after_a_deadline_does_not_pass_deletion(eval_env, monkeypatch):
    monkeypatch.setenv('MINDGRAPH_RECALL_DEADLINE_MS', '250')
    with oracle() as server:
        server.delays['/retrieve/context'] = 0.5
        report = run_suite(base_url=server.url, api_key='mg_offline', home=eval_env, wait_s=3, only='deletion')
    assert report['input_ready']
    assert report['passed'] == 0
    assert report['outcomes'][0]['retrieval_outcome'] == 'timeout'
