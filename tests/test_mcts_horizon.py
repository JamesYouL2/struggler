"""The MCTS horizon: a simulation stops `horizon` action rounds past the root.

`MCTSPlayer(horizon=None)` is the original prototype (rollouts to the end
of the turn); a horizon of 1 is our card play and the opponent's reply, 2
is two of each. Timed on 2026-09-27: docs/notes/claude/2026-09-27-mcts-horizons-timed.md.
"""
from __future__ import annotations

import gzip
import json
import logging

import pytest

from conftest import ROOT
from struggler.bots.mcts import MCTSPlayer
from struggler.engine import Engine, Side


def _ar1_position():
    recs = json.loads(gzip.open(ROOT / 'tests' / 'corpus' / 'positions.json.gz').read())['records']
    rec = next(r for r in recs if r['kind'] == 'action_round_play'
               and Engine.deserialize(r['engine']).action_round == 1)
    engine = Engine.deserialize(rec['engine'])
    return engine.observe(Side(rec['side']))


def test_a_horizon_must_be_positive():
    with pytest.raises(ValueError):
        MCTSPlayer(horizon=0)


@pytest.mark.parametrize('horizon', [1, 2])
def test_a_horizon_search_stops_early_and_says_so(horizon):
    logging.getLogger('struggler').setLevel(logging.ERROR)
    obs = _ar1_position()
    player = MCTSPlayer(seed=1, simulations=4, search_all=True, horizon=horizon)
    action = player.choose_action(obs, [])
    assert action in obs.pending_decision.options
    search = player.last_search
    assert search['horizon'] == horizon
    # Every simulation ends mid-turn at the horizon, scored by the value function.
    assert search['truncated'] == search['simulations'] == 4
