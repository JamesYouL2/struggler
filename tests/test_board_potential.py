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
- **M2**: `delta` multiplied the regional VP change by the changed
  country's scoring urgency, while `value` and the event sandbox applied
  none. A Southeast Asian country's urgency includes Southeast Asia
  Scoring, so the same Asia tier change was worth more from Thailand than
  from Pakistan. Variant b: the regional VP is weighted by its own region's
  scoring urgency (`evaluator.region_urgency`) on every path.
"""
from __future__ import annotations

import dataclasses
import random

import pytest

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import evaluator as ev
from struggler.engine import Action, Decision, DecisionKind as K, Engine, Region, Side

# Weight overrides the exactness properties are asserted under.
POTENTIALS = (
    pytest.param({}, id='shipped-weights'),
    pytest.param({'access': 0.}, id='no-access'),
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
    bot._base_regions, bot._base_country = {}, {}
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
    # With access off no neighbour's value can move, so that one count is
    # only required where the weights give it something to count.
    required = {k: n for k, n in seen.items() if k != 'neighbour moved' or bot.weights.access}
    assert all(n >= 15 for n in required.values()), seen


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
    """Codex's M1 weights: region VP off, so what is left of the gap is
    access alone. (The margin terms this also switched off were deleted on
    2026-09-19; there is nothing left to switch.)"""
    return _player(region=0)


def test_controlling_nigeria_charges_cameroon_the_access_it_consumes():
    """Codex M1, reproduced: US Cameroon 1 on an empty turn-1 board, US +1
    Nigeria. At M1's dating `delta` returned 13.9502222222 against a board
    difference of 8.4435555556; the missing -5.5066666667 was Cameroon's
    access to an uncontrolled Nigeria. Re-pinned twice: under the retention
    urgency at 4.132012930555556, and under the factor-2 masses at
    14.05555555555555 (5cf67af), and under the fitted country weights at
    15.546451969888892 (2026-09-18, while they were the default). Re-pinned
    again 2026-09-21 to 14.957940227388889, when the fitted weights became
    the only weights: not the same number as 2026-09-18 because `access`
    was still calling `importance` without a side then, so the reach half
    of this very gap was priced on the tiers while the rest was on fitted
    VP. The property -- delta equals the board difference exactly -- is
    what carries, not the number."""
    engine = _empty_engine()
    engine.board.influence['Cameroon']['US'] = 1
    obs = engine.observe(Side.US)
    bot = _cameroon_then_nigeria()
    bot.prepare(obs)
    expected = _board_difference(bot, Side.US, 'Nigeria', 1, 0)
    assert expected == pytest.approx(14.957940227388889, abs=1e-9)
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
    """Codex M1's table, re-pinned to the factor-2 masses: both orders sum
    to the board exactly at 39.355555555555554 (at M1's dating Cameroon
    then Nigeria summed 29.1486222222, Nigeria then Cameroon 23.6419555556,
    both final boards 23.6419555556; under the retention urgency
    11.569636205555554; under the fitted country weights, 37.69155245288889,
    2026-09-18; and 38.20352451788889 from 2026-09-21, when those weights
    became the only weights and `access` had been put on the same scale as
    the rest of the country layer). The order-invariance is the property;
    the level follows the urgency and the country weights."""
    total, board = _placements_in_order(_cameroon_then_nigeria, [(first, 1), (second, 1)])
    assert board == pytest.approx(38.20352451788889, abs=1e-9)
    assert total == pytest.approx(board, rel=0, abs=1e-9)


def _no_access():
    """Codex's M2 weights: access off, so what is left of any gap is the
    regional term."""
    return _player(access=0)


@pytest.mark.parametrize('make_bot', [_no_access, _player], ids=['no-access', 'shipped-weights'])
@pytest.mark.parametrize('placements', [
    (('Thailand', 2), ('Pakistan', 2)), (('Pakistan', 2), ('Thailand', 2)),
    (('Cameroon', 1), ('Nigeria', 1)), (('Nigeria', 1), ('Cameroon', 1)),
], ids=['thailand-pakistan', 'pakistan-thailand', 'cameroon-nigeria', 'nigeria-cameroon'])
def test_placements_sum_to_the_same_board_in_either_order(make_bot, placements):
    """Codex M2: US +2 Thailand and +2 Pakistan, reply and access off,
    summed 118.5570666667 in one order and 116.5602666667 in the other, to
    a board worth 109.2502222222 either way. Each order must sum to the
    board, so both orders sum the same; under the shipped weights too, where
    M1's access spillover is also in play."""
    total, board = _placements_in_order(make_bot, list(placements))
    assert total == pytest.approx(board, rel=0, abs=1e-9)


@pytest.mark.parametrize('make_bot', [_no_access, _player], ids=['no-access', 'shipped-weights'])
def test_fidel_is_worth_the_placement_that_makes_the_same_change(make_bot):
    """Codex M2: on an empty board Fidel is exactly USSR +3 Cuba -- no VP,
    no Military Ops -- yet the event sandbox and `delta` priced it
    differently (21.22 against 22.26 here with access off, the whole gap the
    regional urgency only `delta` applied). Events and Ops price one
    potential."""
    engine = _empty_engine()
    options = (Action(K.HEADLINE_PLAY, {'card': 'Fidel'}),)
    obs = dataclasses.replace(engine.observe(Side.USSR),
                              pending_decision=Decision(1, Side.USSR, K.HEADLINE_PLAY, options))
    bot = make_bot()
    bot.rank_actions(obs)
    event = bot._public_event_value(obs, 'Fidel')
    assert bot.delta(obs, 'Cuba', own=3) == pytest.approx(event, rel=0, abs=1e-9)


