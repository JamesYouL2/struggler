"""What a seat can deduce about the opponent's hand from public counts.

`card_state` used to call the draw pile and the opponent's hand
"deliberately indistinguishable, mandate #4". That misread the mandate.
Mandate #4 constrains what `observe()` may *expose* -- the opponent's card
identities, and the identity of undrawn cards -- and in the same breath
makes their hand *count* public, along with the draw pile size, the discard
pile and the removed cards. Inferring a distribution from those is not
peeking; it is what a strong player does at the table, and the engine was
already handing the bot every input required.
"""
from __future__ import annotations

import pytest

from struggler.engine import Engine, Side
from struggler.bots.strategic.public_cards import (
    CHINA_CARD, card_state, p_opponent_holds, unseen_cards, unseen_split)


def opening(seed: int = 4000, side: Side = Side.US):
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    return engine, engine.observe(side)


def test_the_unseen_pool_accounts_for_every_hidden_card():
    """The pool must be exactly their hand plus the draw pile. If it is not,
    something is being counted that is not hidden, or something hidden is
    being missed -- and every per-card probability drawn from it is wrong."""
    for seed in (4000, 4001, 4002):
        for side in (Side.US, Side.USSR):
            _engine, obs = opening(seed, side)
            theirs, pile = unseen_split(obs)
            assert len(unseen_cards(obs)) == theirs + pile, (
                f'seed {seed} {side.value}: pool {len(unseen_cards(obs))} against '
                f'{theirs} in hand + {pile} in the pile')


def test_the_probabilities_sum_to_their_hand_size():
    """The consistency check that makes the pool trustworthy: the expected
    number of unseen cards in their hand is their hand size."""
    _engine, obs = opening()
    total = sum(p_opponent_holds(obs, c) for c in unseen_cards(obs))
    assert total == pytest.approx(obs.opponent_hand_size)


def test_the_china_card_is_not_in_the_unseen_pool():
    """Its owner is public (`obs.china_card_owner`) and it counts toward
    nobody's hand size. Left as 'unseen' it was a permanent phantom,
    inflating the pool by one for the whole game."""
    _engine, obs = opening()
    assert CHINA_CARD not in obs.hand, 'fixture assumption: we do not hold it'
    assert card_state(obs, CHINA_CARD) == 'china'
    assert CHINA_CARD not in unseen_cards(obs)
    assert p_opponent_holds(obs, CHINA_CARD) == 0.0


def test_nothing_visible_is_given_a_probability():
    """Our own cards, played cards and removed cards are known, not guessed."""
    _engine, obs = opening()
    for card in obs.hand:
        assert p_opponent_holds(obs, card) == 0.0
    for card in obs.discard_pile + obs.removed_cards:
        assert p_opponent_holds(obs, card) == 0.0


def test_knowledge_rises_as_the_draw_pile_empties():
    """The point of the whole thing. The pile drains before every reshuffle,
    so an unseen card becomes steadily more likely to be in their hand --
    measured on captured play, 17.6% at turn 1 against 34.6% at turn 2. This
    pins the direction with a synthetic pile rather than a whole game.
    """
    _engine, obs = opening()
    early = p_opponent_holds(obs, unseen_cards(obs)[0])

    drained = obs._replace(draw_pile_size=2) if hasattr(obs, '_replace') else None
    if drained is None:                       # not a NamedTuple; build by hand
        import dataclasses
        drained = dataclasses.replace(obs, draw_pile_size=2)
    late = p_opponent_holds(drained, unseen_cards(obs)[0])
    assert late > early, f'a draining pile must raise the odds: {early} -> {late}'
    assert late == pytest.approx(obs.opponent_hand_size / (obs.opponent_hand_size + 2))
