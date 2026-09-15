"""The reply look-ahead may only charge an answer the rules allow."""
from __future__ import annotations

import dataclasses

import pytest

from conftest import bare_engine
from struggler.bots import rules_math
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import DecisionKind as K, Engine, Side


def _priced(engine, side, cid, points, budget):
    obs = engine.observe(side)
    weights = dataclasses.replace(StrategicWeights(), reply_model=1., reply_ops=float(budget))
    bot = StrategicPlayer(weights)
    bot.prepare(obs)
    raw = bot.delta(obs, cid, own=points)
    before = bot.board.serialize()
    after = bot._after_reply(obs, cid, points, raw)
    assert bot.board.serialize() == before
    return raw, after


def _zaire(engine):
    # At DEFCON 2, a Battleground Coup would be nuclear war, so placement is
    # the only answer the rules leave in Zaire.
    engine.defcon = 2
    return engine


def test_no_reply_where_the_opponent_cannot_place():
    engine = _zaire(bare_engine())
    engine.board.influence['Cameroon']['US'] = 1
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert raw > 0
    assert after == raw

    engine.board.influence['Angola']['USSR'] = 1
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert after < raw


def _codex_board(**influence):
    engine = Engine(seed=1)
    for values in engine.board.influence.values():
        values.update(US=0, USSR=0)
    for key, n in influence.items():
        cid, side = key.rsplit('_', 1)
        engine.board.influence[cid][side] = n
    return engine


def test_unreachable_reply_reproduction(monkeypatch):
    """No placement answer where the USSR cannot reach -- but Zaire is a
    battleground, and at DEFCON 5 a USSR Coup can answer, so the placement
    rule is pinned with Coup answers switched off, and the Coup is checked
    to be what remains."""
    raw, after = _priced(_codex_board(Angola_US=1), Side.US, 'Zaire', 1, budget=4)
    assert raw > 0
    assert after < raw, 'a 4-Op Coup answers what no placement can'
    monkeypatch.setattr(StrategicPlayer, '_may_coup', lambda *args: False)
    _, placement_only = _priced(_codex_board(Angola_US=1), Side.US, 'Zaire', 1, budget=4)
    assert placement_only == raw


def test_retake_uses_doubling_rule_point_by_point():
    def position():
        engine = _zaire(bare_engine())
        engine.board.influence['Cameroon']['US'] = 1
        engine.board.influence['Angola']['USSR'] = 1
        return engine

    raw, after = _priced(position(), Side.US, 'Zaire', 1, budget=3)
    assert after < raw
    raw, after = _priced(position(), Side.US, 'Zaire', 1, budget=2)
    assert after == raw
    # Overprotected by one: 2 + 2 + 1 = 5, not 3 * 2 = 6.
    raw, after = _priced(position(), Side.US, 'Zaire', 2, budget=5)
    assert after < raw
    raw, after = _priced(position(), Side.US, 'Zaire', 2, budget=4)
    assert after == raw

    engine = position()
    engine.board.influence['Zaire']['US'] = 1
    engine.begin_influence_operations(Side.USSR, 3)
    while engine.pending_decision is not None and engine.pending_decision.kind is K.PLACE_INFLUENCE:
        engine.step(next(a for a in engine.legal_actions() if a.payload['country'] == 'Zaire'))
    assert engine.board.control('Zaire') is Side.USSR
    assert rules_math.ops_to_control(0, 1, 1) == 3


def test_chernobyl_bans_the_retake_for_the_rest_of_the_turn():
    engine = _zaire(bare_engine())
    engine.board.influence['Cameroon']['US'] = 1
    engine.board.influence['Angola']['USSR'] = 1
    engine.turn_effects['chernobyl'] = 'AFRICA'
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert after == raw


