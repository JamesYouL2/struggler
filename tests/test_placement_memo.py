"""The cross-decision placement memo changes no decision.

`StrategicPlayer._placement_ops_value` keeps its results across decisions,
keyed on everything the search reads (see its comment). The parity corpus
cannot test that: it builds a fresh bot per record, so the memo never hits
there. This plays the same games with the memo on and off and requires the
same action at every step -- a stale key would show up as a divergence.
"""
from __future__ import annotations

import logging

import pytest

from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Engine, Side


def _play(seed: int, memo: bool, stop_turn: int) -> list:
    old = StrategicPlayer.PLACEMENT_MEMO
    StrategicPlayer.PLACEMENT_MEMO = memo
    try:
        logging.getLogger('struggler').setLevel(logging.ERROR)
        engine = Engine.new_game(seed=seed, setup_bonus=True)
        bots = {s: StrategicPlayer() for s in (Side.US, Side.USSR)}
        moves = []
        while not engine.is_terminal and engine.turn <= stop_turn:
            d = engine.pending_decision
            action = (d.options[0] if d.actor is Side.CHANCE
                      else bots[d.actor].choose_action(engine.observe(d.actor), []))
            moves.append((d.kind.name, repr(action.payload)))
            engine.step(action)
        return moves
    finally:
        StrategicPlayer.PLACEMENT_MEMO = old


@pytest.mark.parametrize('seed', [4100, 4101])
def test_the_memo_changes_no_move(seed):
    with_memo = _play(seed, True, stop_turn=3)
    without = _play(seed, False, stop_turn=3)
    assert with_memo == without


def test_the_memo_actually_hits(monkeypatch):
    """A memo that never hits would pass the test above vacuously. A hit
    skips the search, so the same game with the memo on runs markedly
    fewer `_investment` evaluations."""
    counts = {}
    original = StrategicPlayer._investment

    def counting(self, *a, **k):
        counts[StrategicPlayer.PLACEMENT_MEMO] = counts.get(StrategicPlayer.PLACEMENT_MEMO, 0) + 1
        return original(self, *a, **k)

    monkeypatch.setattr(StrategicPlayer, '_investment', counting)
    _play(4100, True, stop_turn=2)
    _play(4100, False, stop_turn=2)
    assert counts[True] < 0.8 * counts[False], counts
