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


def test_a_safe_root_holds_only_plays_as_safe_as_the_policys_pick():
    """Survival first, then search: every root card's turn-loss risk is no
    higher than the policy's top card's, and none is cornered unless it is."""
    logging.getLogger('struggler').setLevel(logging.ERROR)
    obs = _ar1_position()
    player = MCTSPlayer(seed=1, simulations=2, search_all=True, horizon=1, safe_root=True)
    safe = player.ranked(obs)
    risks = player.policy._risks
    _, top, top_cornered = risks[id(safe[0])]
    for a in safe:
        _, risk, cornered = risks[id(a)]
        assert risk <= top + 1e-12 and (top_cornered or not cornered)
    assert player.choose_action(obs, []) in obs.pending_decision.options


def test_an_edge_knows_its_standard_error():
    from struggler.bots.mcts import Edge
    e = Edge()
    assert e.variance_of_mean == float('inf')
    for r in (0.0, 1.0, 0.0, 1.0):
        e.visits += 1; e.total += r; e.squares += r * r
    assert e.mean == 0.5
    assert e.variance_of_mean == pytest.approx((1.0 / 3.0) / 4)


def test_an_unconfident_search_plays_the_policys_card():
    """Traced 2026-09-27 (seed 151001): overrides decided by 0.0004 over 33
    visits each. With `confidence` the root defers to the policy unless the
    searched best beats the policy's card by that many standard errors; an
    unreachable bar means the policy's card, always."""
    logging.getLogger('struggler').setLevel(logging.ERROR)
    obs = _ar1_position()
    player = MCTSPlayer(seed=1, simulations=8, search_all=True, horizon=1, confidence=1e9)
    action = player.choose_action(obs, [])
    assert action.payload['card'] == player.last_search['policy_card'] == player.last_search['chosen']
