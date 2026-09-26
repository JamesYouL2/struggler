"""Event branches priced by board value (maintainer, 2026-09-25/26).

The unpriced EVENT_CHOICEs -- the ones the live remeasurement found the
bot picking blind, ~3 a game -- were South African Unrest, Warsaw Pact and
Chernobyl. The maintainer's answers (docs/EXPERT_ASKS.md, item 5):

- Warsaw Pact: add, unless removing swings control of East Germany or
  Poland and adding cannot. Otherwise board value before and after.
- South African Unrest: generally Angola (the adjacent branch); board
  value before and after.
- Chernobyl: the region with the highest swing per Op.

The first two are priced by playing the branch out in the public sandbox
(`_board_choice_value`) -- the rule is a CONSEQUENCE of board value, which
is what these tests check, not a special case the code carries.
"""
from __future__ import annotations

import pytest

from conftest import bare_engine
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Side


def _ranked(engine, event, side):
    engine._fire_event(side, event)
    d = engine.pending_decision
    bot = StrategicPlayer()
    ranked = bot.rank_actions(engine.observe(d.actor))
    return [a.payload['choice'] for _, a in ranked], bot


@pytest.mark.parametrize('setup, expected', [
    ({'East_Germany': (4, 0)}, 'remove'),              # only removing breaks the hold
    ({'East_Germany': (4, 0), 'Poland': (3, 0)}, 'remove'),
    ({'East_Germany': (1, 3)}, 'add'),                 # adding flips it anyway
    ({'Poland': (1, 4), 'Czechoslovakia': (1, 0)}, 'add'),
    ({}, 'add'),                                       # nothing of the US's to remove
])
def test_warsaw_pact_adds_unless_only_removal_takes_east_germany_or_poland(setup, expected):
    engine = bare_engine()
    for country, (us, ussr) in setup.items():
        engine.board.influence[country]['US'] = us
        engine.board.influence[country]['USSR'] = ussr
    order, _ = _ranked(engine, 'Warsaw_Pact_Formed', Side.USSR)
    assert order[0] == expected


def test_south_african_unrest_takes_the_adjacent_branch_on_an_open_board():
    order, _ = _ranked(bare_engine(), 'South_African_Unrest', Side.USSR)
    assert order[0] == 'and_adjacent'


def test_board_only_branches_are_priced_not_blind():
    """Each option carries an opinion now -- none falls to `score`'s
    `None`, which is what made them blind picks."""
    for event in ('Warsaw_Pact_Formed', 'South_African_Unrest', 'Chernobyl'):
        engine = bare_engine()
        engine._fire_event(Side.USSR if event != 'Chernobyl' else Side.US, event)
        d = engine.pending_decision
        bot = StrategicPlayer()
        bot.choose_action(engine.observe(d.actor), [])
        ranked, no_opinion = bot.last_ranking
        assert not no_opinion, f'{event} still has unpriced options'


def test_chernobyl_blocks_the_region_with_the_highest_swing_per_op():
    engine = bare_engine()
    engine._fire_event(Side.US, 'Chernobyl')
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    ranked = bot.rank_actions(obs)
    per_op = {r: bot._chernobyl_denial(obs, r) for r in
              ('EUROPE', 'ASIA', 'MIDDLE_EAST', 'AFRICA', 'CENTRAL_AMERICA', 'SOUTH_AMERICA')}
    assert ranked[0][1].payload['choice'] == max(per_op, key=per_op.get)
    # A region the USSR cannot reach costs it nothing to lose.
    assert min(per_op.values()) == 0.0


def test_a_choice_the_sandbox_cannot_reproduce_keeps_no_opinion():
    """Priced only when re-firing the event reproduces THIS decision: a
    mid-event state (options that differ from a fresh firing) is not the
    first step of the event and stays unpriced."""
    import dataclasses
    from struggler.engine import Action, Decision, DecisionKind as K
    engine = bare_engine()
    engine._fire_event(Side.USSR, 'Warsaw_Pact_Formed')
    obs = engine.observe(Side.USSR)
    only = (Action(K.EVENT_CHOICE, {'choice': 'add'}),)
    d = obs.pending_decision
    obs = dataclasses.replace(obs, pending_decision=Decision(d.id, d.actor, d.kind, only, d.context))
    bot = StrategicPlayer()
    bot.prepare(obs)
    bot.rank_actions(obs)
    assert bot._board_choice_value(obs, only[0], 'Warsaw_Pact_Formed', d.context) is None
