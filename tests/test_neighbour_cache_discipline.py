"""`_delta`'s neighbour-diff cache: the key has to carry what the value reads.

The cache stores, per `(country, side, control after, our influence present,
theirs present)`, the per-neighbour differences a trial placement makes. It
is worth having -- 44.7% of the 402,097 neighbour sweeps in one self-play
game repeat a key already computed -- and it is the ninth cache in a file
whose commonest defect is **a cached value keyed on less state than it
reads**. Shape 6 in docs/notes/claude/bug-shapes.md has shipped twice.

The property that makes the key legal is not "neighbours rarely change".
It is exact, and `_delta`'s own docstring already states it:

> Another country's `country_value` reads `cid` only through
> `evaluator.access`, and `access` reads three things about it: who
> controls it, and whether each side holds any influence there.

Three facts, and they are the three in the key -- the same three the skip
above the cache has always turned on. So this file checks the property
rather than the code: if `access` ever starts reading a fourth thing about
a country, the key is too small and these tests must fail.

**Since 2026-09-26 the cache is unreachable.** `access` was deleted, no
country's `country_value` reads another's influence, `VALUE_RADIUS` is 0 and
`others_moved_by` is empty, so `_delta` never sweeps a neighbour. The three
tests that need a neighbour to move are skipped while the radius is 0 -- a
`skipif` on the radius rather than a deletion, so they re-arm by themselves
if a term that reads a neighbour ever comes back. Deleting the cache, and
these tests with it, is the follow-up simplification.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic.policy import StrategicWeights

_UNREACHABLE = pytest.mark.skipif(
    ev.VALUE_RADIUS == 0,
    reason='VALUE_RADIUS is 0 since `access` was deleted (2026-09-26): no '
           'neighbour value can move, so the neighbour cache is never reached')


@_UNREACHABLE
def test_a_neighbours_value_moves_only_on_the_three_facts_in_the_key():
    """The key's premise, checked directly against `country_value`.

    For a neighbour `j`, sweep every influence pair at `i` that the game can
    reach and group the resulting `country_value(j)` by the triple the key
    uses. Two placements at `i` that agree on the triple must leave `j` on
    the SAME float -- not close, the same, because rankings are decided by
    strict comparison.
    """
    t = ev.terrain()
    w = StrategicWeights()
    urgency = ev.ones(t)
    # A country with neighbours that hold influence, so `access` has work to
    # do in both directions.
    i = t.index['Italy']
    neighbours = list(ev.others_moved_by(t, i))
    assert neighbours, 'Italy has dependents or this test is vacuous'

    pos = ev.Position(t)
    pos.place(t.index['France'], 2, 1)
    pos.place(t.index['West_Germany'], 1, 2)
    pos.place(t.index['Greece'], 0, 2)
    pos.place(t.index['Austria'], 1, 1)

    by_key: dict[tuple, dict[int, float]] = {}
    for us in range(6):
        for ussr in range(6):
            pos.place(i, us, ussr)
            key = (pos.control[i], us > 0, ussr > 0)
            values = {j: ev.country_value(t, pos, j, ev.US, w, urgency)
                      for j in neighbours}
            if key in by_key:
                assert by_key[key] == values, (
                    f'two placements at Italy agreeing on {key} left a neighbour '
                    f'on a different value, so the cache key is too small: '
                    f'{by_key[key]} vs {values}')
            else:
                by_key[key] = values
    assert len(by_key) > 1, 'the sweep never changed the triple; nothing was tested'


@_UNREACHABLE
def test_distinct_triples_really_do_move_a_neighbour():
    """The negative control. If every triple gave the same neighbour values
    the test above would pass on a key of nothing at all."""
    t = ev.terrain()
    w = StrategicWeights()
    urgency = ev.ones(t)
    i, j = t.index['Italy'], t.index['France']
    pos = ev.Position(t)
    pos.place(j, 2, 0)
    pos.place(t.index['West_Germany'], 1, 0)

    pos.place(i, 0, 0)
    empty = ev.country_value(t, pos, j, ev.US, w, urgency)
    pos.place(i, 4, 0)            # US control of Italy: a different triple
    controlled = ev.country_value(t, pos, j, ev.US, w, urgency)
    assert empty != controlled, (
        "France's value did not move when Italy went from empty to US-controlled; "
        'the positive test above is then vacuous')


# The cache is per-decision and lives inside `rank_actions`, so the guard can
# only be provoked from within one -- which is the mistake an earlier version
# of `test_base_cache_discipline.py` made and passed vacuously for.
PROBE = """
import sys; sys.path.insert(0, %r)
import dataclasses
from struggler.bots.strategic import evaluator as ev, policy as pol
from struggler.bots.strategic import StrategicWeights
from conftest import bare_engine
from struggler.engine import Side
assert ev.DIGEST and pol.CHECK_SNAPSHOT, 'the checker must be on'

