"""How often the bot breaks a Battleground with the cheapest possible point.

The maintainer's instrument, and the one that found the forward search's
inverted sign. Breaking an opponent's bare control of a Battleground
costs two Ops -- one point, at the doubled rate -- and a bot that does it
freely is handing back the exchange: the opponent repairs for less than
the break cost, and the point was spent to provoke rather than to hold.
Their estimate was about one a game, with three as the ceiling.

It is a *rate*, so it cannot be asserted from a position. That is the
whole reason it is here: every unit test of `_after_reply` asked what a
value was, and the defect was in the sign of a difference, which none of
them could see. Only playing games shows it.

Measured over 24 full games (48 seats) at the commit that turned the
search on:

                            search off   search on
    pokes per seat, mean          6.27        0.08
    median / max                  6 / 13      0 / 1
    seats above three            38/48        0/48

So the maintainer's ceiling of three separates the two arms completely,
with headroom on both sides. The bound here is theirs, not the
measurement's: fitting it to 0.08 would fail on ordinary variation,
while three still catches any return to the unsuppressed behaviour.

These games stop after turn `STOP_TURN`, because a full game costs about
thirty seconds with the search on and this file would otherwise double
the suite. The cut is where the measurement says it can be: 130 of the
301 pokes in the off arm land in the first three turns, and by the end of
turn four every seed used here already has a seat over the ceiling (4-7),
while the on arm is at 0-1 everywhere. Shortening the games costs the
separation nothing.
"""
from __future__ import annotations

import collections

import pytest

from struggler.bots.strategic import StrategicPlayer
from struggler.engine import DecisionKind as K, Engine, Side

# The maintainer's ceiling. Their estimate of the right rate is about one.
MAX_POKES_PER_SEAT = 3
SEEDS = (4000, 4001, 4002)
STOP_TURN = 4


def minimum_pokes(seed: int, weights=None) -> dict[str, int]:
    """Per seat, the number of times a spend put exactly one point into a
    Battleground the *opponent* controlled when that spend began."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(weights), Side.USSR: StrategicPlayer(weights)}
    spend: dict[tuple, int] = collections.defaultdict(int)
    started: dict[tuple, object] = {}
    while not engine.is_terminal and engine.turn <= STOP_TURN:
        decision = engine.pending_decision
        if decision.actor is Side.CHANCE:
            engine.step(decision.options[0])
            continue
        side = decision.actor
        placing = decision.kind is K.PLACE_INFLUENCE and not decision.context.get('setup')
        action = bots[side].choose_action(engine.observe(side), [])
        if placing:
            # One spend is all the points a side puts into one country in
            # one action round: a "poke" is a spend of exactly one, not a
            # single placement decision inside a larger commitment.
            key = (engine.turn, engine.action_round, side.value, action.payload['country'])
            started.setdefault(key, engine.board.control(key[3]))
            spend[key] += 1
        engine.step(action)
    pokes = collections.Counter({'US': 0, 'USSR': 0})
    for (turn, action_round, side_value, cid), points in spend.items():
        was = started[(turn, action_round, side_value, cid)]
        if points != 1 or was is None or was.value == side_value:
            continue
        if engine.board.countries[cid].battleground:
            pokes[side_value] += 1
    return dict(pokes)


@pytest.mark.parametrize('seed', SEEDS)
def test_a_seat_does_not_poke_battlegrounds_repeatedly(seed):
    """Three a seat a game is the maintainer's ceiling, not a fitted bound.

    Without the forward search this sits at a median of six and a maximum
    of thirteen, so a regression that switches it off, inverts its sign,
    or leaves it pricing against a stale base fails here.
    """
    pokes = minimum_pokes(seed)
    assert pokes, 'no seats were measured'
    for side, count in pokes.items():
        assert count <= MAX_POKES_PER_SEAT, (
            f'seed {seed} {side} broke a Battleground with the minimum two Ops '
            f'{count} times; the ceiling is {MAX_POKES_PER_SEAT} a seat. '
            f'See the forward search in policy.py (`reply_model`) and '
            f'docs/notes/claude/ "The poke count".')


def test_the_forward_search_is_what_holds_the_rate_down():
    """A negative control, so the bound above cannot pass vacuously.

    If the rate were low for some other reason -- a change in placement
    values, say -- the test above would keep passing while the search
    rotted. Turning the search off has to break it.
    """
    import dataclasses

    from struggler.bots.strategic import StrategicWeights

    off = dataclasses.replace(StrategicWeights(), reply_model=0.)
    without = minimum_pokes(SEEDS[0], off)
    assert max(without.values(), default=0) > MAX_POKES_PER_SEAT, (
        f'with the forward search off the rate is {without}, already under '
        f'the ceiling -- the test above is then passing for some other reason '
        f'and gates nothing')
