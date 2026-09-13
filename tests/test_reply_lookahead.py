"""The reply look-ahead may only charge an answer the rules allow.

`StrategicPlayer._after_reply` discounts a placement that changes control by
what the opponent's answer takes back. Codex's audit of 2026-09-13
(`docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md`) found it charging
three answers the rules do not give them:

- Q1, a placement where the opponent cannot place;
- Q2, a retake priced at the first point's doubled cost for every point;
- F5, an answer after the game's last possible move.

These are its reproductions. Each carries the control that shows the test
can fail: the same position with the one fact changed does get a discount.
"""
from __future__ import annotations

import dataclasses

import pytest

from conftest import bare_engine
from struggler.bots import rules_math
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import DecisionKind as K, Engine, Side


def _priced(engine, side, cid, points, budget):
    """(raw, after the reply) for `side` placing `points` in `cid`, against
    an opponent who always answers with exactly `budget` Ops (model 1)."""
    obs = engine.observe(side)
    weights = dataclasses.replace(StrategicWeights(), reply_model=1., reply_ops=float(budget))
    bot = StrategicPlayer(weights)
    bot.prepare(obs)
    raw = bot.delta(obs, cid, own=points)
    before = bot.board.serialize()
    after = bot._after_reply(obs, cid, points, raw)
    assert bot.board.serialize() == before, 'the look-ahead left the board moved'
    return raw, after


def _zaire(engine):
    # DEFCON 2: a Battleground Coup would be nuclear war for whoever made it,
    # so placement is the only answer the rules leave in Zaire.
    engine.defcon = 2
    return engine


def test_q1_no_reply_where_the_opponent_cannot_place():
    engine = _zaire(bare_engine())
    engine.board.influence['Cameroon']['US'] = 1   # the US reaches Zaire; the USSR nothing near it
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert raw > 0
    assert after == raw, 'charged a retake the USSR has no legal placement for'

    engine.board.influence['Angola']['USSR'] = 1   # a foothold next door
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert after < raw, 'control: with access the retake is legal and must be charged'


def _codex_board(**influence):
    """Codex's follow-up setup (2026-09-13): `Engine(seed=1)` with every
    country emptied, then only the influence named, as `Country_SIDE=n`."""
    engine = Engine(seed=1)
    for values in engine.board.influence.values():
        values.update(US=0, USSR=0)
    for key, n in influence.items():
        cid, side = key.rsplit('_', 1)
        engine.board.influence[cid][side] = n
    return engine


def test_q1_codex_followup_reproduction():
    """Codex re-reproduced Q1 with exact numbers: US Angola 1 only, US +1
    Zaire, a fixed 4-Op reply. Before the fix the adjusted value was
    -23.843867 although the USSR has no placement access; now it is the raw
    value untouched. At DEFCON 5 a USSR Coup *could* answer, which is the
    next change's business -- here only the placement answer exists."""
    raw, after = _priced(_codex_board(Angola_US=1), Side.US, 'Zaire', 1, budget=4)
    assert raw == pytest.approx(21.512711, abs=1e-6)
    assert after == raw


def test_q2_codex_followup_reproduction():
    """Codex's Q2: USSR Angola 1 only, US +1 Zaire, a fixed 3-Op reply. Before
    the fix raw and adjusted were equal -- the retake was priced at 4 Ops and
    declined. It costs 3, so the reply applies at budget 3 and not at 2.

    Codex reported raw 26.046533 at 51e4ca4; at this branch's base (7e3d911)
    the same setup gives 23.843867, and the pre-fix defect (adjusted == raw)
    reproduces identically, so the value is pinned as measured here."""
    raw, after = _priced(_codex_board(Angola_USSR=1), Side.US, 'Zaire', 1, budget=3)
    assert raw == pytest.approx(23.843867, abs=1e-6)
    assert after < raw, 'a 3-Op retake was declined as if it cost 4'
    raw, after = _priced(_codex_board(Angola_USSR=1), Side.US, 'Zaire', 1, budget=2)
    assert after == raw


def test_q1_chernobyl_bans_the_retake_for_the_rest_of_the_turn():
    engine = _zaire(bare_engine())
    engine.board.influence['Cameroon']['US'] = 1
    engine.board.influence['Angola']['USSR'] = 1
    engine.turn_effects['chernobyl'] = 'AFRICA'
    raw, after = _priced(engine, Side.US, 'Zaire', 1, budget=4)
    assert after == raw


