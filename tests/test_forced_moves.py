"""Positions where a strong player's move is not a matter of judgement.

The value function is measured two ways today, and both are indirect: the
gate plays games and reports a score, and `models/expert_valuations.json`
checks that the bot *ranks* things in the maintainer's order. Neither
asks the question a player would -- given this board, does it make the
move? A ranking can be right while the action is wrong, because the
action comes out of a stack of decisions (which card, then which mode,
then where) and only the last of them is what the ranking scored.

So this file is a third instrument: boards where one move is obvious, and
an assertion that the bot plays it. They are deterministic, they take
milliseconds, and a failure names the position rather than a score.

The bar for adding one is that the maintainer would call the move forced,
not merely best -- these are specifications, and a fixture that encodes a
close judgement call will fossilise it (shape 8 in
docs/CLAUDE_NOTES.md). Every case says why the move is forced.

All the cases below currently pass. They are regression gates, not open
defects.
"""
from __future__ import annotations

from struggler.bots.strategic import StrategicPlayer
from struggler.engine import DecisionKind as K, Engine, Region, Side


def opened(seed: int = 4000) -> Engine:
    """A game played through setup only, so the board is the opening book."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    while engine.phase == 'setup' and not engine.is_terminal:
        decision = engine.pending_decision
        engine.step(decision.options[0] if decision.actor is Side.CHANCE
                    else StrategicPlayer().choose_action(engine.observe(decision.actor), []))
    return engine


def choose(engine: Engine, side: Side):
    return StrategicPlayer().choose_action(engine.observe(side), [])


def test_the_ussr_spaces_a_us_card_it_would_otherwise_have_to_play():
    """Grain Sales to Soviets, the last card of the turn, as the USSR.

    Playing it for Operations fires the US event: the US sees a random
    USSR card and may play it. The Space Race takes the card off the
    board entirely and pays for the privilege. There is no third option
    and nothing to weigh -- the Ops are not worth handing over a card.
    """
    engine = opened()
    engine.turn, engine.phase, engine.action_round = 5, 'action_rounds', 7
    engine.hands['USSR'] = ['Grain_Sales_to_Soviets']
    engine.hands['US'] = ['Truman_Doctrine']
    engine.china_card_owner = Side.US          # leave exactly one card to play
    engine._push_action_round_play(Side.USSR)

    engine.step(choose(engine, Side.USSR))
    decision = engine.pending_decision
    assert decision.kind is K.PLAY_MODE
    modes = {action.payload['mode'] for action in decision.options}
    assert {'ops', 'event', 'space_race'} <= modes, f'the position lost an option: {modes}'
    assert choose(engine, Side.USSR).payload['mode'] == 'space_race'


def test_the_first_point_goes_to_an_empty_battleground_in_an_unscored_region():
    """South America is untouched: no influence anywhere, nothing scored.

    With the USSR holding Venezuela outright, Brazil next door is an empty
    Battleground -- uncontested, in a region where the first Presence is
    free and the region cannot be scored against anyone. Nothing else
    reachable buys a Battleground nobody is contesting, so the first point
    goes there.
    """
    engine = opened()
    engine.turn, engine.phase, engine.action_round = 5, 'action_rounds', 1
    engine.board.influence['Venezuela']['USSR'] = 3
    engine.begin_influence_operations(Side.USSR, 2)

    decision = engine.pending_decision
    assert decision.kind is K.PLACE_INFLUENCE
    reachable = {action.payload['country'] for action in decision.options}
    assert 'Brazil' in reachable, 'the fixture no longer offers the empty Battleground'
    board = engine.board
    assert board.influence['Brazil'] == {'US': 0, 'USSR': 0}, 'Brazil is not empty'
    assert all(board.influence[cid] == {'US': 0, 'USSR': 0}
               for cid in board.countries
               if board.countries[cid].region is Region.SOUTH_AMERICA
               and cid != 'Venezuela'), 'South America is not untouched'

    assert choose(engine, Side.USSR).payload['country'] == 'Brazil'
