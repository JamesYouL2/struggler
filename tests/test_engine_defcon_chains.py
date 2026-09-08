"""Regressions for phasing responsibility and the audited event rules."""
import pytest

from conftest import bare_engine, headline_setup
from struggler.engine import Action, DecisionKind as K, Engine, Side


def choose(engine, **payload):
    action = next(a for a in engine.legal_actions() if all(a.payload.get(k) == v for k, v in payload.items()))
    engine.step(action)


@pytest.mark.parametrize('card,phasing,beneficiary', [
    ('CIA_Created', Side.USSR, Side.US),
    ('Lone_Gunman', Side.US, Side.USSR),
    ('Grain_Sales_to_Soviets', Side.USSR, Side.US),
])
def test_opponent_granted_coup_blames_phasing_player_after_roundtrip(card, phasing, beneficiary):
    engine = bare_engine()
    engine.defcon = 2
    engine.board.influence['Mexico'][phasing.value] = 1
    engine._fire_event(phasing, card)
    assert engine.pending_decision.actor is beneficiary
    choose(engine, type='coup')
    choose(engine, country='Mexico')
    restored = Engine.deserialize(engine.serialize())
    assert restored.serialize() == engine.serialize()
    for game in (engine, restored):
        choose(game)
        assert game.winner is beneficiary
        assert game.defcon == 1
    assert restored.serialize() == engine.serialize()


@pytest.mark.parametrize('card', ['Star_Wars', 'Grain_Sales_to_Soviets', 'Five_Year_Plan'])
def test_nested_us_event_preserves_original_ussr_responsibility(card):
    engine = bare_engine()
    engine.defcon = 2
    engine.space_race['US'] = 1
    engine.discard_pile = ['Duck_and_Cover'] if card == 'Star_Wars' else []
    engine.hands['USSR'] = [] if card == 'Star_Wars' else ['Duck_and_Cover']
    engine._fire_event(Side.USSR, card)
    if card == 'Star_Wars':
        choose(engine, choice='Duck_and_Cover')
    elif card == 'Five_Year_Plan':
        choose(engine)
    else:
        choose(engine)  # reveal
        choose(engine, choice='take')
        choose(engine, mode='event')
    assert engine.winner is Side.US
    assert engine.defcon == 1


def test_headline_coup_keeps_headline_owner_as_responsible():
    engine = bare_engine()
    engine.defcon = 3
    engine.board.influence['Cuba']['USSR'] = 3
    headline_setup(engine, 'CIA_Created', 'Duck_and_Cover')
    choose(engine, card='CIA_Created')
    choose(engine, card='Duck_and_Cover')
    assert engine.defcon == 2
    choose(engine, type='coup')
    choose(engine, country='Cuba')
    choose(engine)
    assert engine.winner is Side.US  # responsibility changed for the second headline


def test_summit_opponent_choice_blames_sponsor():
    engine = bare_engine()
    engine.defcon = 2
    # Same continuation produced when the opponent wins the Summit contest.
    with engine._phasing_scope(Side.USSR):
        engine.push_event_choice('Summit_defcon', Side.US, ('raise', 'lower', 'none'))
    choose(engine, choice='lower')
    assert engine.winner is Side.US


def test_five_year_plan_discards_scoring_without_scoring():
    engine = bare_engine()
    engine.hands['USSR'] = ['Asia_Scoring']
    engine.defcon = 2
    engine._fire_event(Side.USSR, 'Five_Year_Plan')
    choose(engine)
    assert engine.discard_pile == ['Asia_Scoring']
    assert engine.vp == 0 and engine.defcon == 2
    assert engine.hands['USSR'] == []


def test_missile_envy_forces_received_reducer():
    engine = bare_engine()
    engine.defcon = 2
    engine.hands['USSR'] = ['Duck_and_Cover']
    engine._fire_event(Side.US, 'Missile_Envy')
    assert engine.winner is Side.USSR
    assert engine.pending_decision is None
    assert engine.hands['USSR'] == ['Missile_Envy']


@pytest.mark.parametrize('vp,winner', [(7, Side.US), (6, None), (5, Side.USSR)])
def test_wargames_skips_regional_scoring(vp, winner):
    engine = bare_engine()
    engine.defcon = 2
    engine.vp = vp
    for cid in engine.board.countries:
        engine.board.influence[cid]['USSR'] = 10
    engine._fire_event(Side.US, 'Wargames')
    choose(engine, choice='end_game')
    assert engine.is_terminal
    assert engine.winner is winner
    assert engine.vp == vp-6
    assert engine.pending_decision is None