def test_the_regional_term_is_weighted_by_its_own_regions_urgency():
    """Variant b, re-pinned to the factor-2 masses. US +2 Iran on an
    empty turn-1 board, access off: `delta` and the board both read
    19.57277167772727 under the fitted country weights as shipped from
    2026-09-21 (21.289943394898987 under those weights on 2026-09-18,
    before `access` was threaded a side; 22.494949494949488 under the
    deleted tiers; under the retention urgency 41.10647617222223; at
    variant-b dating 52.9822222222). Iran is not in Southeast Asia, so
    its urgency is the Middle East's, and the board weights the Middle
    East's VP by it too -- that equality is the property, at any level.

    And the case that made the old weighting incoherent: at turn 1 Thailand's
    urgency counts Southeast Asia Scoring and Pakistan's does not, yet
    Asia's tiers are weighted by neither alone -- by Asia's own."""
    engine = _empty_engine()
    obs = engine.observe(Side.US)
    bot = _no_access()
    bot.prepare(obs)
    expected = _board_difference(bot, Side.US, 'Iran', 2, 0)
    # Re-pinned 2026-09-19 from 22.494949494949488 when the region-margin
    # terms were deleted: the same board difference with one fewer summand.
    assert expected == pytest.approx(19.57277167772727, abs=1e-9)
    assert bot.delta(obs, 'Iran', own=2) == pytest.approx(expected, rel=0, abs=1e-9)

    t, urgency = ev.terrain(), bot._urgency
    thailand, pakistan = urgency[t.index['Thailand']], urgency[t.index['Pakistan']]
    assert thailand > pakistan, 'the fixture needs Southeast Asia Scoring live'
    assert ev.region_urgency(t, Region.ASIA, urgency) == pakistan
    for region in Region:
        anchor = t.ids[t.region_anchor[region]]
        assert t.region_of[t.region_anchor[region]] is region
        assert not any(s.name == 'SOUTHEAST_ASIA' for s in bot.board.countries[anchor].subregions)


# -- the diagnostic wrapper's own contract -----------------------------------
#
# `scoring_potential` is the potential-delta rewrite's oracle and nothing
# else calls it, which is how all three of these survived: a component DP
# test exercises the terms, never the wiring above them.


def _prepared(side=Side.US, **overrides):
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(side)
    if overrides:
        obs = dataclasses.replace(obs, **overrides)
    bot = _player()
    bot.prepare(obs)
    return bot, obs


@pytest.mark.parametrize('flags', [
    pytest.param({'formosan_resolution': True}, id='formosan'),
    pytest.param({'shuttle_diplomacy': True}, id='shuttle'),
    pytest.param({'formosan_resolution': True, 'shuttle_diplomacy': True}, id='both'),
])
def test_scoring_potential_answers_under_the_scoring_modifiers(flags):
    """It passed `_overrides_map(pos)` -- a dict of six index-set pairs --
    to the parameter that unpacks the two scoring flags, so any position
    with Formosan Resolution or Shuttle Diplomacy in force raised
    `ValueError: too many values to unpack (expected 2)`."""
    def probe(effects):
        bot, _ = _prepared(game_effects=effects)
        # The modifiers have to have something to bite on, or this pins
        # nothing: Formosan promotes a US-Controlled Taiwan to a
        # Battleground, Shuttle drops one USSR-Controlled Battleground from
        # the nearer of the Middle East and Asia.
        bot.board.influence['Taiwan'].update(US=4, USSR=0)
        bot.board.influence['Iran'].update(US=0, USSR=4)
        bot.board.influence['Iraq'].update(US=0, USSR=4)
        return bot.scoring_potential(bot.board, Side.US)

    under = probe(flags)
    assert isinstance(under, float)
    assert under != probe({})


def test_scoring_potential_answers_the_seat_it_is_asked_about():
    """It took `side` and ignored it, reading the prepared observation's
    seat instead, so a bot prepared for the US returned the same number for
    both. The potential is zero-sum between the seats, like `value`."""
    for prepared_for in (Side.US, Side.USSR):
        bot, _ = _prepared(prepared_for)
        us = bot.scoring_potential(bot.board, Side.US)
        ussr = bot.scoring_potential(bot.board, Side.USSR)
        assert us != 0.0
        assert us == -ussr


def test_the_potential_is_its_six_regions_plus_the_southeast_asia_card():
    """`_potential_total` walked `_region_cards`, which maps each Region to
    its own scoring card and so holds exactly the six regional ones. Its
    `card == SEA_SCORING` arm was unreachable and the SEA term was simply
    absent from the sum."""
    # Turn 5 with the card in hand and US influence in South East Asia, so
    # the term is substantial rather than a rounding difference.
    bot, _ = _prepared(turn=5, hand=('Southeast_Asia_Scoring',))
    bot.board.influence['Thailand'].update(US=4, USSR=0)
    pos = bot._position_for(bot.board)
    regions = sum(bot._region_term(region, pos) for region in bot._region_cards)
    sea = bot._sea_term(pos)
    assert sea != 0.0, 'the fixture needs a live Southeast Asia card'
    assert bot._potential_total(pos) == pytest.approx(regions + sea, rel=0, abs=1e-12)
    assert bot._potential_total(pos) != pytest.approx(regions, rel=0, abs=1e-9)
