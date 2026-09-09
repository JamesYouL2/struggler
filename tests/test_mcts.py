"""Search returns, hidden-state isolation, and a build-before-scoring regression."""
import copy
import random

from conftest import bare_engine, assert_invariants
from struggler.bots.mcts import MCTSPlayer
from struggler.bots.strategic import CARDS
from struggler.engine import Side
from struggler.engine.cards import entry_turn


def scoring_position():
    engine = bare_engine()
    engine.turn = 4
    engine.action_round = 6
    engine.phase = 'action_rounds'
    engine._ars_played = 12
    engine.defcon = 2
    engine.hands['US'] = ['Central_America_Scoring', 'Captured_Nazi_Scientist', 'Truman_Doctrine']
    engine.board.influence['Mexico']['US'] = 1
    engine.board.influence['Cuba']['USSR'] = 3
    engine.draw_pile = [c.id for c in CARDS.values() if c.in_deck and not c.optional
                        and entry_turn(c) <= engine.turn and c.id not in engine.hands['US']]
    engine._push_action_round_play(Side.US)
    return engine


def test_leaf_counts_banked_vp_and_terminal_results_for_both_seats():
    engine = bare_engine()
    bot = MCTSPlayer()
    before = bot.leaf_return(engine, Side.US)
    board = copy.deepcopy(engine.board.influence)
    engine.vp = 6
    assert bot.leaf_return(engine, Side.US) > before
    assert bot.leaf_return(engine, Side.USSR) < -before
    assert engine.board.influence == board
    engine._winner = Side.USSR
    assert bot.leaf_return(engine, Side.US) == -1
    assert bot.leaf_return(engine, Side.USSR) == 1
    engine._winner = None
    engine.phase = 'complete'
    assert bot.leaf_return(engine, Side.US) == 0


def test_actual_scoring_order_changes_return_even_with_identical_final_board():
    early, late = scoring_position(), scoring_position()
    early._resolve_scoring_card('Central_America_Scoring')
    early.board.influence['Mexico']['US'] += 1
    late.board.influence['Mexico']['US'] += 1
    late._resolve_scoring_card('Central_America_Scoring')
    bot = MCTSPlayer()
    assert early.board.influence == late.board.influence
    assert late.vp > early.vp
    assert bot.policy.value(early.board, Side.US) == bot.policy.value(late.board, Side.US)
    assert bot.leaf_return(late, Side.US) > bot.leaf_return(early, Side.US)


def test_sampling_is_public_only_and_preserves_inventory_and_cursor():
    engine = scoring_position()
    engine.hands['USSR'] = [engine.draw_pile.pop()]
    obs = engine.observe(Side.US)
    before = engine.serialize()
    bot = MCTSPlayer()
    sample = bot.sample_engine(obs, random.Random(7))
    assert_invariants(sample)
    assert sample.observe(Side.US) == obs
    assert sample._ars_played == engine._ars_played
    engine.hands['USSR'][0], engine.draw_pile[0] = engine.draw_pile[0], engine.hands['USSR'][0]
    assert bot.sample_engine(engine.observe(Side.US), random.Random(7)).serialize() == sample.serialize()
    # Sampling didn't mutate either the input observation or the original engine.
    engine.hands['USSR'][0], engine.draw_pile[0] = engine.draw_pile[0], engine.hands['USSR'][0]
    assert engine.serialize() == before


def test_search_builds_before_scoring_and_executes_legal_macro():
    engine = scoring_position()
    before = engine.serialize()
    bot = MCTSPlayer(simulations=12, seed=3)
    action = bot.choose_action(engine.observe(Side.US), [])
    assert action.payload['card'] != 'Central_America_Scoring'
    assert engine.serialize() == before
    assert bot.last_search['simulations'] == 12
    assert bot.last_search['nodes'] > 1
    other = MCTSPlayer(simulations=12, seed=3)
    assert other.choose_action(engine.observe(Side.US), []) == action
    assert other.last_search['moves'] == bot.last_search['moves']
    # Actually execute the chosen card's micro-decisions, then score.
    engine.step(action)
    while engine.turn == 4 and not engine.is_terminal:
        d = engine.pending_decision
        a = d.options[0] if d.actor is Side.CHANCE else bot.choose_action(engine.observe(d.actor), [])
        assert a in d.options
        engine.step(a)
    assert engine.board.control('Mexico') is Side.US
    assert 'Central_America_Scoring' in engine.discard_pile
    assert engine.vp > -4  # scoring the starting position would pay USSR 4 VP


def test_target_continuation_cannot_override_defcon_safety():
    engine = bare_engine()
    engine.defcon = 2
    engine.board.influence['Mexico']['USSR'] = 2
    engine._push_ops_type(Side.US, 3)
    bot = MCTSPlayer()
    action = bot.continuation(engine.observe(Side.US), 'Mexico')
    assert action.payload['type'] != 'coup'


def test_incomplete_inventory_falls_back_to_strategic():
    engine = scoring_position()
    engine.draw_pile.clear()
    bot = MCTSPlayer(simulations=1)
    obs = engine.observe(Side.US)
    assert bot.choose_action(obs, []) == bot.policy.choose_action(obs, [])
    assert bot.last_search is None


def test_leaf_value_does_not_depend_on_what_was_ranked_before():
    """Astra's audit: an identical leaf returned three different values
    depending on which position the shared policy had ranked last, because
    value() read the previous ranking's scoring weights and caches. The
    leaf is now evaluated in its own observation's context."""
    engine = scoring_position()
    fresh = MCTSPlayer().leaf_return(engine, Side.US)
    bot = MCTSPlayer()
    bot.policy.rank_actions(engine.observe(Side.US))
    after_same = bot.leaf_return(engine, Side.US)
    other = scoring_position()
    other.hands['US'].remove('Central_America_Scoring')
    other.discard_pile.append('Central_America_Scoring')
    bot.policy.rank_actions(other.observe(Side.US))
    after_other = bot.leaf_return(engine, Side.US)
    assert fresh == after_same == after_other
    # And the leaf context differs from the ranking context when it should:
    # the same board with the scoring card gone from hand values differently.
    assert MCTSPlayer().leaf_return(other, Side.US) != fresh
