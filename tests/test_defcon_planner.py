"""Hand survival, escape resources, and observed nuclear-loss regressions."""
from dataclasses import replace

import pytest

from conftest import bare_engine
from struggler.engine import Side, Action, Decision, DecisionKind as K
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.defcon import DefconPlanner, SurvivalPrior


def setup_hand(cards, side=Side.USSR, rounds=2, defcon=2, space_used=0, china=False):
    e = bare_engine()
    e.turn = 3
    e.phase = 'action_rounds'
    e.action_round = 7-rounds
    e._ars_played = 2*(e.action_round-1)  # keep the director consistent once a decision drains
    e.defcon = defcon
    e.hands[side.value] = list(cards)
    e.china_card_owner = side.value
    e.china_card_available = china
    e.space_race_attempts[side.value] = space_used
    e.board.influence['Cuba'][side.value] = 2
    # Direct card-mode decisions use the engine's real mode enumeration.
    return e


def planner(e, side=Side.USSR, **prior):
    # Exact-structure tests default the opponent hand-attack prior off; the
    # tests that exercise it set it explicitly.
    prior.setdefault('opponent_hand_attack', 0)
    obs = e.observe(side)
    bot = StrategicPlayer()
    return DefconPlanner(obs, bot.public_engine(obs), SurvivalPrior(**prior))


@pytest.mark.parametrize('side,card', [(Side.US,'We_Will_Bury_You'),
                                     (Side.USSR,'Duck_and_Cover'),
                                     (Side.USSR,'Soviets_Shoot_Down_KAL_007')])
def test_direct_reducers_are_spaced_when_possible(side, card):
    e = setup_hand([card], side, rounds=1)
    e.push_full_card_play(side, card)
    before = e.serialize()
    a = StrategicPlayer().choose_action(e.observe(side), [])
    assert a.payload['mode'] == 'space_race'
    assert e.serialize() == before
    e.step(a)
    assert e.defcon == 2 and card not in e.hands[side.value]


@pytest.mark.parametrize('side', [Side.US, Side.USSR])
@pytest.mark.parametrize('phasing_same', [True, False])
def test_hiltsw_never_loses_own_action_and_wins_borrowed_action(side, phasing_same):
    e = bare_engine()
    phasing = side if phasing_same else side.opponent
    with e._phasing_scope(phasing):
        e._fire_event(side, 'How_I_Learned_to_Stop_Worrying')
    a = StrategicPlayer().choose_action(e.observe(side), [])
    e.step(a)
    if phasing_same:
        assert e.defcon == 5 and e.winner is None
    else:
        assert e.defcon == 1 and e.winner is side


def test_space_attempt_is_reserved_for_hazardous_card():
    e = setup_hand(['Duck_and_Cover','CIA_Created','Fidel','Nasser'], rounds=3)
    p = planner(e)
    assert p.risk('Fidel','ops') == 0
    assert p.risk('Fidel','space_race') == 1
    e.push_full_card_play(Side.USSR, 'Fidel')
    assert StrategicPlayer().choose_action(e.observe(Side.USSR), []).payload['mode'] != 'space_race'


def test_china_card_provides_extra_safe_play_but_face_down_does_not():
    e = setup_hand(['CIA_Created','Fidel'], rounds=2, space_used=1)
    assert planner(e).risk() == 1
    e.china_card_available = True
    assert planner(e).risk() == 0
    e.china_card_owner = 'US'
    assert planner(e).risk() == 1


@pytest.mark.parametrize('card', ['How_I_Learned_to_Stop_Worrying','Salt_Negotiations','Nuclear_Test_Ban'])
def test_defcon_raiser_opens_escape_window(card):
    e = setup_hand(['Duck_and_Cover',card], space_used=1)
    p = planner(e, opponent_lowers_defcon=1)
    assert p.risk(card,'event') == 0
    assert p.risk(card,'ops') == 1
    e.push_full_card_play(Side.USSR, card)
    assert StrategicPlayer().choose_action(e.observe(Side.USSR), []).payload['mode'] == 'event'


