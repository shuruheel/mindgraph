"""Behavioral gates for the MCP 0.27 port, including response-only contracts."""

import json

import pytest
from hermes_mindgraph_plugin import handlers_read
from hermes_mindgraph_plugin.handlers_write import handle_remember
from hermes_mindgraph_plugin.memory_tool import MemoryRuntimeConfig, handle_memory_tool


@pytest.mark.parametrize('confirm', [None, False, 'true', 1])
def test_forget_requires_boolean_confirmation(runtime, fake_client, confirm):
    fake_client.responses['forget'] = {'uid': 'n1', 'edge_uids': ['e1']}
    result = json.loads(handle_remember(runtime, {'action': 'forget', 'uid': 'n1', 'confirm': confirm}))
    assert result['confirmation_required'] and not result['removed']
    assert result['preview']['edge_uids'] == ['e1']
    assert fake_client.called('forget')[0][1]['dry_run'] is True


def test_confirmed_forget_has_undo_hint_but_dry_run_still_wins(runtime, fake_client):
    fake_client.responses['forget'] = {'uid': 'n1', 'edge_uids': ['e1']}
    args = {'action': 'forget', 'uid': 'n1', 'confirm': True}
    result = json.loads(handle_remember(runtime, args))
    assert 'restore' in result['undo_hint']
    assert 'dry_run' not in fake_client.called('forget')[0][1]
    preview = json.loads(handle_remember(runtime, {**args, 'dry_run': True}))
    assert preview == fake_client.responses['forget']
    assert fake_client.called('forget')[1][1]['dry_run'] is True


def test_restore_deduplicates_edges_and_reports_partial_failure(runtime, fake_client):
    def evolve(**kwargs):
        if kwargs['uid'] == 'bad':
            raise RuntimeError('edge unavailable')
        return {}

    fake_client.responses['evolve'] = evolve
    result = json.loads(handle_remember(runtime, {
        'action': 'restore', 'uid': ' n1 ', 'edge_uids': ['e1', 'bad', 'e1', '', None, 'e2'], 'agent_id': 'a',
    }))
    assert fake_client.calls[0] == ('restore', ('n1',), {'agent_id': 'a'})
    assert result['edges_restored'] == 2
    assert result['edges_failed'] == [{'uid': 'bad', 'error': 'edge unavailable'}]
    assert all(kwargs['agent_id'] == 'a' for _, kwargs in fake_client.called('evolve'))


@pytest.mark.parametrize('args', [
    {'uid': ''}, {'uid': 'n1', 'edge_uids': 'e1'},
    {'uid': 'n1', 'edge_uids': [f'e{i}' for i in range(501)]},
])
def test_invalid_restore_does_not_write(runtime, fake_client, args):
    assert 'error' in json.loads(handle_remember(runtime, {'action': 'restore', **args}))
    assert fake_client.calls == []


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(handlers_read.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(handlers_read.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


@pytest.mark.parametrize('handler', [handlers_read.handle_ingest, handlers_read.handle_synthesize])
def test_job_wait_stops_on_completion(runtime, fake_client, clock, handler):
    jobs = iter([{'status': 'running'}, {'status': 'completed', 'progress': {'nodes_created': 3}}])
    fake_client.responses['get_job'] = lambda _: next(jobs)
    result = json.loads(handler(runtime, {'action': 'job_status', 'job_id': 'j', 'wait_seconds': 50}))
    assert result == {'status': 'completed', 'progress': {'nodes_created': 3}, 'waited_seconds': 2}
    assert len(fake_client.called('get_job')) == 2


def test_wait_is_capped_and_returns_progress_and_next(runtime, fake_client, clock):
    fake_client.responses['get_job'] = {'status': 'running', 'progress': {'processed_chunks': 2}}
    result = json.loads(handlers_read.handle_ingest(runtime, {
        'action': 'job_status', 'job_id': 'j', 'wait_seconds': 999,
    }))
    assert clock[0] == result['waited_seconds'] == 50
    assert result['still_running'] is True and 'job_status' in result['next']
    assert result['progress'] == {'processed_chunks': 2}


@pytest.mark.parametrize('wait', [None, 0, -1, True, '10', float('nan'), float('inf'), .5])
def test_invalid_or_zero_wait_is_one_immediate_read(runtime, fake_client, clock, wait):
    fake_client.responses['get_job'] = {'status': 'running'}
    result = json.loads(handlers_read.handle_synthesize(runtime, {
        'action': 'job_status', 'job_id': 'j', 'wait_seconds': wait,
    }))
    assert result == {'status': 'running'}
    assert clock[0] == 0 and len(fake_client.calls) == 1


def brief(runtime, **args):
    return json.loads(handle_memory_tool(runtime, {'action': 'context', 'mode': 'brief', **args}, MemoryRuntimeConfig()))


def test_brief_filters_document_goals_and_orders_stated_before_inferred(runtime, fake_client):
    fake_client.responses['get_goals'] = [
        {'uid': 'book', 'label': 'Book goal', 'props': {'source': 'document'}},
        {'uid': 'inferred', 'label': 'Inferred goal', 'updated_at': 99, 'props': {'source': 'session'}},
        {'uid': 'imported', 'label': 'Imported goal', 'updated_at': 100, 'props': {'source': 'import'}},
        {'uid': 'stated', 'label': 'Stated goal', 'updated_at': 1},
    ]
    result = brief(runtime, project_uid='p1', scope_uids=['p1', 'p2'], agent_id='a')
    assert 'Book goal' not in result['result']
    assert result['result'].index('Stated goal') < result['result'].index('Inferred goal')
    assert result['result'].index('Stated goal') < result['result'].index('Imported goal')
    assert fake_client.called('plan')[0][1] == {
        'action': 'resume_work', 'limit': 6, 'scope_uids': ['p1', 'p2'], 'agent_id': 'a',
    }
    assert result['structured']['retrieval_trace']['strategy'] == 'brief'


def test_brief_reports_partial_failure_and_total_failure(runtime, fake_client):
    fake_client.responses['get_goals'] = RuntimeError('offline')
    result = brief(runtime)
    assert any(w['code'] == 'brief_section_unavailable' and 'goals' in w['message']
               for w in result['structured']['warnings'])
    for method in ['plan', 'get_open_decisions', 'retrieve']:
        fake_client.responses[method] = RuntimeError('offline')
    assert 'every section failed' in brief(runtime)['error']


def test_brief_is_bounded_and_counts_unshown_items(runtime, fake_client):
    fake_client.responses['retrieve'] = [{'uid': f'p{i}', 'label': 'long preference ' * 40} for i in range(8)]
    result = brief(runtime, max_output_chars=512)
    assert len(result['result']) <= 512
    assert '6 shown, 2 more' in result['result']
    assert result['structured']['budget']['omitted_items'] > 0


def test_unsupported_workspace_scope_never_falls_back_to_unscoped_read(runtime, fake_client):
    result = brief(runtime, scope='workspace')
    assert 'scope_uids' in result['error']
    assert fake_client.calls == []


@pytest.mark.parametrize('edges, count', [([], 0), (['e1', 'e1', 'e2'], 2)])
def test_restore_returns_edge_count(runtime, edges, count):
    result = json.loads(handle_remember(runtime, {'action': 'restore', 'uid': 'n1', 'edge_uids': edges}))
    assert result['edges_restored'] == count
    assert 'edges_failed' not in result
