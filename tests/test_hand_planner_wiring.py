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
from struggler.bots.strategic.policy import is_certain
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


def _shipped_order(obs):
    off = StrategicPlayer(StrategicWeights())
    off.prepare(obs)
    return [a.payload['card'] for _, a in off.rank_actions(obs)]


def test_the_lead_is_the_shipped_ranking_stably_partitioned():
    """The plan never ORDERS cards: an ordinary card's price is the same in
    every round, so `rounds` is `solve_hand`'s by-key tie-break. Leading
    with `rounds[0]` played the hand alphabetically (run 35814771005,
    -0.240). The ranking under the weight must be the shipped ranking with
    the demoted cards moved to the back, each group in the scorer's order."""
    bot, obs = _bot_obs()
    ranked = [a.payload['card'] for _, a in bot.rank_actions(obs)]
    mode, demoted = bot._plan_lead(obs)
    assert mode == 'demote'
    shipped = _shipped_order(obs)
    assert ranked == ([c for c in shipped if c not in demoted]
                      + [c for c in shipped if c in demoted])


def test_a_tie_between_playing_and_holding_is_not_a_preference():
    """At `hold_option` 0 a card's hold price IS its play price
    (`hold_value` reads the same `card_play_value`), so which cards the
    solver holds is a tie-break too -- reading `holds` directly held the
    alphabetically LAST card (NORAD over Duck and Cover, seed 4000). With
    every ordinary card tied, nothing may be demoted and the ranking must be
    exactly the shipped one."""
    bot, obs = _bot_obs(cards=('Duck_and_Cover', 'Marshall_Plan', 'Fidel', 'NORAD',
                               'Containment', 'COMECON', 'Truman_Doctrine'),
                        action_round=4)
    table = bot.hand_prices(obs)
    assert all(c.play[0] == c.hold for c in table if c.may_hold), 'the premise: play == hold'
    plan = max(bot.hand_plan(obs), key=lambda wp: wp.probability).assignment
    assert plan.holds, 'the solver does hold something -- by tie-break'
    assert bot._plan_lead(obs) == ('demote', frozenset())
    assert [a.payload['card'] for _, a in bot.rank_actions(obs)] == _shipped_order(obs)


def test_a_strictly_better_hold_is_demoted(monkeypatch):
    """Where the plan does have a preference, it acts: a card whose hold
    price strictly beats its play is demoted, whatever its name."""
    bot, obs = _bot_obs(cards=('Duck_and_Cover', 'Marshall_Plan', 'Fidel', 'NORAD',
                               'Containment', 'COMECON', 'Truman_Doctrine'),
                        action_round=4)
    real = bot.hand_prices(obs)
    keep = 'Containment'
    table = tuple(dataclasses.replace(c, hold=c.play[0] + 100.0) if c.key == keep else c
                  for c in real)
    monkeypatch.setattr(bot, 'hand_prices', lambda _obs: table)
    bot._hand_plan = bot._plan_lead_cache = None
    assert bot._plan_lead(obs) == ('demote', frozenset({keep}))
    assert bot._plan_pref(obs, Action(K.ACTION_ROUND_PLAY, {'card': keep})) == 0
    assert bot._plan_pref(obs, Action(K.ACTION_ROUND_PLAY, {'card': 'NORAD'})) == 1


def test_renaming_the_cards_cannot_move_what_the_plan_spends():
    """What the lead now reads -- the set the plan spends and the set it
    holds -- must be a property of the PRICES, not of the names. Relabel
    every card so the alphabetical order reverses: the sets must follow.
    (The ORDER in `rounds` does not survive this, which is why the lead no
    longer reads it; the partition test above is the one that failed on
    `rounds[0]`.)"""
    prices = {'A_weak': 0.5, 'B_ok': 2.0, 'M_mid': 3.0, 'Z_best': 9.0, 'Q_keep': 1.0}
    holds = {'Q_keep': 50.0}

    def table(names):
        return tuple(hp.Card(key=names[k], headline=0.0, play=(v,) * 3,
                             hold=holds.get(k, 0.0)) for k, v in prices.items())

    same = {k: k for k in prices}
    renamed = dict(zip(sorted(prices), sorted(prices, reverse=True), strict=True))
    for names in (same, renamed):
        plan = hp.solve_hand(table(names), 3, headline_slots=0)
        spent = {unit[1] for unit in plan.rounds}
        assert spent == {names['Z_best'], names['M_mid'], names['B_ok']}
        assert set(plan.holds) == {names['A_weak'], names['Q_keep']}


def test_the_china_card_is_never_demoted_by_a_plan_that_cannot_see_it():
    """`hand_prices` reads `obs.hand`, which does not carry the China
    Card, so the plan has no opinion on it. It must rank with the cards the
    plan spends -- the old lead vetoed every China play the scorer wanted
    (seed 4001, turn 1, AR2 through AR6)."""
    bot, obs = _bot_obs()
    china = Action(K.ACTION_ROUND_PLAY, {'card': 'The_China_Card'})
    assert bot._plan_pref(obs, china) == 1


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
    mode, lead = bot._plan_lead(obs)
    assert mode == 'lead' and want in lead
    assert ranked[0][1].payload['card'] in lead


def test_certain_outcomes_are_bounded_before_they_reach_the_solver():
    # A position where a card's price is a certain-outcome FLAG: the
    # USSR holding Duck and Cover at DEFCON 2, where the Ops play fires
    # the US event and drops DEFCON to 1. The scorer is allowed to say
    # that with a flag; the table must hand the solver PRICES, because
    # the solver is pure arithmetic and the sentinel refuses to be added
    # (`_refuse`) -- which is exactly how the played-game smoke found
    # this. The plan then avoids the card if the hand allows.
    engine = Engine(seed=0)
    engine.defcon = 2
    engine.hands[Side.US.value] = []
    engine.hands[Side.USSR.value] = ['Duck_and_Cover', 'Fidel']
    obs = engine.observe(Side.USSR)
    cards = tuple(obs.hand)
    options = tuple(Action(K.ACTION_ROUND_PLAY, {'card': c}) for c in cards)
    obs = dataclasses.replace(
        obs, action_round=6,
        pending_decision=Decision(1, Side.USSR, K.ACTION_ROUND_PLAY, options))
    bot = StrategicPlayer(StrategicWeights(hand_assignment=1.0))
    bot.prepare(obs)
    table = {c.key: c for c in bot.hand_prices(obs)}
    gv = bot.game_value(obs)
    for card in table.values():
        for price in (card.headline, card.space, card.hold, *card.play):
            if price is hp.NEG:
                continue  # the eligibility marker: checked, never summed
            assert not is_certain(price), f'{card.key} carried a flag into the table'
            assert abs(price) <= abs(gv) * (1 + 1e-9)
    plans = bot.hand_plan(obs)
    assert plans
    plan = max(plans, key=lambda wp: wp.probability).assignment
    # The best disposal is the space slot: the attempt removes the event
    # risk entirely and advances our marker -- ruling 4's policy pick is
    # exactly this card. Better than holding it, and far better than the
    # certain-defeat Ops play the flag was talking about.
    assert plan.rounds == (('space', 'Duck_and_Cover'),)
    assert plan.holds == ('Fidel',)
