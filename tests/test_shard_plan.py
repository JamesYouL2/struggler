"""The tail reserve: one lost game costs a backfill, not a sample.

`scripts/shard_plan.py` is where the shard cut lives -- `experiments.yml`'s
plan step and `tests/test_experiment_registry.py` both ask it, because a
second spelling of the cut is the drift shape. What is pinned here is what
the 255-of-256 fix depends on: each shard gets ITS OWN spares (a backfill
must never count one seed twice), cores never straddle the gap between
`seeds` and `held`, the counting target is the core's size even when the
core is short, and a reserve is refused when it lands in anybody's core.
"""
from __future__ import annotations

import pytest

from shard_plan import assert_disjoint, cut


def test_each_core_takes_its_own_slice_of_the_reserve():
    specs = cut(['92000-92255'], '94000-94003', size=128)
    assert len(specs) == 2
    assert [s['seeds'] for s in specs] == ['92000-92127', '92128-92255']
    assert [s['reserve'] for s in specs] == ['94000-94001', '94002-94003']
    assert all(s['target'] == 128 for s in specs)


def test_cores_never_straddle_the_gap_between_blocks():
    specs = cut(['92000-92063', '94000-94063'], '', size=128)
    assert [s['seeds'] for s in specs] == ['92000-92063', '94000-94063']
    # No reserve declared: exactly the pre-reserve behaviour.
    assert all(s['reserve'] == '' for s in specs)


def test_a_short_last_core_still_counts_short():
    specs = cut(['92000-92200'], '94000-94003', size=128)
    assert len(specs) == 2
    assert specs[1]['seeds'] == '92128-92200'
    assert specs[1]['target'] == 73


def test_a_reserve_that_runs_out_spares_the_earliest_shards_only():
    specs = cut(['92000-92255'], '94000-94000', size=128)
    assert [s['reserve'] for s in specs if s['reserve']] == ['94000-94000']
    assert sum(1 for s in specs if not s['reserve']) == 1


def test_a_reserve_inside_a_core_is_refused():
    # The shape a DERIVED reserve would have had: 9700-9827 with held
    # 9828-9891 sits flush, so "spares just past hi" lands inside the held
    # block -- one seed counted twice in one pool.
    with pytest.raises(AssertionError, match='overlap'):
        assert_disjoint([
            {'seeds': '9700-9827', 'held': '9828-9891', 'reserve': '9828-9829'},
        ])


def test_identical_blocks_share_and_that_is_not_a_collision():
    # Pairing IS two arms on the same text.
    assert_disjoint([
        {'seeds': '92000-93023', 'reserve': '94000-94017'},
        {'seeds': '92000-93023', 'reserve': '94000-94017'},
    ])
