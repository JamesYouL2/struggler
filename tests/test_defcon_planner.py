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