def test_five_year_plan_discard_probability_and_scoring_escape():
    e = setup_hand(['Five_Year_Plan','Duck_and_Cover','Nasser'], rounds=1)
    p = planner(e)
    assert p.event_risk('Five_Year_Plan') == .5
    assert p.risk('Five_Year_Plan','ops') == .5
    e.hands['USSR'] = ['Five_Year_Plan','Asia_Scoring']
    assert planner(e).risk('Five_Year_Plan','ops') == 0
    e.hands['USSR'] = ['Five_Year_Plan','Duck_and_Cover']
    assert planner(e).risk('Five_Year_Plan','ops') == 1


def test_one_op_cia_is_not_spaceable_without_ops_bonus():
    e = setup_hand(['CIA_Created'], rounds=1)
    assert planner(e).risk() == 1
    e.turn_effects['brezhnev'] = True
    assert planner(e).risk() == 0


def test_no_coup_target_and_nuclear_subs_remove_cia_coup_route():
    e = setup_hand(['CIA_Created'], rounds=1)
    assert planner(e).event_risk('CIA_Created') == 1
    e.board.influence['Cuba']['USSR'] = 0
    assert planner(e).event_risk('CIA_Created') == 0
    e.board.influence['Cuba']['USSR'] = 2
    e.turn_effects['nuclear_subs'] = True
    assert planner(e).event_risk('CIA_Created') == 0


def test_un_intervention_spends_two_cards_without_firing_event():
    e = setup_hand(['Duck_and_Cover','UN_Intervention','CIA_Created'], rounds=2, space_used=1)
    assert planner(e).risk('Duck_and_Cover','un_intervention') == 1  # leaves only CIA for last round
    e.china_card_available = True
    assert planner(e).risk('Duck_and_Cover','un_intervention') == 0


def test_ask_not_discards_hazard_then_stops_and_has_uncertain_replacements():
    card = 'Ask_Not_What_Your_Country_Can_Do_For_You'
    e = setup_hand([card,'Lone_Gunman'], Side.US, rounds=2, space_used=1)
    p = planner(e, Side.US)
    assert 0 < p.risk(card,'event') < p.risk(card,'ops')
    e.hands['US'].remove(card)
    e._fire_event(Side.US, card)
    bot = StrategicPlayer()
    a = bot.choose_action(e.observe(Side.US), [])
    assert a.payload['choice'] == 'Lone_Gunman'
    # No hidden cards are supplied to the planner; only the real engine draws.
    e.hands['US'].append('Fidel')
    e.step(a)
    assert bot.choose_action(e.observe(Side.US), []).payload['choice'] == 'stop'


def test_aldrich_ames_removes_safe_play_to_preserve_us_suicide_card():
    e = setup_hand(['Lone_Gunman','Fidel'], Side.US, rounds=2, space_used=1)
    e._fire_event(Side.USSR, 'Aldrich_Ames_Remix')
    a = StrategicPlayer().choose_action(e.observe(Side.USSR), [])
    assert a.payload['choice'] == 'Fidel'
    e.step(a)
    assert e.hands['US'] == ['Lone_Gunman']


def test_search_budget_and_features_are_explicit():
    e = setup_hand(['Duck_and_Cover','CIA_Created','Fidel'], rounds=3)
    p = planner(e, max_states=1)
    f = p.features()
    assert 0 <= f['turn_loss_risk'] <= 1
    assert f['hazardous_cards'] == 2
    assert f['search_truncated']
    with pytest.raises(ValueError):
        SurvivalPrior(opponent_lowers_defcon=float('nan'))


# -- coups that create targets, and headlines that resolve second -------------


