"""The shard cache key, which is the thing that decides whether a cached
reading is the same reading.

A cache that serves a stale shard is strictly worse than no cache: the
pooled table still prints, the interval still looks clean, and the number
is from a different bot. So the property under test is not "the key is
stable" but **the key covers everything that can change play** -- one test
per input, each asserting that moving it moves the key.

The stability half matters too, and in one specific way: `{'a': 1}` and
`{'a': 1.0}` are the same weights, and a dict's insertion order is not part
of its meaning. If those hashed differently the cache would simply never
hit, which is a silent cost rather than a wrong answer, but it is the whole
point of the file.
"""
from __future__ import annotations

import json

import pytest

from conftest import load_script

ARM = load_script('arm_identity')

BASE = {'src_tree': 'tree0', 'seeds': '64000-64127', 'weights': {'region': 1.0},
        'bot_ref_sha': '', 'anchor_sha': 'bc5ef93', 'openings': 'US=italy,USSR=austria'}


def key(**over) -> str:
    return ARM.cache_key(**{**BASE, **over})


def test_the_same_shard_hashes_the_same():
    assert key() == key()


@pytest.mark.parametrize('field,moved', [
    ('src_tree', 'tree1'),
    ('seeds', '64128-64255'),
    ('weights', {'region': 1.5}),
    ('bot_ref_sha', '30aa9e8'),
    ('anchor_sha', '07d553a'),
    ('openings', 'US=lebanon,USSR=poland'),
    ('version', 'v2'),
])
def test_every_input_that_can_change_play_changes_the_key(field, moved):
    assert key(**{field: moved}) != key(), (
        f'{field} moved and the key did not: a cached shard from the old '
        f'{field} would be served for the new one')


def test_a_dropped_weight_is_not_the_same_as_a_zero_one():
    """`{'access_chain': 0.0}` and `{}` are the same bot only because the
    default happens to be 0.0 today. Defaults move; the key must not assume
    this one has not."""
    assert key(weights={}) != key(weights={'access_chain': 0.0})


def test_weight_order_and_int_float_spelling_do_not_change_the_key():
    assert key(weights={'region': 1, 'access': 2}) == key(weights={'access': 2.0, 'region': 1.0})


def test_no_weights_and_empty_weights_are_the_same_arm():
    """`plan` emits `'weights': a.get('weights') or {}`, so an arm with no
    weights arrives as `{}`; a caller passing None must land on the same key."""
    assert key(weights=None) == key(weights={})


def test_a_missing_src_tree_is_refused_rather_than_hashed_as_blank():
    """An empty tree hash is what a failed `git rev-parse` produces. Hashing
    it would make every arm in every revision share one key -- the exact
    failure this file exists to prevent, arrived at by an error nobody
    checked."""
    with pytest.raises(ValueError):
        key(src_tree='')
    with pytest.raises(ValueError):
        key(seeds='')


def test_the_cli_agrees_with_the_library_on_a_real_plan_shard(capsys):
    """`plan` emits shard objects and the runner pipes one in as JSON, so the
    workflow's key comes from the CLI while every test here comes from the
    library. If those two ever disagree the suite is green and the cache is
    wrong, which is why this asserts the printed line."""
    shard = {'slug': 'fit-bc-on', 'shard': 3, 'of': 8, 'seeds': '64384-64511',
             'weights': {'country_vp_scale': 2.795}, 'anchor': 'bc5ef93',
             'bot_ref': '', 'openings': 'US=italy,USSR=austria',
             'compare_to': 'fit-bc-base', 'logs': False}
    assert ARM.main(['--shard', json.dumps(shard), '--src-tree', 'tree0',
                     '--anchor-sha', 'bc5ef93deadbeef']) == 0
    printed = capsys.readouterr().out.strip()
    assert printed == ARM.cache_key(
        src_tree='tree0', seeds=shard['seeds'], weights=shard['weights'],
        anchor_sha='bc5ef93deadbeef', openings=shard['openings'])
    assert printed.startswith('exp-')


def test_the_key_ignores_what_cannot_change_the_report():
    """`slug`, `shard`, `of` and `compare_to` are bookkeeping: two arms that
    differ only in name play the same games. Excluding them is what lets
    `leak-iso-fixed` reuse a shard `fit-intransitive-on` already played."""
    a = {'slug': 'a', 'shard': 0, 'of': 8, 'seeds': '1-2', 'weights': {},
         'anchor': '', 'bot_ref': '', 'openings': '', 'compare_to': 'x'}
    b = {**a, 'slug': 'b', 'shard': 5, 'of': 16, 'compare_to': ''}
    both = {ARM.cache_key(src_tree='t', seeds=s['seeds'], weights=s['weights'],
                          openings=s['openings']) for s in (a, b)}
    assert len(both) == 1


def test_logs_are_outside_the_key_which_is_a_hole_the_workflow_has_to_close():
    """`"logs": true` changes the ARTIFACT (tens of MB of INFO logs) without
    changing the REPORT, so it is deliberately not in the key -- a logged run
    and an unlogged one on the same bot are the same measurement.

    The cost is that a hit serves the report WITHOUT the logs. The key cannot
    express that; only the workflow can, by not restoring for an arm that
    asked for logs. This asserts the hole is where it is documented to be, so
    that closing it in the key (or the workflow) is a deliberate change and
    not a surprise."""
    def key_for(logs):
        shard = {'seeds': '1-2', 'weights': {}, 'openings': '', 'logs': logs}
        return ARM.cache_key(src_tree='t', seeds=shard['seeds'],
                             weights=shard['weights'], openings=shard['openings'])
    assert key_for(True) == key_for(False)
