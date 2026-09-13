"""What the shared history tells a player about the other hand.

`runner.play_game` hands *both* players the same `history`, so every
`Event` in it crosses a seat boundary. `replay.build_event` records
`decision.public()` rather than the Decision, which closes the option
list -- after a headline pick that list is the actor's whole remaining
hand, and eight opponent cards were recoverable from one recorded event.

But `public()` deliberately keeps `context`, on the reasoning that "what
the actor is being asked" is public. That reasoning is not checked
anywhere, and it is the kind that stays true until someone adds a
context key. These tests check it against the rules' own notion of
public: a card is public once it has been *chosen* in an event the
history already carries, or once it is in the discard or removed piles.

Mandate #4 is that hidden information is absent, never masked -- so a
leak here is not a display bug, it is the engine handing a bot a fact the
rules do not give it.
"""
from __future__ import annotations

import random

import pytest

from struggler.engine import DecisionKind as K, Engine, Side
from struggler.engine.cards import load_cards
from struggler.engine.replay import HistoryBuilder

CARD_IDS = frozenset(load_cards())


def card_ids_in(value, path='', found=None):
    """Every card id reachable in a nested payload, with the path to it."""
    found = [] if found is None else found
    if isinstance(value, str):
        if value in CARD_IDS:
            found.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            card_ids_in(item, f'{path}.{key}', found)
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            card_ids_in(item, f'{path}[{i}]', found)
    return found


def play_random_game(seed: int, driver_seed: int, max_steps: int = 4000):
    """A full game driven by random legal choices, yielding the shared
    history as it grows. Random, not a bot: this asks what the engine
    *records*, which no policy affects, and a bot would cost seconds.
    """
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    driver = random.Random(driver_seed)
    builder = HistoryBuilder()
    steps = 0
    while not engine.is_terminal and steps < max_steps:
        decision = engine.pending_decision
        action = (decision.options[0] if decision.actor is Side.CHANCE
                  else driver.choice(engine.legal_actions()))
        engine.step(action)
        builder.record(decision, action, engine)
        yield engine, builder.history
        steps += 1


@pytest.mark.parametrize('seed,driver_seed', [(7000, 1), (7001, 2), (7002, 3)])
def test_shared_history_names_no_card_it_has_not_revealed(seed, driver_seed):
    """Every card id in the shared history is one the table has seen.

    The oracle is the history itself plus the public piles, not a
    hand-rolled list of what "ought" to be visible: a card becomes public
    by being chosen in a recorded event (that is what playing a card *is*),
    or by reaching the discard or removed pile.
    """
    for engine, history in play_random_game(seed, driver_seed):
        revealed = set(engine.discard_pile) | set(engine.removed_cards)
        for event in history:
            # A chosen card is face up: the choice is the reveal. Walked in
            # order, so a later reveal cannot excuse an earlier leak -- the
            # PLAY_MODE context that names the card being played is covered
            # by the ACTION_ROUND_PLAY event that chose it, one event back.
            revealed.update(cid for _path, cid in card_ids_in(dict(event.action.payload)))
            for path, cid in card_ids_in(dict(event.decision.context)):
                assert cid in revealed, (
                    f'seed {seed}: the shared history names {cid} at '
                    f'{event.decision.kind.value} context{path}, and nothing '
                    f'public has revealed it. Both players are handed this '
                    f'history -- see Decision.public() and mandate #4.')


@pytest.mark.parametrize('seed,driver_seed', [(7000, 1), (7001, 2), (7002, 3)])
def test_shared_history_carries_no_option_list_of_cards(seed, driver_seed):
    """The leak that was actually found and closed: a recorded Decision's
    options are the actor's hand."""
    for _engine, history in play_random_game(seed, driver_seed):
        for event in history:
            if event.actor not in (Side.US, Side.USSR):
                continue  # a CHANCE reveal has no owner to keep a secret from
            named = {cid for option in event.decision.options
                     for _path, cid in card_ids_in(dict(option.payload))}
            assert len(named) <= 1, (
                f'a recorded {event.decision.kind.value} lists {len(named)} cards '
                f'as options: {sorted(named)}. build_event must record '
                f'decision.public().')


def test_a_headline_pick_is_not_visible_before_the_reveal():
    """The one place secrecy is load-bearing. Both headlines are chosen
    before either resolves, so the first pick must not reach the shared
    history until the second is in."""
    engine = Engine.new_game(seed=7000, setup_bonus=True)
    driver = random.Random(5)
    builder = HistoryBuilder()
    picks = 0
    while not engine.is_terminal and picks < 2:
        decision = engine.pending_decision
        action = (decision.options[0] if decision.actor is Side.CHANCE
                  else driver.choice(engine.legal_actions()))
        engine.step(action)
        builder.record(decision, action, engine)
        if decision.kind is K.HEADLINE_PLAY:
            picks += 1
            if picks == 1:
                assert not [e for e in builder.history if e.decision.kind is K.HEADLINE_PLAY], (
                    'the first headline pick reached the shared history before the '
                    'second was chosen; HistoryBuilder must buffer the pair')
    assert picks == 2, 'no headline pair was played'
    pair = [e for e in builder.history if e.decision.kind is K.HEADLINE_PLAY]
    assert len(pair) == 2, 'both halves of the pair should arrive together at the reveal'