def test_q2_a_retake_pays_the_doubling_rule_point_by_point():
    """Zaire US 1 / USSR 0 with USSR access from Angola: two Ops to break
    the US, one to take it -- three, where `points * cost` said four."""
    def position():
        engine = _zaire(bare_engine())
        engine.board.influence['Cameroon']['US'] = 1
        engine.board.influence['Angola']['USSR'] = 1
        return engine

    raw, after = _priced(position(), Side.US, 'Zaire', 1, budget=3)
    assert after < raw, 'a three-Op budget retakes it and was not charged'
    raw, after = _priced(position(), Side.US, 'Zaire', 1, budget=2)
    assert after == raw
    # Overprotected by one: 2 + 2 + 1 = 5, not 3 * 2 = 6.
    raw, after = _priced(position(), Side.US, 'Zaire', 2, budget=5)
    assert after < raw
    raw, after = _priced(position(), Side.US, 'Zaire', 2, budget=4)
    assert after == raw

    # And the real engine agrees about the three.
    engine = position()
    engine.board.influence['Zaire']['US'] = 1
    engine.begin_influence_operations(Side.USSR, 3)
    while engine.pending_decision is not None and engine.pending_decision.kind is K.PLACE_INFLUENCE:
        engine.step(next(a for a in engine.legal_actions() if a.payload['country'] == 'Zaire'))
    assert engine.board.control('Zaire') is Side.USSR
    assert rules_math.ops_to_control(0, 1, 1) == 3


def _turn_ten(placer, *, action_round, ars_played, phase='action_rounds',
              phasing=None, turn=10, turn_effects=(), game_effects=()):
    """`placer` about to spend 2 Ops breaking the opponent's Zaire (1 point
    at the doubled rate), the opponent able to take it straight back."""
    engine = bare_engine()
    engine.turn, engine.phase = turn, phase
    engine.action_round, engine._ars_played = action_round, ars_played
    engine.turn_effects.update(turn_effects)
    engine.game_effects.update(game_effects)
    engine.board.influence['Zaire'][placer.opponent.value] = 1
    engine.board.influence['Angola'][placer.value] = 1
    if phasing is not None:
        engine._phasing_player = phasing   # stamped on the decision pushed below
    engine.begin_influence_operations(placer, 2)
    engine._phasing_player = None
    return engine


# (case, placer, turn-order state, whether the opponent still gets a move)
TURN_ORDER = [
    ('the US final play of turn 10', Side.US, dict(action_round=7, ars_played=14), False),
    ('the USSR AR7 of turn 10, the US still to play', Side.USSR, dict(action_round=7, ars_played=13), True),
    ('the US AR7 of turn 10, the USSR holding the Space Station', Side.US,
     dict(action_round=7, ars_played=14, game_effects={'space_race_extra_round_holder': 'USSR'}), True),
    ('the US AR7 of turn 10 under North Sea Oil: the extra round is the US', Side.US,
     dict(action_round=7, ars_played=14, turn_effects={'north_sea_oil_extra': True}), False),
    ('the US extra round of turn 10 itself', Side.US,
     dict(action_round=8, ars_played=15, turn_effects={'north_sea_oil_extra': True}), False),
    ('the US placing for a USSR card in the USSR AR7 of turn 10', Side.US,
     dict(action_round=7, ars_played=13, phasing=Side.USSR), False),
    ('the USSR placing for a US card in the US AR6 of turn 10', Side.USSR,
     dict(action_round=6, ars_played=12, phasing=Side.US), True),
    ('the US final play of turn 9: the USSR plays next turn', Side.US,
     dict(action_round=7, ars_played=14, turn=9), True),
    ('a headline of turn 10', Side.US, dict(action_round=1, ars_played=0, phase='headline'), True),
]


@pytest.mark.parametrize('case,placer,state,answered', TURN_ORDER, ids=[c[0] for c in TURN_ORDER])
def test_f5_a_reply_needs_a_move_before_the_game_ends(case, placer, state, answered):
    engine = _turn_ten(placer, **state)
    assert rules_math.next_move(engine.observe(placer), placer.opponent) is not None if answered \
        else rules_math.next_move(engine.observe(placer), placer.opponent) is None
    raw, after = _priced(engine, placer, 'Zaire', 1, budget=4)
    assert raw > 0
    if answered:
        assert after < raw, f'{case}: the opponent moves again and was not charged'
    else:
        assert after == raw, f'{case}: charged a reply the opponent never gets'


def test_f5_the_audit_reproduction_really_ends_the_game():
    """The final US play of turn 10 is followed by Final Scoring, not a reply."""
    engine = _turn_ten(Side.US, action_round=7, ars_played=14)
    engine.step(next(a for a in engine.legal_actions() if a.payload['country'] == 'Zaire'))
    assert engine.is_terminal and engine._final_scoring_ran and engine.pending_decision is None


def test_next_move_follows_the_engine_turn_order_through_a_whole_turn():
    """`next_move` locates the current play from the observation; the engine
    knows it outright. Walk every play of a turn with both extra rounds in
    force and compare against the engine's own index arithmetic."""
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
