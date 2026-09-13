"""An influence change is worth exactly what it moves the board potential by.

`delta` prices one country's change incrementally; `value` prices the whole
board. With the context fixed (one prepared observation, `reply_model=0` so
no reply term is mixed in), the first must be the difference of the second,
because every placement search, coup and realignment expectation adds
deltas up, and the event sandbox prices the same board change as a
difference of the whole potential. Where they disagree, a sequence of
placements is worth something different in each order despite reaching the
same board, and an event is worth something different from the Ops that
make the same change.

Codex's audit (docs/notes/codex/2026-09-13-strategic-math-followup.md)
found two ways they disagreed:

- **M1**: `delta` recomputed only the changed country's own value, but
  other countries' access reads it -- controlling Nigeria consumes a US
  Cameroon's access to an uncontrolled Nigeria. Raw delta 13.95 against a
  board difference of 8.44.
"""
from __future__ import annotations

import dataclasses
import random

import pytest

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import evaluator as ev
from struggler.engine import Engine, Side

# Weight overrides the exactness properties are asserted under.
POTENTIALS = (
    pytest.param({'region': 0.}, id='no-region-vp'),
)


def _empty_engine(seed: int = 1) -> Engine:
    """Codex's fixture: a turn-1 engine with every influence point removed."""
    engine = Engine(seed=seed)
    for inf in engine.board.influence.values():
        inf.update(US=0, USSR=0)
    return engine


def _player(**weights) -> StrategicPlayer:
    return StrategicPlayer(dataclasses.replace(StrategicWeights(), reply_model=0, **weights))


def _as_in_a_ranking(bot: StrategicPlayer) -> None:
    """Open the per-decision base caches exactly as `rank_actions` does, so
    `delta` runs its cached path: before-values of the changed country and
    of its neighbours are then read from `_base_country` on repeat calls."""
    bot._base_regions, bot._base_margins, bot._base_country = {}, {}, {}
    bot._base_digest = bot._position.digest


def _applied(bot: StrategicPlayer, side: Side, cid: str, own: int, opp: int):
    """The clamped counts `delta(own, opp)` moves `cid` to."""
    inf = bot.board.influence[cid]
    mine, theirs = side.value, side.opponent.value
    counts = {mine: max(0, inf[mine] + own), theirs: max(0, inf[theirs] + opp)}
    return counts['US'], counts['USSR']


def _board_difference(bot: StrategicPlayer, side: Side, cid: str, own: int, opp: int) -> float:
    """`value(after) - value(before)` for the change, board put back."""
    was = dict(bot.board.influence[cid])
    before = bot.value(bot.board, side)
    bot._set_influence(cid, *_applied(bot, side, cid, own, opp))
    try:
        return bot.value(bot.board, side) - before
    finally:
        bot._set_influence(cid, was['US'], was['USSR'])


def _random_observation(rng: random.Random):
    """A random board in a random scoring context, from either seat."""
    engine = _empty_engine(seed=rng.randrange(1000))
    t = ev.terrain()
    for cid in rng.sample(t.ids, rng.randint(4, 45)):
        engine.board.influence[cid]['US'] = rng.choice((0, 0, 1, 1, 2, 3, 4, 5))
        engine.board.influence[cid]['USSR'] = rng.choice((0, 0, 1, 1, 2, 3, 4, 5))
    engine.turn = rng.randint(1, 10)
    side = rng.choice((Side.US, Side.USSR))
    scoring = ['Asia_Scoring', 'Southeast_Asia_Scoring', 'Europe_Scoring',
               'Middle_East_Scoring', 'Africa_Scoring']
    engine.hands[side.value] = rng.sample(scoring, rng.randint(0, 2))
    engine.discard_pile = [c for c in scoring
                           if c not in engine.hands[side.value] and rng.random() < 0.3]
    if rng.random() < 0.2:
        engine.game_effects['formosan_resolution'] = True
    if rng.random() < 0.2:
        engine.game_effects['shuttle_diplomacy'] = True
    return engine.observe(side), side


