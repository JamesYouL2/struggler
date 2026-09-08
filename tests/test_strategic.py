"""Tactical regressions and the observation-only policy contract."""
import dataclasses

import pytest

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import Action, Decision, DecisionKind as K, Engine, Side
from struggler.bots.train import evaluate, mutate
import random


def test_invests_in_uncontrolled_battleground_without_mutating_observation():
    engine = Engine(seed=1)
    engine.board.influence['Iran']['US'] = 1
    engine._maybe_push_place_influence(Side.US, 3)
    obs = engine.observe(Side.US)
    before = engine.serialize()
    bot = StrategicPlayer()
    action = bot.choose_action(obs, [])
    assert action in obs.pending_decision.options
    assert engine.board.countries[action.payload['country']].battleground
    assert engine.serialize() == before
    assert bot.board.influence == obs.influence


def test_reused_evaluation_caches_match_fresh_policy_after_board_and_weight_changes():
    engine = Engine(seed=1)
    engine.board.influence['Iran']['US'] = 1
    engine._maybe_push_place_influence(Side.US, 3)
    bot = StrategicPlayer()
    bot.rank_actions(engine.observe(Side.US))
    engine.board.influence['Iran']['US'] = 4
    engine.board.influence['Pakistan']['USSR'] = 2
    bot.weights = StrategicWeights(progress_curve=2, battleground=7)
    obs = engine.observe(Side.US)
    assert bot.rank_actions(obs) == StrategicPlayer(bot.weights).rank_actions(obs)


@pytest.mark.parametrize('crisis', [False, True])
def test_avoids_fatal_coups(crisis):
    engine = Engine(seed=0)
    engine.defcon = 2 if not crisis else 5
    engine.board.influence['Mexico']['USSR'] = 4
    if crisis:
        engine.turn_effects['cuban_missile_crisis'] = 'US'
    engine._push_ops_type(Side.US, 4)
    obs = engine.observe(Side.US)
    assert StrategicPlayer().choose_action(obs, []).payload['type'] != 'coup'


def test_coup_expectation_accounts_for_each_die_and_clamps_removal():
    engine = Engine(seed=0)
    engine.board.influence['Mexico']['USSR'] = 2
    engine.military_ops['US'] = 5
    engine._push_ops_type(Side.US, 3)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.choose_action(obs, [])
    # Mexico stability 2: margins are 0,1,2,3,4,5 for a 3-op coup.
    expected = sum(bot.delta(obs, 'Mexico', own=max(0,m-2), opp=-min(2,m)) for m in range(6))/6
    assert bot.coup(obs, 'Mexico', 3) == pytest.approx(expected * bot.weights.coup_discount)


def test_event_removes_enemy_battleground_influence():
    engine = Engine(seed=0)
    engine.board.influence['France']['US'] = 3
    engine.board.influence['UK']['US'] = 8
    engine.push_event_influence('Suez_Crisis', 'remove', Side.USSR, Side.US, 1, ['UK','France'])
    obs = engine.observe(Side.USSR)
    action = StrategicPlayer().choose_action(obs, [])
    assert action.payload['country'] == 'France'
    engine.step(action)
    assert engine.board.control('France') is None


def test_own_duck_and_cover_can_be_used_for_ops_at_defcon_two():
    engine = Engine(seed=0)
    engine.defcon = 2
    obs = engine.observe(Side.US)
    options = tuple(Action(K.PLAY_MODE, {'mode': m}) for m in ('event','ops','space_race'))
    obs = dataclasses.replace(obs, pending_decision=Decision(1,Side.US,K.PLAY_MODE,options,{'card':'Duck_and_Cover'}))
    assert StrategicPlayer().choose_action(obs, []).payload['mode'] == 'ops'
    soviet = dataclasses.replace(obs, side=Side.USSR)
    assert StrategicPlayer().choose_action(soviet, []).payload['mode'] == 'space_race'


def test_public_event_simulation_prefers_fidel_over_dead_event():
    engine = Engine(seed=0)
    obs = engine.observe(Side.USSR)
    options = tuple(Action(K.HEADLINE_PLAY, {'card': c}) for c in ('Truman_Doctrine','Fidel'))
    obs = dataclasses.replace(obs, pending_decision=Decision(1,Side.USSR,K.HEADLINE_PLAY,options))
    before = engine.serialize()
    assert StrategicPlayer().choose_action(obs, []).payload['card'] == 'Fidel'
    assert engine.serialize() == before


def test_weight_checkpoint_roundtrip_and_validation(tmp_path):
    path = tmp_path/'weights.json'
    weights = StrategicWeights(progress=4.2)
    weights.save(path, seeds=[1,2])
    assert StrategicWeights.load(path) == weights
    with pytest.raises(ValueError):
        StrategicWeights(progress=float('nan'))