def test_battleground_coup_is_priced_by_the_hand_at_the_lower_defcon():
    # Seed 2402, T2 AR4: USSR couped Zaire from DEFCON 3 holding CIA Created
    # and Five Year Plan with no spare play; its new Zaire influence became
    # the CIA coup target and the turn was lost.
    e = setup_hand(['CIA_Created', 'Five_Year_Plan', 'US_Japan_Mutual_Defense_Pact'], rounds=3,
                   defcon=3, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0  # no DEFCON-2-legal target for the US yet
    e.board.influence['Zaire']['US'] = 2
    e.board.influence['Kenya']['US'] = 1
    e._push(Side.USSR, K.OPS_TYPE, (Action(K.OPS_TYPE, {'type': 'coup'}), Action(K.OPS_TYPE, {'type': 'influence'})),
            {'side': 'USSR', 'ops': 3, 'bonus': None, 'allow_coup': True})
    bot = StrategicPlayer(survival_prior=SurvivalPrior(opponent_hand_attack=0))
    obs = e.observe(Side.USSR)
    bot.choose_action(obs, [])
    assert bot.coup_survival_risk(obs, 'Kenya') == 0
    assert bot.coup_survival_risk(obs, 'Zaire') == pytest.approx(1.0)
    e._decision_stack.pop()
    e._push(Side.USSR, K.COUP_TARGET, tuple(Action(K.COUP_TARGET, {'country': c}) for c in ('Zaire', 'Kenya')),
            {'ops': 3, 'bonus': None})
    assert bot.choose_action(e.observe(Side.USSR), []).payload['country'] == 'Kenya'


def test_headline_pick_prices_the_opponent_headline_resolving_first():
    # Seed 2400, T10: the US headlined Lone Gunman at DEFCON 3; the USSR's
    # higher-Ops headline resolved first and DEFCON was 2 when it fired.
    hand = ['Lone_Gunman', 'Decolonization', 'Socialist_Governments', 'Nasser', 'Fidel',
            'Independent_Reds', 'Korean_War', 'The_Voice_Of_America', 'An_Evil_Empire']
    e = setup_hand(hand, Side.US, rounds=7, defcon=3)
    e.board.influence['Nigeria']['US'] = 2
    e.phase = 'headline'
    e._push_headline(Side.US)
    p = planner(e, Side.US, opponent_lowers_defcon=1)
    assert p.risk('Lone_Gunman', 'event') == 0  # naive: fires at DEFCON 3
    assert p.headline_pick_risk('Lone_Gunman') > 0.8  # a 1-Ops card almost always resolves second
    assert p.headline_pick_risk('Socialist_Governments') == 0
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['card'] != 'Lone_Gunman'


def test_pending_own_headline_is_a_forced_event_before_the_action_rounds():
    e = setup_hand(['Decolonization', 'Socialist_Governments'], Side.US, rounds=7, defcon=3)
    e.board.influence['Nigeria']['US'] = 2
    e.phase = 'headline'
    e._headline_pending = [['US', 'Lone_Gunman']]
    obs = e.observe(Side.US)
    assert obs.headline_pending == (('US', 'Lone_Gunman'),)
    p = planner(e, Side.US)
    assert p.pending_headline == 'Lone_Gunman' and p.rounds == 6  # turn 3: six rounds, no headline card to count
    assert p.risk() == 0
    e.defcon = 2
    assert planner(e, Side.US).risk() == 1
    # Couping a battleground to DEFCON 2 with that headline still to come is fatal.
    e.defcon = 3
    e.board.influence['Zaire']['USSR'] = 2
    e._push(Side.US, K.COUP_TARGET, (Action(K.COUP_TARGET, {'country': 'Zaire'}),), {'ops': 2, 'bonus': None})
    bot = StrategicPlayer()
    bot.choose_action(e.observe(Side.US), [])
    assert bot.coup_survival_risk(e.observe(Side.US), 'Zaire') == 1


# -- discard events, traps, and opponent hand attacks -------------------------


def test_blockade_self_discard_is_refused_when_it_strands_a_suicide_card():
    # Seed 2401, T9 AR5 (logs/game-check/2401-strategic-strategic.debug.log):
    # the US paid Socialist Governments to Blockade and was left holding
    # Lone Gunman for the last round.
    hand = ['Allende', 'Blockade', 'Lone_Gunman', 'Socialist_Governments']
    e = setup_hand(hand, Side.US, rounds=3, space_used=1)
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.risk() == 0 and p.risk('Blockade', 'ops') == 0
    e.hands['US'].remove('Blockade')
    e._fire_event(Side.US, 'Blockade')
    decision = e.observe(Side.US).pending_decision
    assert decision.kind is K.EVENT_CHOICE and decision.context['event'] == 'Blockade'
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.mid_play and p.rounds == 2
    assert p.discard_risk('Socialist_Governments') == 1
    assert p.discard_risk(None) == 0
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['choice'] == 'refuse'


def test_blockade_discard_is_an_exit_for_a_three_ops_hazard():
    e = setup_hand(['We_Will_Bury_You', 'Blockade', 'Fidel'], Side.US, rounds=2, space_used=1)
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.risk('We_Will_Bury_You', 'ops') == 1
    assert p.risk('Blockade', 'ops') == 0
    assert p.risk('Fidel', 'ops') == 0  # Blockade can still pay WWBY away next round
    e.hands['US'].remove('Blockade')
    e._fire_event(Side.US, 'Blockade')
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['choice'] == 'We_Will_Bury_You'


def test_self_bear_trap_disposes_of_us_events_without_firing_them():
    hand = ['Bear_Trap', 'Grain_Sales_to_Soviets', 'CIA_Created', 'The_Voice_Of_America']
    e = setup_hand(hand, rounds=3, space_used=1)
    p = planner(e, opponent_hand_attack=0)
    assert p.risk('Grain_Sales_to_Soviets', 'ops') == 1
    assert p.risk('CIA_Created', 'ops') == 1
    assert p.risk('Bear_Trap', 'ops') == 0
    e.game_effects['bear_trap'] = True
    p = planner(e, opponent_hand_attack=0)
    assert p.trapped and p.risk() == 0
    assert p.features()['trapped'] == 1


def test_trap_step_pays_the_card_that_keeps_the_hand_safest():
    # Trapped USSR must pay a 2+ Ops card: paying Voice of America keeps a
    # safe 2-Ops card (Fidel) for the round after an escape; paying Fidel
    # leaves Grain Sales as the only later play if the die frees us.
    e = setup_hand(['Fidel', 'Grain_Sales_to_Soviets', 'CIA_Created'], rounds=2, space_used=1)
    e.game_effects['bear_trap'] = True
    e._push_trap_step(Side.USSR, 'bear_trap')
    p = planner(e, opponent_hand_attack=0)
    assert p.mid_play and p.rounds == 1
    assert p.discard_risk('Grain_Sales_to_Soviets', escape_roll=True) == 0
    assert p.discard_risk('Fidel', escape_roll=True) == pytest.approx(4/6)
    a = StrategicPlayer().choose_action(e.observe(Side.USSR), [])
    assert a.payload['card'] == 'Grain_Sales_to_Soviets'


def test_opponent_hand_attack_prior_prices_a_missing_spare_card():
    e = setup_hand(['CIA_Created', 'Fidel', 'Nasser'], rounds=2, space_used=1)
    assert planner(e, opponent_hand_attack=0).risk() == 0
    assert planner(e, opponent_hand_attack=.5).risk() == pytest.approx(.5)
    assert planner(e, opponent_hand_attack=1).risk() == 1
    # One spare safe card absorbs the single attack between two rounds...
    e.hands['USSR'].append('Decolonization')
    assert planner(e, opponent_hand_attack=1).risk() == 0
    # ...but three rounds leave room for two attacks: three plays plus two
    # stolen cards need five safe cards alongside the held hazard.
    e.action_round = 7-3
    assert planner(e, opponent_hand_attack=1).risk() == 1
    e.hands['USSR'].append('Warsaw_Pact_Formed')
    assert planner(e, opponent_hand_attack=1).risk() == 1
    e.hands['USSR'].append('Arab_Israeli_War')
    assert planner(e, opponent_hand_attack=1).risk() == 0


def test_five_year_plan_and_missile_envy_chains_only_matter_at_defcon_2():
    from struggler.engine import Side
    for defcon, expected in ((5, 0.), (2, SurvivalPrior().unknown_chain_loss)):
        e = bare_engine()
        e.phase = 'action_rounds'
        e.defcon = defcon
        e.hands['US'] = ['Five_Year_Plan', 'Missile_Envy']
        e.hands['USSR'] = ['Nasser']
        e._push_action_round_play(Side.US)
        planner = DefconPlanner(e.observe(Side.US), e, SurvivalPrior(opponent_hand_attack=0))
        assert planner.event_risk('Five_Year_Plan') == expected
        assert planner.event_risk('Missile_Envy') == expected
