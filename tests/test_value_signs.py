"""Sign invariants the maintainer states as always-true.

Two of them, and they are worth mechanising because the failures this
repo produces are sign failures: the forward search's discount inverted
and spent a day looking like a no-op, and a `CardSide is Side.US`
comparison priced a whole term at zero. Neither showed up in a value
test; both would have shown up in a sign test.

  1. "Space is better than nothing."  The Space Race attempt is worth
     positive expected VP whenever the rules allow it.
  2. "Playing any non-opponent card is better than nothing."  Our own
     cards and neutrals cannot be worth less than not playing them --
     only an *opponent's* card can, because playing it fires their event.
"""
from __future__ import annotations

import pytest

from struggler.bots.greedy import _space_race_expected_vp
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.policy import CARDS, is_certain
from struggler.engine import Engine, Side


def primed(turn: int = 5, side: Side = Side.US):
    engine = Engine.new_game(seed=4000)
    bot = StrategicPlayer()
    while engine.phase == 'setup' and not engine.is_terminal:
        d = engine.pending_decision
        engine.step(d.options[0] if d.actor is Side.CHANCE
                    else bot.choose_action(engine.observe(d.actor), []))
    engine.turn, engine.phase = turn, 'action_rounds'
    engine._push_action_round_play(side)
    obs = engine.observe(side)
    player = StrategicPlayer()
    player.rank_actions(obs)
    return engine, player, obs


@pytest.mark.parametrize('turn', [1, 4, 8, 10])
def test_a_space_race_attempt_is_worth_more_than_nothing(turn):
    """The *gross* value of the attempt, not `space_value`, which nets off
    a 0.4 opportunity charge for the card it costs and is negative for a
    big card by design. The planner wants the gross value of each mode and
    should make the comparison itself; conflating the two is why this
    needed saying.
    """
    _engine, bot, obs = primed(turn)
    for side in (Side.US, Side.USSR):
        expected = _space_race_expected_vp(obs, side)
        assert expected >= 0, f'turn {turn} {side.value}: negative expected VP {expected}'
    # Not yet at the top of the track, so there is something to gain.
    assert _space_race_expected_vp(obs, obs.side) > 0, (
        'the Space Race is worth nothing from the start of the track')


def test_playing_our_own_or_a_neutral_card_beats_not_playing_it():
    """Only an opponent's card can be worth less than nothing, because
    playing it fires their event. Ours and the neutrals always buy either
    their Ops or their event, both of which are non-negative."""
    _engine, bot, obs = primed(5)
    negative = []
    for cid, card in CARDS.items():
        if not card.in_deck or card.scoring or card.ops <= 0:
            continue
        if card.side.value == obs.side.opponent.value:
            continue  # theirs: allowed to be negative, that is the point
        event = bot.event_value(obs, cid)
        if is_certain(event):
            continue  # an ordering flag, not a price
        value = bot.card_play_value(obs, cid, card.ops, event)
        if value < 0:
            negative.append((cid, card.side.value, card.ops, round(value, 1)))
    assert not negative, (
        'these are ours or neutral and price below zero, so the bot would '
        'rather hold them than play them, which the Ops alone forbid: '
        f'{negative[:8]}')