def _turn_position(placer, *, action_round, ars_played, phase='action_rounds',
                  phasing=None, turn=10, turn_effects=(), game_effects=()):
    engine = bare_engine()
    engine.turn, engine.phase = turn, phase
    engine.action_round, engine._ars_played = action_round, ars_played
    engine.turn_effects.update(turn_effects)
    engine.game_effects.update(game_effects)
    engine.board.influence['Zaire'][placer.opponent.value] = 1
    engine.board.influence['Angola'][placer.value] = 1
    if phasing is not None:
        engine._phasing_player = phasing
    engine.begin_influence_operations(placer, 2)
    engine._phasing_player = None
    return engine


TURN_ORDER = [
    ('US final play of turn 10', Side.US, {'action_round': 7, 'ars_played': 14}, False),
    ('USSR AR7 of turn 10', Side.USSR, {'action_round': 7, 'ars_played': 13}, True),
    ('US AR7 with USSR Space Station', Side.US,
     {'action_round': 7, 'ars_played': 14,
      'game_effects': {'space_race_extra_round_holder': 'USSR'}}, True),
    ('US AR7 under North Sea Oil', Side.US,
     {'action_round': 7, 'ars_played': 14,
      'turn_effects': {'north_sea_oil_extra': True}}, False),
    ('US extra round under North Sea Oil', Side.US,
     {'action_round': 8, 'ars_played': 15,
      'turn_effects': {'north_sea_oil_extra': True}}, False),
    ('US placing for a USSR card', Side.US,
     {'action_round': 7, 'ars_played': 13, 'phasing': Side.USSR}, False),
    ('USSR placing for a US card', Side.USSR,
     {'action_round': 6, 'ars_played': 12, 'phasing': Side.US}, True),
    ('US final play of turn 9', Side.US,
     {'action_round': 7, 'ars_played': 14, 'turn': 9}, True),
    ('turn 10 headline', Side.US,
     {'action_round': 1, 'ars_played': 0, 'phase': 'headline'}, True),
]


@pytest.mark.parametrize('case,placer,state,answered', TURN_ORDER,
                         ids=[case for case, *_ in TURN_ORDER])
def test_reply_needs_a_move_before_the_game_ends(case, placer, state, answered):
    engine = _turn_position(placer, **state)
    future = rules_math.next_move(engine.observe(placer), placer.opponent)
    assert (future is not None) is answered
    raw, after = _priced(engine, placer, 'Zaire', 1, budget=4)
    assert raw > 0
    if answered:
        assert after < raw, case
    else:
        assert after == raw, case


def test_final_turn_really_ends_after_the_last_play():
    engine = _turn_position(Side.US, action_round=7, ars_played=14)
    engine.step(next(a for a in engine.legal_actions() if a.payload['country'] == 'Zaire'))
    assert engine.is_terminal and engine._final_scoring_ran
    assert engine.pending_decision is None


def test_next_move_follows_engine_turn_order():
    for turn in (3, 10):
        for extras in ({}, {'north_sea_oil_extra': True}):
            engine = bare_engine()
            engine.turn, engine.phase = turn, 'action_rounds'
            engine.turn_effects.update(extras)
            engine.game_effects['space_race_extra_round_holder'] = 'USSR'
            total = engine._total_action_rounds()
            for idx in range(total):
                side = engine._side_for_play_index(idx)
                engine._ars_played, engine.action_round = idx + 1, idx // 2 + 1
                engine._decision_stack.clear()
                engine.begin_influence_operations(side, 1)
                obs = engine.observe(side)
                for who in (Side.US, Side.USSR):
                    later = engine._next_play_index_for(who)
                    want = 0 if later is not None else (1 if turn < 10 else None)
                    assert rules_math.next_move(obs, who) == want, (turn, extras, idx, who)


# -- the opponent may answer with a Coup --------------------------------------
#
# Placement is not the only answer. With each budget the opponent takes
# whichever hurts more: the retake, or a Coup on the same country. A Coup needs
# no reach and ignores the doubling rule, so these positions are built so that
# the retake is impossible and only the Coup can answer -- and each is paired
# with the one rules fact that takes the Coup away.