def test_paired_full_games_finish_and_are_reproducible():
    a = evaluate(StrategicWeights(), [17], 'random')
    b = evaluate(StrategicWeights(), [17], 'random')
    assert a == b
    assert a['games'] == 2
    assert {r['side'] for r in a['records']} == {'US','USSR'}
    assert all(r['winner'] in ('US','USSR',None) for r in a['records'])


def test_influence_search_prices_breaking_enemy_control():
    engine = Engine(seed=0)
    engine.board.influence['Pakistan']['USSR'] = 2
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.board.load_influence(engine.board.serialize())
    before = bot.board.serialize()
    # First point breaks control and costs two; the second costs only one.
    expected = max(bot.delta(obs, 'Pakistan', own=1)/2,
                   bot.delta(obs, 'Pakistan', own=2)/3)
    assert bot.influence(obs, 'Pakistan', 3) == pytest.approx(expected)
    assert bot.board.serialize() == before


def test_evaluation_rejects_empty_seed_set():
    with pytest.raises(ValueError, match='at least one seed'):
        evaluate(StrategicWeights(), [])


def test_live_scoring_card_raises_regional_urgency_between_hand_and_dead():
    engine = Engine(seed=0)
    engine.turn = 2
    engine.board.influence['Iran']['USSR'] = 1
    engine.hands['US'] = ['Nasser']
    bot = StrategicPlayer()
    live = engine.observe(Side.US)
    dead = dataclasses.replace(live, discard_pile=('Middle_East_Scoring',))
    held = dataclasses.replace(live, hand=live.hand+('Middle_East_Scoring',))
    urgencies = [bot.scoring_urgency(o, 'Iran') for o in (dead, live, held)]
    assert urgencies == [1.0, bot.weights.scoring_live, bot.weights.scoring_hand]
    from struggler.bots.greedy import _sync_board
    _sync_board(bot.board, live)
    deltas = [bot.delta(o, 'Iran', own=3) for o in (dead, live, held)]  # +3 takes control: the region score moves
    assert deltas[0] < deltas[1] < deltas[2]
    # Mid War scoring is not in the deck before turn 4 (static schedule).
    assert bot.scoring_urgency(dataclasses.replace(live, turn=1), 'Brazil') == 1.0
    assert bot.scoring_urgency(dataclasses.replace(live, turn=5), 'Brazil') == bot.weights.scoring_live
    # Southeast Asia Scoring reaches Thailand but not Japan, even with Asia Scoring dead.
    asia_dead = dataclasses.replace(live, turn=5, discard_pile=('Asia_Scoring',))
    assert bot.scoring_urgency(asia_dead, 'Thailand') == bot.weights.scoring_live
    assert bot.scoring_urgency(asia_dead, 'Japan') == 1.0


def test_mutation_can_be_restricted_to_named_weights():
    base = StrategicWeights()
    rng = random.Random(5)
    only = mutate(base, rng, ('scoring_live', 'scoring_hand'))
    changed = {k for k, v in dataclasses.asdict(only).items() if v != getattr(base, k)}
    assert changed == {'scoring_live', 'scoring_hand'}
    everything = mutate(base, rng)
    assert all(v != getattr(base, k) for k, v in dataclasses.asdict(everything).items())
    with pytest.raises(ValueError, match='unknown weight'):
        mutate(base, rng, ('not_a_weight',))


def test_influence_value_is_convex_and_reserve_scales_with_stability():
    engine = Engine(seed=0)
    bot = StrategicPlayer()
    board = bot.board
    board.load_influence(engine.board.serialize())
    def value_at(cid, own):
        board.influence[cid]['US'] = own
        board.influence[cid]['USSR'] = 0
        try:
            return bot.country_value(board, cid, Side.US)
        finally:
            board.influence[cid]['US'] = 0
    # Default (linear, flat) shape: the first point in stability-2 Iran is
    # priced above control's own term -- the option-value stand-in.
    empty, one, control = (value_at('Iran', n) for n in (0, 1, 2))
    assert one - empty > bot.weights.battleground
    assert value_at('Angola', 2) - value_at('Angola', 1) == value_at('Pakistan', 3) - value_at('Pakistan', 2)
    # Convex shape: well under half of control for a lone point, and a
    # reserve that is worth more where a coup is cheap.
    bot = StrategicPlayer(StrategicWeights(progress_curve=2.0, reserve_stability=1.0))
    board = bot.board
    board.load_influence(engine.board.serialize())
    empty, one, control = (value_at('Iran', n) for n in (0, 1, 2))
    assert one - empty < 0.5 * (control - empty)
    guard_low = value_at('Angola', 2) - value_at('Angola', 1)      # stability 1
    guard_high = value_at('Pakistan', 3) - value_at('Pakistan', 2)  # stability 2
    assert 0 < guard_high < guard_low


