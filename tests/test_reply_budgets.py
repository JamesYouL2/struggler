"""The forward search's reply budget: what the opponent can answer with.

Two candidate models from the maintainer, 2026-09-13, each to be measured
before it ships -- the shipped default stays model 3:

  4  the budget is the MAX over what they are known to hold and a hand drawn
     from the unseen pool: a reply is made with their best card, not an
     average one. Known today means the China Card, when it is theirs and
     face up. The unseen hand is `opponent_hand_size` cards drawn without
     replacement, scoring cards included as zero-Op slots, because they take
     up room in the hand.
  5  model 3's pool, plus the China Card when it is theirs and face up.

Model 5 is the China Card phantom done properly: bc5ef93 took the China Card
out of the unseen pool everywhere (correctly -- it is face up), which also
took a 4-Op card out of every reply budget, including when the bot held it
itself. Restoring the phantom gated five points better; this keeps the card
only where it belongs, in the opponent's reply.
"""
from __future__ import annotations

import itertools

import pytest

from conftest import bare_engine
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic.policy import max_budget_weights
from struggler.engine import Side


def _brute_force(pool, hand, known):
    """Every hand of `hand` cards from `pool`, equally likely: the max of each
    hand and `known`."""
    hands = list(itertools.combinations(range(len(pool)), min(hand, len(pool))))
    counts = {}
    for chosen in hands:
        best = max([known] + [pool[i] for i in chosen])
        counts[best] = counts.get(best, 0) + 1
    return {b: n / len(hands) for b, n in counts.items()}


@pytest.mark.parametrize('pool,hand,known', [
    ([1, 2, 2, 3, 4], 2, 0),
    ([0, 1, 1, 3, 3, 4], 3, 0),
    ([2, 2, 3], 1, 0),
    ([1, 2, 3, 4], 2, 3),   # a known 3 floors every hand at 3
    ([0, 0, 1], 2, 4),      # a known 4 is the whole answer
    ([1, 2, 3], 5, 0),      # more hand than pool: they hold all of it
])
def test_the_max_budget_matches_enumerating_every_hand(pool, hand, known):
    got = dict(max_budget_weights(pool, hand, known))
    want = _brute_force(pool, hand, known)
    assert set(got) == set(want)
    for budget, weight in want.items():
        assert got[budget] == pytest.approx(weight)
    assert sum(got.values()) == pytest.approx(1.0)


def test_no_hand_and_nothing_known_is_no_reply():
    assert max_budget_weights([1, 2, 3], 0, 0) == ((0, 1.0),)


def _obs(owner: Side, available: bool, seat: Side = Side.US):
    engine = bare_engine(seed=1)
    engine.phase = 'action_rounds'
    engine.turn = 3
    engine.china_card_owner = owner.value
    engine.china_card_available = available
    # A bare engine deals nobody a hand. Only the count reaches the
    # observation (mandate #4), so which placeholders fill it does not matter.
    engine.hands[seat.opponent.value] = ['placeholder'] * 8
    return engine.observe(seat)


def _budgets(model, obs):
    return dict(StrategicPlayer(StrategicWeights(reply_model=model))._reply_budgets(obs))


def test_model_5_adds_the_china_card_only_when_the_opponent_holds_it_face_up():
    theirs = _obs(Side.USSR, True)
    shipped, with_china = _budgets(3, theirs), _budgets(5, theirs)
    assert with_china[4] > shipped[4], 'their face-up China Card is a 4-Op answer'
    assert sum(with_china.values()) == pytest.approx(1.0)
    # Ours, or face down: the opponent cannot answer with it, and model 5 is model 3.
    assert _budgets(5, _obs(Side.US, True)) == _budgets(3, _obs(Side.US, True))
    assert _budgets(5, _obs(Side.USSR, False)) == _budgets(3, _obs(Side.USSR, False))


def test_model_4_with_their_china_card_is_a_certain_four():
    assert _budgets(4, _obs(Side.USSR, True)) == {4: pytest.approx(1.0)}
    # Without it, the answer is a distribution over a drawn hand.
    ours = _budgets(4, _obs(Side.US, True))
    assert sum(ours.values()) == pytest.approx(1.0) and len(ours) > 1
