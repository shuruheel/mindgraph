"""A current assertion must survive relevant historical aliases and packing."""
from copy import deepcopy

import pytest
from hermes_mindgraph_plugin.recall import RecallConfig, RecallEngine, build_query, relevant, select_items
from test_recall import node, response, spawn

QUERY = build_query('What is the approved budget for the Orion pilot? Answer using your available context. Do not use tools.')


def fixture():
    old = [node(f'old-{i}', 'Orion pilot approved budget', 'The approved budget for the Orion pilot is $8,000.',
                superseded={'head_uid': 'new', 'heads': ['new'], 'head_label': 'Untrusted display label'})
           for i in range(5)]
    current = node('new', 'Orion pilot budget is $12,500', 'The Orion pilot budget is $12,500.',
                   kind='Claim', current=True, supersedes_at_t=[n['uid'] for n in old])
    return response(*old, current)


def test_actual_successor_inherits_relevance_and_precedes_five_retired_aliases():
    raw = fixture()
    assert not relevant(QUERY, raw['graph']['nodes'][-1]['summary'])
    result = RecallEngine(lambda q, n: raw, RecallConfig(limit=5), spawn).recall('s', QUERY.query)
    assert len(result.items) == 5
    assert result.items[0].uid == 'new' and not result.items[0].retired
    assert '$12,500' in result.items[0].assertion
    assert 'Untrusted display label' not in result.items[0].assertion
    assert all(item.retired for item in result.items[1:])
    assert len(result.text) <= 4000


@pytest.mark.parametrize('defect', ['missing', 'deleted', 'unrelated', 'no_reciprocal', 'not_current',
                                   'retired', 'invalid', 'refuted', 'cycle', 'fan_in', 'conflict',
                                   'graph_conflict', 'duplicate', 'legacy'])
def test_no_successor_promotion_without_unambiguous_live_reciprocal_nodes(defect):
    raw = fixture()
    nodes = raw['graph']['nodes']
    head = nodes[-1]
    if defect == 'missing':
        nodes.pop()
    elif defect == 'deleted':
        head['tombstone_at'] = 1
    elif defect == 'unrelated':
        head.update(uid='elsewhere', label='Sirius launch calendar', summary='Sirius launches on Tuesday.')
    elif defect == 'no_reciprocal':
        head['supersedes_at_t'] = []
    elif defect == 'not_current':
        head.pop('current')
    elif defect in ('retired', 'cycle'):
        head['superseded'] = {'head_uid': 'old-0', 'heads': ['old-0']}
    elif defect == 'invalid':
        head['currently_valid'] = False
    elif defect == 'refuted':
        head['truth_status'] = 'refuted'
    elif defect == 'fan_in':
        for old in nodes[:-1]:
            old['superseded']['heads'].append('another')
    elif defect == 'conflict':
        head['conflict'] = {'with': 'another'}
    elif defect == 'graph_conflict':
        raw['conflicts'] = [{'kind': 'unreviewed_fan_in', 'a_uid': 'new', 'b_uid': 'another'}]
    elif defect == 'duplicate':
        nodes.append(deepcopy(head))
    elif defect == 'legacy':
        for old in nodes[:-1]:
            old.update(superseded=True, superseded_by='new')
    items = select_items(raw, QUERY)
    assert all(item.uid.startswith('old-') for item in items)
    assert not any(item.requires_uid for item in items)


def test_unrelated_parent_cannot_launder_successor_relevance():
    raw = fixture()
    for old in raw['graph']['nodes'][:-1]:
        old.update(label='Sirius launch calendar', summary='Sirius launches on Tuesday.')
    assert select_items(raw, QUERY) == []


def test_packing_never_shows_retired_alias_without_its_required_head():
    raw = fixture()
    head = raw['graph']['nodes'][-1]
    head['summary'] += ' Long detail.' * 30
    engine = RecallEngine(lambda q, n: raw, RecallConfig(limit=5, max_chars=180), spawn)
    result = engine.recall('s', QUERY.query)
    assert not result.items and not result.text


def test_one_slot_keeps_current_fact_and_history_is_available_with_room():
    raw = fixture()
    result = RecallEngine(lambda q, n: raw, RecallConfig(limit=1), spawn).recall('s', QUERY.query)
    assert [item.uid for item in result.items] == ['new']
    result = RecallEngine(lambda q, n: raw, RecallConfig(limit=2), spawn).recall('s', 'What was the Orion pilot budget?')
    assert [item.uid for item in result.items] == ['new', 'old-0']
    assert result.items[1].retired and '$8,000' in result.items[1].assertion


def test_unseen_history_reincludes_previously_shown_head_and_compression_resets():
    raw = fixture()
    engine = RecallEngine(lambda q, n: raw, RecallConfig(limit=2), spawn)
    assert [i.uid for i in engine.recall('s', QUERY.query).items] == ['new', 'old-0']
    assert [i.uid for i in engine.recall('s', QUERY.query).items] == ['new', 'old-1']
    engine.forget_injected('s')
    assert [i.uid for i in engine.recall('s', QUERY.query).items] == ['new', 'old-0']


def test_one_slot_does_not_repeat_head_forever_when_history_cannot_fit():
    raw = fixture()
    engine = RecallEngine(lambda q, n: raw, RecallConfig(limit=1), spawn)
    assert [i.uid for i in engine.recall('s', QUERY.query).items] == ['new']
    assert not engine.recall('s', QUERY.query).items
    assert not engine.recall('s', QUERY.query).items


def test_character_cap_does_not_repeat_head_without_new_history():
    raw = fixture()
    head = select_items(raw, QUERY)[0]
    engine = RecallEngine(lambda q, n: raw, RecallConfig(limit=5, max_chars=len(head.line) + 50), spawn)
    assert [i.uid for i in engine.recall('s', QUERY.query).items] == ['new']
    assert not engine.recall('s', QUERY.query).items
