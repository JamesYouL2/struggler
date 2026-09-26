"""The shard cut, the spares and the waves: what a reading is owed.

`scripts/shard_plan.py` is where the cut lives -- `experiments.yml`'s plan
step, `pool_reports.py` and `tests/test_experiment_registry.py` all ask it,
because a second spelling of the cut is the drift shape. What is pinned
here is what the counting depends on: cores never straddle the gap between
`seeds` and `held`, the reserve becomes at most two WHOLE spare shards (the
loss that actually happens is a whole shard), spares play in the arm's last
wave so an interim reads its core, the information fraction is the one the
look really sees, and plan order puts every core seed before any spare.
"""
from __future__ import annotations

import pytest

from conftest import load_script
from shard_plan import (DEFAULT_SHARD, SPARE_SHARDS, assert_disjoint, build, cut, fraction,
                        seed_order, split_waves)


def test_the_default_is_64_seed_shards_and_two_spares():
    assert (DEFAULT_SHARD, SPARE_SHARDS) == (64, 2)
    specs = cut(['92000-92255'], '94000-94127')
    assert [s['seeds'] for s in specs] == ['92000-92063', '92064-92127', '92128-92191',
                                           '92192-92255', '94000-94063', '94064-94127']
    assert [s['role'] for s in specs] == ['core'] * 4 + ['spare'] * 2


def test_cores_never_straddle_the_gap_between_blocks():
    specs = cut(['92000-92063', '94000-94063'], '', size=128)
    assert [s['seeds'] for s in specs] == ['92000-92063', '94000-94063']
    # No reserve declared: exactly the arm's core, no spares.
    assert all(s['role'] == 'core' for s in specs)


def test_a_short_reserve_gives_a_short_spare_and_a_long_one_is_capped():
    # The registry's older arms declared 18-seed reserves: one short spare.
    assert [s['seeds'] for s in cut(['92000-92127'], '94000-94017') if s['role'] == 'spare'] \
        == ['94000-94017']
    # More than two shards' worth is not played: two is the cover asked for.
    spares = [s for s in cut(['92000-92127'], '94000-94999') if s['role'] == 'spare']
    assert [s['seeds'] for s in spares] == ['94000-94063', '94064-94127']


def _arm(slug='on', **extra):
    return {'slug': slug, 'seeds': '92000-92255', 'reserve': '94000-94127', **extra}


def test_spares_play_in_the_last_wave_and_the_core_splits_by_half():
    wave1, wave2 = split_waves(build([_arm()]), waves=True)
    assert [(s['seeds'], s['role']) for s in wave1] == [('92000-92063', 'core'),
                                                         ('92064-92127', 'core')]
    assert [s['role'] for s in wave2] == ['core', 'core', 'spare', 'spare']
    assert {s['wave'] for s in wave1} == {1} and {s['wave'] for s in wave2} == {2}


def test_without_waves_everything_is_wave_one():
    wave1, wave2 = split_waves(build([_arm()]), waves=False)
    assert wave2 == [] and len(wave1) == 6


def test_the_fraction_is_what_the_interim_really_sees():
    """Five core shards split 3/2: the look sees 60% of the information,
    and the boundary must be computed for 0.6, not 0.5 (audit F5)."""
    wave1, wave2 = split_waves(build([_arm(seeds='92000-92319')]), waves=True)
    assert fraction(wave1 + wave2, 'on') == pytest.approx(0.6)
    # Spares are not information the interim was owed.
    wave1, wave2 = split_waves(build([_arm()]), waves=True)
    assert fraction(wave1 + wave2, 'on') == pytest.approx(0.5)


def test_plan_order_puts_every_core_seed_before_any_spare():
    shards = build([_arm(seeds='92000-92003', reserve='91000-91001', shard=2)])
    order, target = seed_order(shards, 'on')
    # The reserve sits BELOW the core numerically; plan order still counts
    # it last, so a spare can never displace a core seed that finished.
    assert order == [92000, 92001, 92002, 92003, 91000, 91001]
    assert target == 4


def test_a_skipped_wave_two_is_not_owed():
    wave1, _ = split_waves(build([_arm()]), waves=True)
    order, target = seed_order(wave1, 'on')
    assert target == 128 and order[-1] == 92127


def test_role_and_wave_ride_along_without_entering_the_cache_key():
    """`arm_identity` hashes seeds, weights and openings; a spare on seeds X
    must hit the cache a core shard on X filled."""
    identity = load_script('arm_identity')
    spare = next(s for s in build([_arm()]) if s['role'] == 'spare')
    as_core = {**spare, 'role': 'core', 'wave': 1}

    def key(s):
        return identity.cache_key(src_tree='t', seeds=s['seeds'], weights=s['weights'],
                                  openings=s['openings'])
    assert key(spare) == key(as_core)


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