w = dataclasses.replace(StrategicWeights(), reply_model=3.0)


class Collapsing(dict):
    '''A cache keyed on LESS than the value reads: `control` dropped, so a
    trial that takes control reads the sum taken before it did.'''
    def get(self, key, default=None):
        return dict.get(self, key[:2], default)
    def __setitem__(self, key, value):
        dict.__setitem__(self, key[:2], value)


class Poisoned(pol.StrategicPlayer):
    @property
    def _base_neighbours(self):
        return self.__dict__.get('_bn')
    @_base_neighbours.setter
    def _base_neighbours(self, value):
        self.__dict__['_bn'] = Collapsing() if isinstance(value, dict) else value


def board():
    e = bare_engine()
    e.board.influence['Italy']['US'] = 2
    e.board.influence['France']['US'] = 1
    e.board.influence['Greece']['USSR'] = 1
    e.board.influence['West_Germany']['USSR'] = 2
    e.begin_influence_operations(Side.USSR, 4)
    return e


pol.StrategicPlayer(w).rank_actions(board().observe(Side.USSR))
print('OK UNPATCHED')

try:
    Poisoned(w).rank_actions(board().observe(Side.USSR))
except AssertionError as exc:
    assert 'moved while cached' in str(exc), exc
    print('GUARD FIRED')
else:
    print('GUARD SILENT')
"""


@_UNREACHABLE
def test_the_checker_is_on_and_the_real_path_does_not_trip_its_own_guard():
    """With `STRUGGLER_CHECK_SNAPSHOT=1` every cache hit is recomputed and
    compared, so a real ranking exercising the cache is itself the check that
    the key is big enough. This runs one; it must stay silent.

    Subprocess because `STRUGGLER_CHECK_SNAPSHOT` is read at import.
    """
    env = dict(os.environ, STRUGGLER_CHECK_SNAPSHOT='1')
    result = subprocess.run(
        [sys.executable, '-c', PROBE % str(pathlib.Path(__file__).parent)],
        capture_output=True, text=True, env=env,
        cwd=str(pathlib.Path(__file__).parent.parent))
    assert result.returncode == 0, result.stderr[-3000:]
    assert 'OK UNPATCHED' in result.stdout, (
        f'the real code path now trips its own guard.\n{result.stdout}')
    assert 'GUARD FIRED' in result.stdout, (
        'the key was shrunk to less than the value reads and the recompute '
        f'did not notice, so CHECK_SNAPSHOT is not guarding this cache.\n'
        f'{result.stdout}')


def test_the_cache_dies_with_the_base_it_describes():
    """`_invalidate_base` is what anything moving the board mid-ranking owes
    `delta`. The neighbour cache is keyed on the board as synced exactly as
    `_base_country` is, so it has to be cleared in the same place -- and by
    the same call, not by a second one someone has to remember."""
    import struggler.bots.strategic.policy as pol
    player = pol.StrategicPlayer(StrategicWeights())
    player._base_regions, player._base_country = {}, {}
    player._base_neighbours = {('x',): (1.0,)}
    player._invalidate_base()
    assert player._base_neighbours == {}, (
        '`_invalidate_base` left the neighbour cache describing a board that '
        'has moved')


def test_the_cache_is_dropped_when_the_other_base_caches_are():
    """Every site that sets `_base_country` must set this one. Checked by
    reading the source rather than by exercising four code paths, because a
    fifth site added later is exactly the failure this catches."""
    source = (pathlib.Path(__file__).parents[1] / 'src' / 'struggler' / 'bots'
              / 'strategic' / 'policy.py').read_text()
    country = source.count('_base_country')
    neighbours = source.count('_base_neighbours')
    assert neighbours >= country - 3, (
        f'_base_country appears {country} times and _base_neighbours '
        f'{neighbours}: a lifecycle site was probably missed. The two caches '
        f'describe the same board and must be created and dropped together.')
