"""A value must be a property of the position, not of the traversal.

The commonest defect in this repo, six times over, is a cached value keyed
on less state than it reads: two evaluator memos that ignored neighbouring
influence, an event basis surviving across decisions, a rollout cache that
did not sync the board, MCTS leaves inheriting the previous ranking's
context, valuing only the countries an event touched, and a
`coup -> vp_value -> ops_value -> coup` cycle that made one Op worth 28.43
or 27.78 depending purely on which arm of a ranking asked first.

Every one of them is the same assertion, which is what this module is:
**ask the same prepared position for the same numbers in a different
order, and get the same answers.** The parity corpus pins values against a
recorded baseline; this pins them against each other, which is the part
that catches a stale cache the moment it is introduced rather than at the
next corpus regeneration.

The probe runs with **cold caches** and establishes no context first, so
it asserts the strong property: the numbers are a function of the
position and nothing else. That only became assertable once the
`coup -> vp_value -> ops_value -> coup` cycle was broken; before that one
Op was worth 24.02 or 26.03 at seed 4000 T3 AR6 US by traversal alone.

See `docs/CLAUDE_NOTES.md`, "The bugs this repo actually gets".
"""
from __future__ import annotations

import gzip
import json
import pathlib
import random

import pytest

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.engine import Engine, Region, Side

CORPUS = pathlib.Path(__file__).parent / 'corpus' / 'positions.json.gz'
# Every 11th position: enough spread over turns, seats and decision kinds to
# exercise the caches, cheap enough to run on every commit.
STRIDE = 11


@pytest.fixture(scope='module')
def positions():
    records = json.loads(gzip.open(CORPUS).read())['records']
    return records[::STRIDE]


def _probe_plan(record, board_countries):
    """The quantities to ask for, as (kind, argument) pairs.

    Deliberately mixes the layers that call each other -- Ops pricing, the
    VP price, event values, per-country and per-region terms -- because the
    cycles that caused these bugs ran between layers, not inside one.
    """
    hand = [c for c in record['engine']['hands'][record['side']] if c != 'The_China_Card']
    plan = [('vp', None), ('ops', 1), ('ops', 2), ('ops', 3), ('ops', 4)]
    plan += [('event', c) for c in hand[:4]]
    plan += [('country', c) for c in list(board_countries)[:6]]
    plan += [('region', r.name) for r in list(Region)[:4]]
    return plan


def _ask(bot, obs, key):
    kind, arg = key
    if kind == 'vp':
        return bot.vp_value(obs)
    if kind == 'ops':
        return bot.ops_value(obs, arg)
    if kind == 'event':
        return bot.event_value(obs, arg)
    if kind == 'country':
        return bot.country_value(bot.board, arg, obs.side)
    if kind == 'region':
        return bot.region_score(bot.board, Region[arg], obs.side)
    raise AssertionError(kind)


# The per-decision caches `rank_actions` establishes. Cleared before each
# probe so the questions are asked *cold*, which is the only condition under
# which a cycle between two cached quantities can resolve differently: once
# `rank_actions` has warmed them, whichever arm asked first has already won
# and every later order agrees with it. A first version of this test skipped
# the reset and passed happily with a known order-dependence reintroduced.
PER_DECISION_CACHES = ('_ops_values', '_vp_price', '_events', '_event_basis',
                       '_placement_values', '_base_regions', '_base_margins')


def _clear_caches(bot, obs):
    for name in PER_DECISION_CACHES:
        assert hasattr(bot, name), (
            f'{name} is gone; this test pins cache behaviour and must be '
            f'updated deliberately, not left silently weaker')
        current = getattr(bot, name)
        setattr(bot, name, {} if isinstance(current, dict) else None)
    # Nothing is re-established: the probe runs genuinely cold. It could
    # not, until the `coup -> vp_value -> ops_value -> coup` cycle was
    # broken by pricing a VP off the placement spend; before that, one Op
    # came out 24.02 or 26.03 at seed 4000 T3 AR6 US by traversal alone.


def _values(record, order):
    """A freshly prepared bot with cold caches, asked for `order` in
    exactly that sequence."""
    engine = Engine.deserialize(record['engine'])
    side = Side(record['side'])
    obs = engine.observe(side)
    bot = StrategicPlayer(StrategicWeights(**record['weights']),
                          survival_prior=SurvivalPrior(**record['prior']))
    bot.rank_actions(obs)
    _clear_caches(bot, obs)
    return {key: _ask(bot, obs, key) for key in order}


def test_values_do_not_depend_on_the_order_they_are_asked_for(positions):
    rng = random.Random(20260910)
    checked = 0
    for record in positions:
        engine = Engine.deserialize(record['engine'])
        plan = _probe_plan(record, engine.board.countries)
        forward = _values(record, plan)

        for label, order in (('reversed', list(reversed(plan))),
                             ('shuffled', rng.sample(plan, len(plan)))):
            other = _values(record, order)
            for key in plan:
                assert forward[key] == other[key], (
                    f'seed {record["seed"]} T{record["turn"]} '
                    f'AR{record["action_round"]} {record["side"]} {record["kind"]}: '
                    f'{key} is {forward[key]!r} asked first and {other[key]!r} '
                    f'asked {label} -- a cache is keyed on less state than it reads')
        checked += 1
    assert checked >= 20, f'only {checked} positions exercised'


def test_a_repeated_question_gives_a_repeated_answer(positions):
    """The degenerate case, kept separate so a failure says which it is:
    asking twice in a row must not move the answer either."""
    for record in positions[:12]:
        engine = Engine.deserialize(record['engine'])
        side = Side(record['side'])
        obs = engine.observe(side)
        bot = StrategicPlayer(StrategicWeights(**record['weights']),
                              survival_prior=SurvivalPrior(**record['prior']))
        bot.rank_actions(obs)
        for key in _probe_plan(record, engine.board.countries):
            first = _ask(bot, obs, key)
            assert _ask(bot, obs, key) == first, f'{key} moved when asked twice'
