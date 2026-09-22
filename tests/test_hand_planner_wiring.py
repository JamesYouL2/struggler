"""The wiring: policy's per-turn price table, and the plan's lead.

`bots/strategic/hand_planner.py` is tested exactly on designed prices in
`test_hand_planner.py`; this pins what policy FEEDS it (the table is the
same prices the scorer reads, minus the two terms the plan owns) and the
one place the plan reaches the ranking. At `hand_assignment` 0 the plan
is not computed at all and the parity corpus pins the unchanged
ordering; the assertions here are the on path.
"""
from __future__ import annotations

import dataclasses

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import hand_planner as hp
from struggler.engine import Action, Decision, DecisionKind as K, Engine, Side

HAND = ('Asia_Scoring', 'Duck_and_Cover', 'Marshall_Plan', 'Fidel', 'UN_Intervention')


def _bot_obs(cards=HAND, action_round: int = 3, kind=K.ACTION_ROUND_PLAY):
    engine = Engine(seed=0)
    engine.hands[Side.US.value] = list(cards)
    engine.hands[Side.USSR.value] = []
    obs = engine.observe(Side.US)
    options = tuple(Action(kind, {'card': c}) for c in cards)
    obs = dataclasses.replace(
        obs, action_round=action_round,
        pending_decision=Decision(1, Side.US, kind, options))
    bot = StrategicPlayer(StrategicWeights(hand_assignment=1.0))
    bot.prepare(obs)
    return bot, obs


def test_the_table_reads_the_scorers_prices_minus_the_planner_owned_terms():
    bot, obs = _bot_obs()
    table = {c.key: c for c in bot.hand_prices(obs)}
    assert set(table) == set(HAND)
    # The scorer's price and the table's differ by exactly ruling 5's
    # timing nudge on a scoring card (the plan owns the timing)...
    scoring = table['Asia_Scoring']
    assert not scoring.may_hold
    live = bot.play_price(obs, 'Asia_Scoring', K.ACTION_ROUND_PLAY)
    assert live - scoring.play[0] == 2 * obs.action_round
    # ...and by the space pre-assignment on the space pick (the plan owns
    # the slot). Every other card reads the scorer's number unchanged.
    for cid in ('Duck_and_Cover', 'Marshall_Plan', 'Fidel', 'UN_Intervention'):
        card = table[cid]
        assert card.may_hold
        assert card.play[0] == bot.play_price(
            obs, cid, K.ACTION_ROUND_PLAY, scoring_nudge=False, space_slot=False)
    # The UN unit prices the pairing (its partner is `un_card`'s pick,
    # that policy standing) and consumes both cards.
    partner = bot.un_card(obs)
    assert partner is not None
    assert table['UN_Intervention'].un_play == table['UN_Intervention'].play[0]
    assert table[partner].un_partner == 0.0
    assert all(table[c].un_partner is hp.NEG for c in HAND if c != partner)
    # Ruling 5's gain is only for the plan's timing; scoring cards carry none.
    assert 'Asia_Scoring' not in bot._plan_gain(obs)


def test_the_plan_pref_leads_the_ranking_under_the_weight():
    bot, obs = _bot_obs()
    ranked = bot.rank_actions(obs)
    plans = bot.hand_plan(obs)
    assert plans
    want = max(plans, key=lambda wp: wp.probability).assignment.rounds[0][1]
    assert ranked[0][1].payload['card'] == want


def test_the_plan_pref_is_everywhere_zero_with_the_gate_off():
    bot, obs = _bot_obs()
    bot.weights = dataclasses.replace(bot.weights, hand_assignment=0.0)
    ranked = bot.rank_actions(obs)
    assert bot.hand_plan(obs) is None
    assert all(bot._plan_pref(obs, a) == 0 for _, a in ranked)


def test_the_headline_leads_the_headline_ranking():
    bot, obs = _bot_obs(kind=K.HEADLINE_PLAY)
    ranked = bot.rank_actions(obs)
    plans = bot.hand_plan(obs)
    assert plans
    want = max(plans, key=lambda wp: wp.probability).assignment.headline
    assert ranked[0][1].payload['card'] == want