def _overprotected_lebanon(defcon):
    """The US puts 3 into an empty Lebanon (stability 1, not a Battleground):
    a retake is 2 + 2 + 2 + 1 = 7 Ops, past any card, but a 4-Op Coup
    removes all three on every roll."""
    engine = bare_engine()
    engine.defcon = defcon
    engine.board.influence['Israel']['US'] = 1
    engine.board.influence['Syria']['USSR'] = 1
    return engine


def test_a_coup_answers_a_placement_no_retake_can():
    assert rules_math.ops_to_control(0, 3, 1) == 7
    raw, after = _priced(_overprotected_lebanon(5), Side.US, 'Lebanon', 3, budget=4)
    assert after < raw, 'a 4-Op Coup wipes three points and was not charged'


def test_no_coup_answer_where_defcon_bans_coups_in_the_region():
    """The Middle East closes to Coups below DEFCON 3 (8.1.5)."""
    raw, after = _priced(_overprotected_lebanon(3), Side.US, 'Lebanon', 3, budget=4)
    assert after < raw, 'control: DEFCON 3 allows it'
    raw, after = _priced(_overprotected_lebanon(2), Side.US, 'Lebanon', 3, budget=4)
    assert after == raw
    # The ban is DEFCON at *their* move: after the US's last play of turn 5
    # the USSR next moves on turn 6, when DEFCON has recovered to 3.
    engine = _overprotected_lebanon(2)
    engine.turn, engine.phase, engine.action_round, engine._ars_played = 5, 'action_rounds', 7, 14
    engine.begin_influence_operations(Side.US, 3)
    raw, after = _priced(engine, Side.US, 'Lebanon', 3, budget=4)
    assert after < raw


def test_nato_leaves_us_controlled_europe_without_a_coup_answer():
    def position(nato):
        engine = bare_engine()
        engine.board.influence['Italy']['US'] = 1   # reach; the USSR reaches nothing near
        if nato:
            engine.game_effects['nato'] = True
        return engine

    raw, after = _priced(position(nato=False), Side.US, 'Spain_Portugal', 2, budget=4)
    assert after < raw, 'control: without NATO the USSR may Coup it'
    raw, after = _priced(position(nato=True), Side.US, 'Spain_Portugal', 2, budget=4)
    assert after == raw


def test_a_battleground_coup_at_defcon_two_is_no_answer():
    """Nuclear war for the phasing player, which a side on its own move is."""
    def position(defcon, cid='Zaire'):
        engine = bare_engine()
        engine.defcon = defcon
        engine.board.influence['Cameroon' if cid == 'Zaire' else 'Zaire']['US'] = 1
        return engine

    raw, after = _priced(position(2), Side.US, 'Zaire', 1, budget=4)
    assert after == raw
    raw, after = _priced(position(3), Side.US, 'Zaire', 1, budget=4)
    assert after < raw, 'control: at DEFCON 3 the Coup is safe'
    raw, after = _priced(position(2, cid='Cameroon'), Side.US, 'Cameroon', 1, budget=4)
    assert after < raw, 'control: a non-Battleground Coup never touches DEFCON'


def test_nuclear_subs_leaves_the_us_its_battleground_coup_answer():
    def position(subs):
        engine = bare_engine()
        engine.defcon = 2
        engine.board.influence['Angola']['USSR'] = 1   # the US reaches nothing near Zaire
        if subs:
            engine.turn_effects['nuclear_subs'] = True
        return engine

    raw, after = _priced(position(subs=False), Side.USSR, 'Zaire', 1, budget=4)
    assert after == raw
    raw, after = _priced(position(subs=True), Side.USSR, 'Zaire', 1, budget=4)
    assert after < raw


def test_the_reply_is_off_at_reply_model_zero():
    engine = _overprotected_lebanon(5)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer(dataclasses.replace(StrategicWeights(), reply_model=0.))
    bot.prepare(obs)
    raw = bot.delta(obs, 'Lebanon', own=3)
    assert bot._after_reply(obs, 'Lebanon', 3, raw) == raw