@pytest.mark.parametrize('overrides', POTENTIALS)
def test_delta_is_the_board_difference_on_random_boards(overrides):
    """The contract, on generated positions: every kind of change that moves
    what another country's access reads -- first footholds, control
    transitions, a route added beside a redundant one, the last enemy point
    removed -- in Southeast Asian and other Asian countries among the rest,
    from the cold path and from a ranking's warm caches.

    Seeded, not hypothesis: the value of the loop is the category counts
    asserted at the end, which say the cases were actually generated."""
    rng = random.Random(20260913)
    t = ev.terrain()
    seen = dict.fromkeys(('first foothold', 'control transition', 'redundant route',
                          'last enemy point', 'neighbour moved', 'southeast asia',
                          'other asia', 'warm cache'), 0)
    for _board in range(60):
        obs, side = _random_observation(rng)
        bot = _player(**overrides)
        bot.prepare(obs)
        warm = rng.random() < 0.5
        if warm:
            _as_in_a_ranking(bot)
        s = ev.SIDE_INDEX[side]
        held = [c for c in t.ids if any(bot.board.influence[c].values())]
        near = sorted({t.ids[j] for c in held for j in ev.dependents(t, {t.index[c]})})
        for _probe in range(12):
            cid = rng.choice(near if near and rng.random() < 0.8 else t.ids)
            own, opp = rng.randint(-3, 4), rng.randint(-3, 4)
            if own == 0 and opp == 0:
                continue
            i = t.index[cid]
            pos = bot._position
            was_own, was_opp = pos.inf[s][i], pos.inf[1 - s][i]
            controller = pos.control[i]
            others = [(j, ev.country_value(t, pos, j, s, bot.weights, bot._urgency))
                      for j in sorted(ev.dependents(t, {i}) - {i})]

            expected = _board_difference(bot, side, cid, own, opp)
            got = bot.delta(obs, cid, own=own, opp=opp)
            assert got == pytest.approx(expected, rel=0, abs=1e-9), (
                cid, own, opp, dict(bot.board.influence[cid]), got, expected)

            # Classify what was just checked.
            us, ussr = _applied(bot, side, cid, own, opp)
            now_own, now_opp = (us, ussr) if side is Side.US else (ussr, us)
            was = pos.place(i, us, ussr)
            seen['control transition'] += pos.control[i] != controller
            seen['neighbour moved'] += any(
                ev.country_value(t, pos, j, s, bot.weights, bot._urgency) != v for j, v in others)
            pos.place(i, *was)
            seen['first foothold'] += was_own == 0 < now_own
            seen['last enemy point'] += was_opp > 0 == now_opp
            seen['redundant route'] += now_own > 0 and any(
                t.battleground[n] and any(m != i and pos.inf[s][m] > 0 for m in t.neighbors[n])
                for n in t.neighbors[i])
            asia = t.region_of[i].name == 'ASIA'
            southeast = 'SOUTHEAST_ASIA' in {r.name for r in bot.board.countries[cid].subregions}
            seen['southeast asia'] += southeast
            seen['other asia'] += asia and not southeast
            seen['warm cache'] += warm
    assert all(n >= 15 for n in seen.values()), seen


@pytest.mark.parametrize('overrides', POTENTIALS)
def test_a_repeated_delta_from_warm_caches_is_still_exact(overrides):
    """The neighbours' before-values are cached per decision on `(index,
    side)`. Asking about many changes on one base -- which is what the
    placement search does -- must not let one answer's caching move the
    next."""
    rng = random.Random(7)
    t = ev.terrain()
    obs, side = _random_observation(rng)
    bot = _player(**overrides)
    bot.prepare(obs)
    _as_in_a_ranking(bot)
    probes = [(c, k) for c in t.ids for k in (1, 2, 3, -1)]
    rng.shuffle(probes)
    for cid, k in probes[:150] * 2:
        expected = _board_difference(bot, side, cid, k, 0)
        assert bot.delta(obs, cid, own=k) == pytest.approx(expected, rel=0, abs=1e-9), (cid, k)


def _cameroon_then_nigeria():
    """Codex's M1 weights: region VP and the margin off, so what is left of
    the gap is access alone."""
    return _player(region=0, margin_presence=0, margin_battleground=0, margin_country=0)


def test_controlling_nigeria_charges_cameroon_the_access_it_consumes():
    """Codex M1, reproduced: US Cameroon 1 on an empty turn-1 board, US +1
    Nigeria. `delta` returned 13.9502222222 against a board difference of
    8.4435555556; the missing -5.5066666667 was Cameroon's access to an
    uncontrolled Nigeria."""
    engine = _empty_engine()
    engine.board.influence['Cameroon']['US'] = 1
    obs = engine.observe(Side.US)
    bot = _cameroon_then_nigeria()
    bot.prepare(obs)
    expected = _board_difference(bot, Side.US, 'Nigeria', 1, 0)
    assert expected == pytest.approx(8.4435555556, abs=1e-9)
    assert bot.delta(obs, 'Nigeria', own=1) == pytest.approx(expected, rel=0, abs=1e-9)


def _placements_in_order(make_bot, placements, side=Side.US):
    """Codex's order probe: re-prepare on the engine before each placement,
    sum the raw deltas, and return that with the whole-board difference
    between the first and last positions."""
    engine = _empty_engine()
    bot = make_bot()
    start = bot.evaluate(engine.observe(side))
    total = 0.
    for cid, points in placements:
        obs = engine.observe(side)
        bot.prepare(obs)
        total += bot.delta(obs, cid, own=points)
        engine.board.influence[cid][side.value] += points
    return total, bot.evaluate(engine.observe(side)) - start


@pytest.mark.parametrize('first, second', [('Cameroon', 'Nigeria'), ('Nigeria', 'Cameroon')])
def test_cameroon_and_nigeria_sum_to_the_same_board_in_either_order(first, second):
    """Codex M1's table: Cameroon then Nigeria summed 29.1486222222, Nigeria
    then Cameroon 23.6419555556, and both final boards value 23.6419555556."""
    total, board = _placements_in_order(_cameroon_then_nigeria, [(first, 1), (second, 1)])
    assert board == pytest.approx(23.6419555556, abs=1e-9)
    assert total == pytest.approx(board, rel=0, abs=1e-9)
