"""Astra's 2026-09-27 audit (docs/notes/codex/2026-09-27-correctness-rust-readiness.md):
the rules and scorer defects F1, F2, F4, each reproduced on the smallest
board that shows it, with positive controls so a fix cannot pass by
breaking the rule it sits next to."""
from __future__ import annotations

import dataclasses

import pytest

from conftest import bare_engine
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Action, Side
from struggler.engine.types import DecisionKind as K


def _empty(engine):
    for inf in engine.board.influence.values():
        inf.update(US=0, USSR=0)
    return engine


def _war(card, attacker, target, die, board):
    """Fire `card` for `attacker` on `board` ({country: (us, ussr)}), pick
    `target` if the card asks, roll `die`; the VP moved and the target's
    influence after."""
    engine = _empty(bare_engine())
    for c, (us, ussr) in board.items():
        engine.board.influence[c].update(US=us, USSR=ussr)
    vp0 = engine.vp
    engine._fire_event(attacker, card)
    d = engine.pending_decision
    if d.kind is K.WAR_TARGET:
        engine.step(Action(K.WAR_TARGET, {'country': target}))
        d = engine.pending_decision
    assert d.kind is K.WAR_ROLL
    # Outside physical mode the engine offers only the face its RNG drew;
    # force the face under test, as the event sandbox does for all six.
    (key,) = d.options[0].payload
    engine._decision_stack[-1] = dataclasses.replace(
        d, options=tuple(Action(d.kind, {key: v}) for v in range(1, 7)))
    engine.step(Action(d.kind, {key: die}))
    return engine.vp - vp0, dict(engine.board.influence[target])


# -- F1: three wars wrongly count the defender's control of the TARGET --------

@pytest.mark.parametrize('card, target, ussr, win_die, vp', [
    ('Brush_War', 'Angola', 1, 3, 1),           # modified 3-6
    ('Indo_Pakistani_War', 'India', 3, 4, 2),   # modified 4-6
    ('Iran_Iraq_War', 'Iraq', 3, 4, 2),         # modified 4-6
])
def test_these_wars_do_not_subtract_for_the_target_itself(card, target, ussr, win_die, vp):
    board = {target: (0, ussr)}  # USSR-controlled target, no controlled neighbour
    moved, after = _war(card, Side.US, target, win_die, board)
    assert moved == vp and after == {'US': ussr, 'USSR': 0}, 'the lowest winning face must win'
    moved, after = _war(card, Side.US, target, win_die - 1, board)
    assert moved == 0 and after == {'US': 0, 'USSR': ussr}, 'one face lower must lose'


def test_arab_israeli_war_still_counts_israel_itself():
    """Positive control: the target-control penalty is Arab-Israeli War's."""
    moved, _ = _war('Arab_Israeli_War', Side.USSR, 'Israel', 4, {'Israel': (4, 0)})
    assert moved == 0
    moved, _ = _war('Arab_Israeli_War', Side.USSR, 'Israel', 5, {'Israel': (4, 0)})
    assert moved == -2


def test_the_adjacent_superpower_still_counts():
    """Positive control (2.1.5): a USSR Brush War on Mexico is -1 for the US
    next door, target control aside."""
    moved, _ = _war('Brush_War', Side.USSR, 'Mexico', 3, {'Mexico': (0, 0)})
    assert moved == 0
    moved, _ = _war('Brush_War', Side.USSR, 'Mexico', 4, {'Mexico': (0, 0)})
    assert moved == -1


# -- F2: the China Card's end-of-turn-10 VP ----------------------------------

@pytest.mark.parametrize('holder, available, vp0, winner', [
    ('US', True, 0, Side.US),       # a tie becomes a win
    ('USSR', True, 0, Side.USSR),
    ('US', False, 0, Side.US),      # face down still counts
    ('USSR', False, 0, Side.USSR),
    ('US', True, -1, None),         # one down becomes a draw
    ('USSR', True, 1, None),
])
def test_the_china_card_holder_scores_one_vp_at_the_end_of_turn_10(holder, available, vp0, winner):
    engine = _empty(bare_engine())
    engine.turn = 10
    engine.vp = vp0
    engine.military_ops = {'US': 5, 'USSR': 5}
    engine.china_card_owner = holder
    engine.china_card_available = available
    engine._finish_game()
    assert engine.is_terminal
    assert engine.winner is winner
    assert engine.vp == vp0 + (1 if holder == 'US' else -1)


# -- F4: the war-target scorer agrees with the engine's roll -----------------

@pytest.mark.parametrize('card, attacker, target, board', [
    ('Brush_War', Side.USSR, 'Mexico', {'Mexico': (2, 0)}),                    # US next door
    ('Brush_War', Side.US, 'Afghanistan', {'Afghanistan': (0, 2)}),            # USSR next door
    ('Brush_War', Side.US, 'Angola', {'Angola': (0, 1), 'Zaire': (0, 2)}),     # a controlled neighbour
    ('Indo_Pakistani_War', Side.USSR, 'Pakistan', {'Pakistan': (3, 0)}),
    ('Iran_Iraq_War', Side.US, 'Iraq', {'Iraq': (0, 3), 'Iran': (0, 2)}),
])
def test_the_scorers_win_probability_is_the_engines(card, attacker, target, board):
    wins = sum(_war(card, attacker, target, die, board)[0] != 0 for die in range(1, 7))
    engine = _empty(bare_engine())
    for c, (us, ussr) in board.items():
        engine.board.influence[c].update(US=us, USSR=ussr)
    engine._fire_event(attacker, card)
    obs = engine.observe(attacker)
    bot = StrategicPlayer()
    bot.prepare(obs)
    ctx = obs.pending_decision.context
    engine_p = wins / 6
    scorer_p = bot._war_win_probability(obs, target, ctx)
    assert scorer_p == pytest.approx(engine_p), (card, target, scorer_p, engine_p)