def test_country_tiers_and_coup_discount():
    engine = Engine(seed=0)
    bot = StrategicPlayer()
    board = bot.board
    board.load_influence(engine.board.serialize())
    def control_value(cid):
        info = board.countries[cid]
        board.influence[cid]['US'] = info.stability
        try:
            return bot.country_value(board, cid, Side.US)
        finally:
            board.influence[cid]['US'] = 0
    # Battleground >> Southeast Asia non-battleground >> other non-battleground.
    assert control_value('Thailand') > control_value('Malaysia') > control_value('Spain_Portugal')
    assert bot.importance(board.countries['Malaysia']) == bot.weights.southeast_asia
    # A coup is priced on the same board change as placement, then discounted.
    obs = engine.observe(Side.US)
    from struggler.bots.greedy import _sync_board
    _sync_board(bot.board, obs)
    bot.board.influence['Angola']['USSR'] = 1
    full = StrategicPlayer(StrategicWeights(coup_discount=1.0))
    _sync_board(full.board, obs)
    full.board.influence['Angola']['USSR'] = 1
    assert 0 < bot.coup(obs, 'Angola', 2) < full.coup(obs, 'Angola', 2)
    assert bot.realign(obs, 'Angola') == pytest.approx(0.9 * full.realign(obs, 'Angola'))


def test_opening_book_plays_the_standard_setup_and_the_handicap():
    from struggler.engine import Engine, Side
    engine = Engine.new_game(seed=9, setup_bonus=True)
    bot = StrategicPlayer()
    placed = []
    while engine.pending_decision.context.get('setup'):
        d = engine.pending_decision
        action = bot.choose_action(engine.observe(d.actor), [])
        placed.append((d.actor.value, action.payload['country']))
        engine.step(action)
    ussr = [c for s, c in placed if s == 'USSR']
    us = [c for s, c in placed if s == 'US']
    assert sorted(ussr) == sorted(['East_Germany'] + ['Poland'] * 4 + ['Austria'])
    assert us[:7].count('West_Germany') == 4 and us[:7].count('Italy') == 3
    assert us[7:] == ['Iran', 'West_Germany']
    assert engine.board.influence['Poland']['USSR'] == 4
    assert engine.board.influence['East_Germany']['USSR'] == 4
    assert engine.board.influence['West_Germany']['US'] == 5


def _opening_board():
    from struggler.engine import Engine
    engine = Engine.new_game(seed=4004, setup_bonus=True)
    bot = StrategicPlayer()
    while engine.pending_decision.context.get('setup'):
        d = engine.pending_decision
        engine.step(bot.choose_action(engine.observe(d.actor), []))
    return engine


def test_ops_are_priced_by_their_best_use_and_concavely():
    from struggler.engine import Side
    engine = _opening_board()
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    one, two, four = (bot.ops_value(obs, n) for n in (1, 2, 4))
    assert one > bot.weights.ops  # a real turn-1 play is worth more than the flat rate
    assert two > one and four > two
    assert four - two <= two  # the later points buy less than the first ones


def test_de_stalinization_is_simulated_and_beats_its_ops():
    from struggler.engine import Side
    engine = _opening_board()
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    event = bot.event_value(obs, 'De_Stalinization')
    assert event > bot.ops_value(obs, 3)
    # The value is board movement: points leave overprotected Europe for reach.
    assert event > 3 * bot.weights.ops * 0.8  # not the estimate


def test_space_slot_goes_to_the_worst_opponent_card():
    from struggler.engine import Side
    engine = _opening_board()
    engine.phase = 'action_rounds'
    engine.hands['US'] = ['Decolonization', 'Fidel', 'NATO', 'Truman_Doctrine']
    engine._push_action_round_play(Side.US)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    assert bot.space_card(obs) == 'Decolonization'
    assert bot.event_value(obs, 'Decolonization') < bot.event_value(obs, 'Fidel') < 0


def test_access_counts_only_newly_reachable_battlegrounds():
    from struggler.engine import Side
    engine = _opening_board()
    bot = StrategicPlayer()
    board = bot.board
    board.load_influence(engine.board.serialize())
    # Hungary borders Austria, Czechoslovakia, Romania, Yugoslavia: the USSR
    # already reaches all of Eastern Europe, so a point there opens nothing.
    assert bot._access(board, 'Hungary', Side.USSR) == 0
    # Venezuela opens South American battlegrounds the USSR reaches no other way.
    assert bot._access(board, 'Venezuela', Side.USSR) > 0
    # Once the USSR holds Brazil itself, Venezuela opens nothing more there.
    board.influence['Brazil']['USSR'] = 1
    assert bot._access(board, 'Venezuela', Side.USSR) == 0