def test_cmc_can_be_cancelled_during_opponents_operations_without_consuming_round():
    engine = bare_engine()
    engine.defcon = 3
    engine.turn_effects['cuban_missile_crisis'] = 'USSR'
    engine.board.influence['Cuba']['USSR'] = 2
    engine._fire_event(Side.US, 'ABM_Treaty')
    engine._advance()
    assert engine.pending_decision.actor is Side.USSR
    assert engine.pending_decision.context['resume_pending']
    restored = Engine.deserialize(engine.serialize())
    choose(restored, choice='Cuba')
    assert restored.pending_decision.kind is K.OPS_TYPE
    assert restored.pending_decision.actor is Side.US
    assert restored.pending_decision.context['phasing_player'] == 'US'
    assert restored.board.influence['Cuba']['USSR'] == 0
    assert restored._ars_played == engine._ars_played
    assert 'cuban_missile_crisis' not in restored.turn_effects


def test_cmc_skip_is_once_per_decision_and_targets_refresh_after_payment():
    engine = bare_engine()
    engine.turn_effects['cuban_missile_crisis'] = 'USSR'
    engine.defcon = 3
    engine.board.influence['Cuba']['USSR'] = 2
    engine.board.influence['Mexico']['USSR'] = 1
    engine._push_ops_type(Side.US, 2)
    engine._advance()
    choose(engine, choice='skip')
    assert engine.pending_decision.kind is K.OPS_TYPE
    choose(engine, type='coup')
    assert engine.pending_decision.context['resume_pending']
    choose(engine, choice='Cuba')
    assert engine.pending_decision.kind is K.COUP_TARGET
    assert {a.payload['country'] for a in engine.legal_actions()} == {'Mexico'}


def test_cmc_coup_loses_before_dice_even_on_opponents_turn():
    engine = bare_engine()
    engine.turn_effects['cuban_missile_crisis'] = 'USSR'
    engine.board.influence['Mexico']['US'] = 1
    engine._fire_event(Side.US, 'Lone_Gunman')
    choose(engine, type='coup')
    rng = engine.serialize()['rng_state']
    choose(engine, country='Mexico')
    assert engine.winner is Side.US
    assert engine._game_over_reason == 'cuban_missile_crisis'
    assert engine.serialize()['rng_state'] == rng


def test_five_year_plan_is_a_legal_last_round_scoring_escape():
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine._ars_played = 11  # USSR's sixth action is current
    engine.hands['USSR'] = ['Five_Year_Plan', 'Asia_Scoring']
    engine._push_action_round_play(Side.USSR)
    choose(engine, card='Five_Year_Plan')
    assert {a.payload['mode'] for a in engine.legal_actions()} == {'ops', 'event'}
    choose(engine, mode='ops')
    choose(engine, order='event_first')
    choose(engine)  # discard the only other card
    assert 'Asia_Scoring' in engine.discard_pile
    choose(engine)  # resume the operations half
    assert engine.pending_decision.kind is K.OPS_TYPE
    assert engine.pending_decision.context['ops'] == 3
    assert engine.vp == 0


def test_cmc_skipping_at_round_start_does_not_immediately_reprompt():
    engine = bare_engine()
    engine.hands['USSR'] = ['Nasser']
    engine.board.influence['Cuba']['USSR'] = 2
    engine.turn_effects['cuban_missile_crisis'] = 'USSR'
    engine._push_cmc_defuse_offer(Side.USSR)
    choose(engine, choice='skip')
    assert engine.pending_decision.kind is K.ACTION_ROUND_PLAY


def test_cmc_refresh_preserves_event_coup_geography():
    engine = bare_engine()
    engine.defcon = 2
    engine.turn_effects['cuban_missile_crisis'] = 'US'
    engine.board.influence['Turkey']['US'] = 2
    engine.board.influence['Cuba']['US'] = 1
    engine.board.influence['Mexico']['US'] = 1
    engine._fire_event(Side.USSR, 'Ortega_Elected_in_Nicaragua')
    choose(engine, choice='coup')
    choose(engine, choice='Turkey')
    assert engine.pending_decision.kind is K.COUP_TARGET
    assert {a.payload['country'] for a in engine.legal_actions()} == {'Cuba'}
