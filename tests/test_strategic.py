"""Tactical regressions and the observation-only policy contract."""
import dataclasses

import pytest

from struggler.bots import evaluator as ev
from struggler.bots.strategic import (ASK, CARDS, TUNABLE_WEIGHTS, UNTUNED_WEIGHTS,
                                      StrategicPlayer, StrategicWeights)
from struggler.engine import Action, Decision, DecisionKind as K, Engine, Region, Side
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
    weights = [bot.scoring_weight(o, 'Iran') for o in (dead, live, held)]
    assert weights[0] < weights[1] < weights[2]  # scored < live < held
    from struggler.bots.greedy import _sync_board
    _sync_board(bot.board, live)
    deltas = [bot.delta(o, 'Iran', own=3) for o in (dead, live, held)]  # +3 takes control: the region score moves
    assert deltas[0] < deltas[1] < deltas[2]
    # A live Early War region scores this cycle and after the reshuffle; a
    # scored one only after the reshuffle; a Mid War region from turn 4. Every
    # region also has the end of the game to play for, at its measured odds,
    # so a scored region is not worth nothing.
    from struggler.bots.public_cards import final_scoring_odds
    d = bot.weights.scoring_discount
    live_iran, dead_iran = (bot.scoring_weight(o, 'Iran') for o in (live, dead))
    assert live_iran - dead_iran == pytest.approx(1.)  # the gap is exactly this cycle
    assert dead_iran > final_scoring_odds(dead)
    turn1 = dataclasses.replace(live, turn=1)
    assert bot.scoring_weight(turn1, 'Brazil') == pytest.approx(d ** 3 + final_scoring_odds(turn1))
    assert bot.scoring_weight(dataclasses.replace(live, turn=5), 'Brazil') > 1
    # Southeast Asia Scoring reaches Thailand but not Japan, even with Asia Scoring dead.
    asia_dead = dataclasses.replace(live, turn=5, discard_pile=('Asia_Scoring',))
    assert bot.scoring_weight(asia_dead, 'Thailand') > bot.scoring_weight(asia_dead, 'Japan')
    # Battleground control is worth more where more scoring is still to come.
    bot.prepare(live)
    live_value = bot.delta(live, 'Iran', own=3)
    bot.prepare(dead)
    assert bot.delta(dead, 'Iran', own=3) < live_value


def test_scoring_urgency_stops_at_the_end_of_the_game_and_counts_final_scoring():
    """The schedule used to promise scorings that never happen and to ignore
    the one that sometimes does. A reshuffle two turns away on turn 9 predicted
    a scoring on turn 11, and the end-of-game scoring of every region was
    missing entirely, so the weight came out flat at 1.800 on every turn.

    Final scoring is not certain either: most games end before it, on the 20 VP
    auto-victory, so it is priced at its measured odds rather than treated as
    a scheduled scoring."""
    from struggler.bots.public_cards import (FINAL_SCORING_ODDS, final_scoring_odds,
                                             scoring_schedule, turns_to_final_scoring)
    engine = Engine(seed=0)
    bot = StrategicPlayer()
    obs = engine.observe(Side.US)
    for turn in range(1, 11):
        now = dataclasses.replace(obs, turn=turn)
        horizon = turns_to_final_scoring(now)
        assert horizon == 10 - turn
        # Nothing is predicted for a turn the game cannot reach.
        for card in ('Middle_East_Scoring', 'Asia_Scoring', 'Africa_Scoring'):
            assert all(t <= horizon for t in scoring_schedule(now, card)), (turn, card)
        # The end-of-game scoring is worth its odds, so no country is worth
        # nothing while the game is live.
        assert bot.scoring_weight(now, 'Iran') >= final_scoring_odds(now)
    # BPA 2026 round 4: FS games 2, 3, 8, 10, 15, 19. Reconstruct the
    # conditional odds from the source rows, not a constraint on curve shape.
    ending_turns = (5, 10, 10, 9, 8, 8, 6, 10, 7, 10, 7, 4, 5, 5,
                    10, 8, 8, 1, 10, 5, 8, 4, 5, 9, 3, 4, 5)
    expected = tuple(6 / sum(end >= turn for end in ending_turns)
                     for turn in range(1, 11))
    assert FINAL_SCORING_ODDS == pytest.approx(expected)
    assert all(0 <= p <= 1 for p in FINAL_SCORING_ODDS)
    assert final_scoring_odds(dataclasses.replace(obs, turn=0)) == expected[0]
    assert final_scoring_odds(dataclasses.replace(obs, turn=11)) == expected[-1]
    # A region whose card is gone still has the end of the game to play for,
    # and nothing else.
    dead = dataclasses.replace(obs, turn=9, discard_pile=('Middle_East_Scoring',),
                               draw_pile_size=40)
    assert scoring_schedule(dead, 'Middle_East_Scoring') == ()  # no reshuffle in time
    assert bot.scoring_weight(dead, 'Iran') == pytest.approx(final_scoring_odds(dead))
    # Zeroing the weight restores the old shape, minus the phantom scorings.
    off = StrategicPlayer(StrategicWeights(scoring_final=0.0))
    assert off.scoring_weight(dead, 'Iran') == 0.0


def test_mutation_can_be_restricted_to_named_weights():
    base = StrategicWeights()
    rng = random.Random(5)
    only = mutate(base, rng, ('scoring_discount', 'scoring_hand'))
    changed = {k for k, v in dataclasses.asdict(only).items() if v != getattr(base, k)}
    assert changed == {'scoring_discount', 'scoring_hand'}
    everything = mutate(base, rng)
    changed_by_default = {k for k, v in dataclasses.asdict(everything).items()
                          if v != getattr(base, k)}
    assert changed_by_default == set(TUNABLE_WEIGHTS)
    with pytest.raises(ValueError, match='unknown weight'):
        mutate(base, rng, ('not_a_weight',))


def test_influence_value_is_linear_and_spare_points_are_not_a_flat_reserve():
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
    # Linear shape: the first point in stability-2 Iran is priced above
    # control's own term -- the option-value stand-in.
    empty, one, control = (value_at('Iran', n) for n in (0, 1, 2))
    assert one - empty > bot.weights.battleground
    # A flat reserve per spare point, until the wipe term replaces it.
    assert value_at('Angola', 2) - value_at('Angola', 1) == value_at('Pakistan', 3) - value_at('Pakistan', 2) > 0
    # Convex shape is still available as a knob: well under half of control
    # for a lone point.
    bot = StrategicPlayer(StrategicWeights(progress_curve=2.0))
    board = bot.board
    board.load_influence(engine.board.serialize())
    empty, one, control = (value_at('Iran', n) for n in (0, 1, 2))
    assert one - empty < 0.5 * (control - empty)

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
    # A battleground is worth its tier; a plain country nothing of its own
    # (reach is priced separately, and the region score carries domination).
    assert control_value('Thailand') > max(control_value('Malaysia'), control_value('Spain_Portugal'))
    # A plain country is a quarter to a third of a battleground.
    assert bot.importance(board.countries['Malaysia']) == bot.weights.control
    assert 0 < bot.weights.control < bot.weights.battleground / 2
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


def test_access_prices_reach_first_footholds_and_chains():
    from struggler.engine import Side
    engine = _opening_board()
    bot = StrategicPlayer()
    board = bot.board
    board.load_influence(engine.board.serialize())
    # Hungary borders no battleground and everything two steps away is
    # already reachable from Eastern Europe: a point there opens nothing.
    assert bot._access(board, 'Hungary', Side.USSR) == 0
    # Venezuela opens South American battlegrounds the USSR reaches no
    # other way, and Brazil is worth more than Colombia (stability 2 vs 1
    # cuts the other way, but Brazil's chain into Argentina/Chile adds).
    alone = bot._access(board, 'Venezuela', Side.USSR)
    assert alone > 0
    # Once the USSR holds Brazil itself, Venezuela's reach into Brazil is
    # redundant: worth less, not nothing (insurance, one more direction).
    board.influence['Brazil']['USSR'] = 1
    assert 0 < bot._access(board, 'Venezuela', Side.USSR) < alone
    # Reach scales with what the battleground is worth: Israel's one point
    # opens Egypt, and through it Libya; the same geometry in a region that
    # will not score for turns is worth less.
    obs = engine.observe(Side.US)
    bot.rank_actions(obs)
    israel = bot._access(bot.board, 'Israel', Side.US)
    assert israel > 0
    board.influence['Egypt']['US'] = 1
    assert bot._access(board, 'Israel', Side.US) < israel


def test_access_does_not_depend_on_an_earlier_trial_placement():
    """`_access` reads influence up to two hops out, so the `(board, cid, side)`
    memo it used to carry went stale as soon as a trial placement moved a
    neighbour: the same position then scored differently depending on what had
    been evaluated before it, which reordered 39 of the 598 corpus rankings."""
    from struggler.engine import Side
    engine = _opening_board()
    obs = engine.observe(Side.USSR)
    plain = StrategicPlayer()
    plain.rank_actions(obs)
    expected = plain._access(plain.board, 'Israel', Side.USSR)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    board = bot.board
    # Make and unmake a neighbouring placement, exactly as `_investment` does.
    original = dict(board.influence['Egypt'])
    board.influence['Egypt']['USSR'] += 2
    on_trial = bot._access(board, 'Israel', Side.USSR)
    board.influence['Egypt'].update(original)
    assert on_trial != expected  # the trial board really does price Israel differently
    assert bot._access(board, 'Israel', Side.USSR) == expected


def test_every_board_write_keeps_the_snapshot_in_step(monkeypatch):
    """The snapshot's control and reachability vectors are updated one country
    at a time, so any write to `board.influence` that skips `_set_influence`
    leaves them describing a board that no longer exists. Under
    CHECK_SNAPSHOT every `delta` inside a ranking rebuilds the snapshot from
    the board and compares it, which covers the placement search, the
    investment loop and the points `ops_value` commits and rolls back."""
    from struggler.bots import strategic
    engine = _opening_board()
    engine.phase = 'action_rounds'
    engine.hands['USSR'] = ['Nasser', 'Marshall_Plan', 'Truman_Doctrine']
    engine._push_action_round_play(Side.USSR)
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    monkeypatch.setattr(strategic, 'CHECK_SNAPSHOT', True)
    ranked = bot.rank_actions(obs)
    assert ranked and ranked[0][1] in obs.pending_decision.options
    assert bot._position.matches(bot.board)


def test_event_basis_reuse_matches_a_full_board_recomputation(monkeypatch):
    """Every whitelisted event at one decision starts from the same board, so
    the basis is computed once and only the affected countries re-valued. That
    set is not the countries the event moved: `country_value` reads access and
    reachability two hops out, so Nasser used to price at -67.83 where a full
    pass gives -65.89, the whole 1.94 being Israel, which the event never
    touched. Reuse must equal the full pass for every event, or a card is
    misranked against Ops."""
    from struggler.bots import strategic
    from struggler.bots.strategic import PUBLIC_EVENTS
    engine = Engine(seed=0)
    engine.board.influence['Egypt']['US'] = 2
    engine.board.influence['Israel']['US'] = 1
    engine.board.influence['Mexico']['US'] = 1
    engine.board.influence['Iran']['USSR'] = 2
    engine._maybe_push_place_influence(Side.US, 3)
    obs = engine.observe(Side.US)

    def priced(bot):
        bot.rank_actions(obs)
        out = {}
        for cid in sorted(PUBLIC_EVENTS):
            try:
                out[cid] = bot._public_event_value(obs, cid)
            except Exception:  # events this board cannot drive are priced elsewhere
                continue
        return out

    reused = priced(StrategicPlayer())
    assert sum(1 for v in reused.values() if v) > 20, 'the fixture should price real events'
    monkeypatch.setattr(strategic.StrategicPlayer, '_value_dependents',
                        lambda self, changed: set(self.board.countries))
    assert priced(StrategicPlayer()) == reused  # bitwise: these decide card choice


def _event_position():
    engine = _opening_board()
    engine.phase = 'action_rounds'
    engine.hands['USSR'] = ['Nasser', 'Marshall_Plan', 'Truman_Doctrine']
    engine._push_action_round_play(Side.USSR)
    return engine.observe(Side.USSR)


def test_a_broken_event_simulation_is_reported_not_silently_estimated(caplog, monkeypatch):
    """`event_value` used to catch every exception, log at debug and hand back
    the 0.8 x Ops estimate, so a defect read as a supported approximation. It
    hid one for as long as it existed: the two dice-contest events could never
    resolve, and the turn-1 table reported their estimate as a simulated
    value. Failures still fall back, so one bad event cannot end a game, but
    they say so."""
    import logging
    from struggler.bots import strategic
    obs = _event_position()
    bot = StrategicPlayer()
    bot.rank_actions(obs)

    def explode(self, obs, cid):
        raise TypeError('a defect, not an unsupported branch')

    monkeypatch.setattr(StrategicPlayer, '_public_event_value', explode)
    with caplog.at_level(logging.WARNING, logger='struggler.bots.strategic'):
        bot._events = {}
        value = bot.event_value(obs, 'Nasser')
    assert bot.sandbox_failures['Nasser'].startswith('TypeError')
    assert any('failed in the sandbox' in r.getMessage() for r in caplog.records)
    # An event the sandbox knowingly declines is not a defect and stays quiet.
    def decline(self, obs, cid):
        raise strategic.SandboxUnsupported('no public branch')

    monkeypatch.setattr(StrategicPlayer, '_public_event_value', decline)
    caplog.clear()
    quiet = StrategicPlayer()
    quiet.rank_actions(obs)
    with caplog.at_level(logging.WARNING, logger='struggler.bots.strategic'):
        declined = quiet.event_value(obs, 'Nasser')
    assert quiet.sandbox_failures['Nasser'] == 'unsupported'
    assert not caplog.records
    # Both fall back to the same estimate: the difference is what gets said,
    # not what gets returned, so a defect cannot end a game.
    assert value == declined


def test_the_sandbox_drives_every_event_it_claims_to():
    """`PUBLIC_EVENTS` is the set the sandbox is supposed to simulate, so a
    failure there is a defect and not an approximation. The two dice-contest
    events, Olympic Games and Summit, failed on every board for as long as the
    whitelist existed: a contest rolls both sides at once and carries two dice
    in its single CHANCE option, and the sandbox read exactly one key from it.
    Both then priced at the flat 0.8 x Ops estimate."""
    from struggler.bots.strategic import PUBLIC_EVENTS
    obs = _event_position()
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    for cid in sorted(PUBLIC_EVENTS):
        bot.event_value(obs, cid)
    assert bot.sandbox_failures == {}
    # And the two that used to fail are now worth something other than the
    # estimate they fell back to.
    for cid in ('Olympic_Games', 'Summit'):
        estimate = CARDS[cid].ops * bot.weights.ops * 0.8
        assert bot._public_event_value(obs, cid) != pytest.approx(estimate)


def test_the_event_helper_follows_a_weights_replacement():
    """Training mutates `bot.weights` on a live player. A helper left on the
    old weights would play the simulated event's choices by one value function
    while the result was scored by another."""
    bot = StrategicPlayer()
    first = bot._event_helper()
    assert first.weights is bot.weights
    bot.weights = StrategicWeights(battleground=9.0)
    second = bot._event_helper()
    assert second is not first
    assert second.weights is bot.weights and second.weights.battleground == 9.0


def test_un_intervention_is_kept_for_the_worst_opponent_card():
    from struggler.engine import Side
    engine = _opening_board()
    engine.phase = 'action_rounds'
    engine.hands['USSR'] = ['UN_Intervention', 'Marshall_Plan', 'Truman_Doctrine', 'Nasser']
    engine._push_action_round_play(Side.USSR)
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    assert bot.un_card(obs) == 'Marshall_Plan'
    ops = CARDS['Marshall_Plan'].ops
    event = bot.event_value(obs, 'Marshall_Plan')
    assert event < 0
    # Paired with UN Intervention the card's Ops come clean.
    assert bot.card_play_value(obs, 'Marshall_Plan', ops, event) == bot.ops_value(obs, ops)
    # Without UN Intervention in hand the event's harm counts.
    plain = StrategicPlayer()
    without = dataclasses.replace(obs, hand=tuple(c for c in obs.hand if c != 'UN_Intervention'))
    plain.rank_actions(without)
    assert plain.card_play_value(without, 'Marshall_Plan', ops, plain.event_value(without, 'Marshall_Plan')) < plain.ops_value(without, ops)



def test_ops_modifiers_are_priced_from_the_hands_they_touch():
    """Containment is the marginal Op on every other Ops card in the US hand;
    Red Scare from the US seat is the expected marginal Op lost over the
    USSR's hand, drawn from the unseen cards; both dwarf the old flat rate."""
    from struggler.engine import Side
    engine = _opening_board()
    engine.phase = 'action_rounds'
    engine.hands['US'] = ['Containment', 'Europe_Scoring', 'Duck_and_Cover', 'Truman_Doctrine', 'NATO', 'Nasser']
    engine._push_action_round_play(Side.US)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    ov = lambda n: bot.ops_value(obs, n)
    # Duck and Cover 3 -> 4, Truman 1 -> 2, Nasser 1 -> 2; NATO is 4 already, scoring is nothing.
    expected = (ov(4) - ov(3)) + 2 * (ov(2) - ov(1))
    assert abs(bot.event_value(obs, 'Containment') - expected) < 1e-6
    assert bot.event_value(obs, 'Containment') > ov(1)
    red = bot.event_value(obs, 'Red_Scare_Purge')
    assert red > 0 and red > ov(1)  # a whole hand at -1 each is worth more than an Op
    assert bot.event_value(obs, 'Brezhnev_Doctrine') < 0  # the USSR's hand grows


def test_first_mover_and_contested_reach():
    """Presence in a battleground the opponent could otherwise walk into
    earns tempo per stability; reach into a battleground the opponent can
    already place in is worth a fraction of exclusive reach."""
    from struggler.engine import Side
    engine = _opening_board()
    bot = StrategicPlayer()
    board = bot.board
    board.load_influence(engine.board.serialize())
    w = bot.weights
    # Egypt is empty; the US reaches it from Israel, the USSR does not.
    # A US point there is tempo the USSR cannot answer: no first-mover
    # bonus (nobody to move first against) but exclusive reach onward.
    board.influence['Egypt']['US'] = 1
    egypt = bot.country_value(board, 'Egypt', Side.US)
    board.influence['Egypt']['US'] = 0
    # Iraq: the USSR holds a point, the US reaches it from Iran: the USSR's
    # point carries the first-mover bonus, per stability (Iraq is 3).
    plain = StrategicPlayer(StrategicWeights(first_mover=0.0))
    plain.board.load_influence(engine.board.serialize())
    bonus = bot.country_value(board, 'Iraq', Side.USSR) - plain.country_value(plain.board, 'Iraq', Side.USSR)
    assert abs(bonus - w.first_mover * bot.importance(board.countries['Iraq']) / 3) < 1e-6
    # Poland: USSR-held, but the US cannot reach it, so no tempo to claim.
    assert bot.country_value(board, 'Poland', Side.USSR) == plain.country_value(plain.board, 'Poland', Side.USSR)
    # Contested reach: USSR reach into Egypt through Israel is a race the US
    # (already next door) can win, so it is worth access_contested of the
    # exclusive value the same geometry would have with no US in Israel.
    board.influence['Israel']['USSR'] = 1
    contested = bot._access(board, 'Israel', Side.USSR)
    board.influence['Israel']['US'] = 0
    exclusive = bot._access(board, 'Israel', Side.USSR)
    assert contested < exclusive
    assert egypt > 0


def _asia_scoring_engine(seed=4000, steps=160):
    """A mid-game engine with the USSR holding an Asian Battleground, so the
    scoring overrides have something to act on."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    for _ in range(steps):
        if engine.is_terminal:
            break
        d = engine.pending_decision
        engine.step(d.options[0])
    return engine


def test_the_bot_scores_asia_the_way_the_engine_will_under_shuttle_diplomacy():
    """The bot's region score is a second implementation of the engine's, and
    for a long time it was the one that did not know about the per-scoring
    overrides: with Shuttle Diplomacy in force it read Asia one tier off from
    what playing Asia Scoring would actually award."""
    from struggler.engine import Region

    engine = _asia_scoring_engine()
    assert engine.board.first_battleground_of(Side.USSR, Region.ASIA) is not None
    engine.game_effects['shuttle_diplomacy'] = True
    obs = engine.observe(Side.US)

    bot = StrategicPlayer(StrategicWeights())
    bot.prepare(obs)
    # Whichever of the two regions the bot spends the one-shot on, that is the
    # region the engine is asked to score, so the two must agree exactly.
    region = bot._shuttle_region()
    expected = engine._score_region_net(region)  # consumes the effect
    assert 'shuttle_diplomacy' not in engine.game_effects
    assert bot.region_score(bot.board, region, Side.US) == expected

    # And without it, the plain score -- which is what makes the effect worth
    # something to price at all.
    plain = Engine.deserialize(engine.serialize())
    assert plain._score_region_net(region) != expected


def test_shuttle_diplomacy_is_credited_to_one_region_not_both():
    """It drops a Battleground from a single scoring, so a whole-board value
    that booked it in the Middle East *and* Asia would count a one-shot twice
    -- and dropping a Battleground can cost a full tier, so the error is
    tiers, not rounding."""
    from struggler.engine import Region

    engine = _asia_scoring_engine()
    engine.game_effects['shuttle_diplomacy'] = True
    obs = engine.observe(Side.US)
    bot = StrategicPlayer(StrategicWeights())
    bot.prepare(obs)

    spent = bot._shuttle_region()
    assert spent in (Region.MIDDLE_EAST, Region.ASIA)
    other = Region.ASIA if spent is Region.MIDDLE_EAST else Region.MIDDLE_EAST
    pos = bot._position
    assert any(bot._overrides_for(spent, pos))
    assert bot._overrides_for(other, pos) == ev.NO_OVERRIDES


def test_nato_removes_a_wipe_risk_the_bot_priced_on_a_coup_the_rules_forbid():
    """`wipe_risk` gated on DEFCON alone, so it feared a USSR coup on
    US-Controlled Europe -- a move the engine rejects.

    The term ships at `wipe = 0` ("off until calibrated"), so this is not a
    live defect: it is the defect the calibration would have inherited.
    Calibrating a term that is systematically wrong across Europe would have
    fitted a weight to the wrong quantity, so the weights here are the ones
    that turn it on."""
    from struggler.engine import Region

    engine = Engine.new_game(seed=4000, setup_bonus=True)
    while engine.phase != 'headline' and not engine.is_terminal:
        engine.step(engine.pending_decision.options[0])
    board = engine.board
    for cid in board.countries_in(Region.EUROPE):
        board.influence[cid]['USSR'] = 0
        board.influence[cid]['US'] = board.countries[cid].stability
    engine.defcon = 5  # Europe is coupable at DEFCON 5 and nowhere below it

    assert StrategicWeights().wipe == 0, 'the term is live now; drop this scaffolding'
    bot = StrategicPlayer(StrategicWeights(wipe=1.0, wipe_backed=0.5))
    # France at 3 influence, stability 3: a 4-Ops coup wipes it on 3 rolls of
    # 12. West Germany cannot be wiped at all (stability 4 needs a 12), which
    # is why the term is silent there and this test is not about it.
    target = 'France'

    bot.prepare(engine.observe(Side.US))
    exposed = bot.country_value(bot.board, target, Side.US)
    assert engine._usable_coup_realign_target(Side.USSR, target)

    engine.game_effects['nato'] = True
    bot.prepare(engine.observe(Side.US))
    shielded = bot.country_value(bot.board, target, Side.US)
    assert not engine._usable_coup_realign_target(Side.USSR, target)
    assert shielded > exposed, (exposed, shielded)

    # De Gaulle lifts the shield on France alone, and the bot sees the risk
    # come back with it. Not back to `exposed`: NATO still shields the rest
    # of Europe, so what the USSR can still aim is spread over fewer targets.
    engine.game_effects['degaulle_france'] = True
    bot.prepare(engine.observe(Side.US))
    assert bot.country_value(bot.board, target, Side.US) < shielded
    assert engine._usable_coup_realign_target(Side.USSR, target)
    assert not engine._usable_coup_realign_target(Side.USSR, 'Italy')


def test_region_margin_incremental_matches_full_recompute():
    """delta() swaps one country's contribution into cached aggregates; it
    must equal a full pass over the region for every trial placement."""
    from struggler.engine import Side
    import itertools
    engine = _opening_board()
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    board = bot.board
    for cid, own, opp in itertools.product(('Iraq', 'Israel', 'Lebanon', 'Saudi_Arabia', 'Iran', 'France', 'Egypt', 'Thailand'), (0, 1, 2, 3), (0, 1)):
        original = dict(board.influence[cid])
        board.influence[cid]['USSR'] += own
        board.influence[cid]['US'] += opp
        region = board.countries[cid].region
        try:
            fast = bot.region_margin_after(board, region, Side.USSR, cid, original)
            full = bot.region_margin(board, region, Side.USSR)
            # Bitwise, not within a tolerance: a swapped aggregate that is
            # only close reorders near-ties against a freshly computed one,
            # and `_investment`'s strict `>` then picks a different point
            # count. The swap re-sums the per-member battleground fractions
            # in member order, which is exactly what the full walk does.
            assert fast == full, (cid, own, opp, fast, full)
        finally:
            board.influence[cid].update(original)


def test_sandbox_prices_a_die_event_at_its_expectation():
    """A war is worth the average over the six faces, not the middle roll."""
    from struggler.engine import Side
    from struggler.engine.core import Engine
    from struggler.engine import Action
    from dataclasses import replace
    engine = _opening_board()
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    expected = bot.event_value(obs, 'Arab_Israeli_War')
    # Force each face on a fresh sandbox and value the outcome.
    _, countries, regions, margins, before = bot._event_basis
    outcomes = []
    for face in range(1, 7):
        sandbox = bot.public_engine(obs)
        sandbox._fire_event(Side.US, 'Arab_Israeli_War')
        d = sandbox.pending_decision
        assert d.actor is Side.CHANCE and d.kind.name.endswith('_ROLL')
        (key,) = d.options[0].payload
        faces = tuple(Action(d.kind, {key: v}) for v in range(1, 7))
        sandbox._decision_stack[-1] = replace(d, options=faces)
        sandbox.step(faces[face - 1])
        outcomes.append(bot._resolve_sandbox(sandbox, obs, 'Arab_Israeli_War', countries, regions, margins,
                                             before, bot._event_helper(), rolls=9))
    assert min(outcomes) < expected < max(outcomes)
    assert abs(expected - sum(outcomes) / 6) < 1e-6


def _ask_not_ranking(asia_holder: Side):
    """Fire Ask Not for the US with Asia Scoring in hand, Asia lopsided in
    `asia_holder`'s favour, and rank the offered discards."""
    engine = Engine(seed=1)
    engine.events_enabled = True
    for cid in ('North_Korea', 'India', 'Pakistan', 'Thailand', 'Japan',
                'Taiwan', 'South_Korea', 'Afghanistan'):
        engine.board.influence[cid] = {'US': 0, 'USSR': 0}
        engine.board.influence[cid][asia_holder.value] = 9
    engine.draw_pile = ['Blockade', 'Defectors', 'Quagmire']
    engine.hands['US'] = ['Asia_Scoring', 'NATO']
    engine._fire_event(Side.US, 'Ask_Not_What_Your_Country_Can_Do_For_You')
    decision = engine.pending_decision
    assert decision.kind is K.EVENT_CHOICE
    offered = {a.payload['choice'] for a in decision.options}
    assert {'Asia_Scoring', 'stop'} <= offered
    ranked = StrategicPlayer().rank_actions(engine.observe(Side.US))
    return {a.payload['choice']: key for key, a in ranked}


def test_ask_not_dumps_a_scoring_card_that_would_score_against_it():
    """Discarding a scoring card is legal and is much of what Ask Not is for.
    With Asia in Soviet hands, the US would rather the card never scored."""
    keys = _ask_not_ranking(Side.USSR)
    assert keys['Asia_Scoring'] > keys['stop']


def test_ask_not_keeps_a_scoring_card_that_would_score_for_it():
    keys = _ask_not_ranking(Side.US)
    assert keys['Asia_Scoring'] < keys['stop']


def test_event_partition_names_are_real_cards():
    """`HIDDEN_INFO_EVENTS` and `OPS_MODIFIER_EVENTS` are subtractions from
    `PUBLIC_EVENTS`, so a misspelled id does not fail -- it silently leaves
    the card in the simulated set. `Our_Man_in_Tehran` (lowercase i) did
    exactly that: the sandbox simulated a draw-pile peek against an empty
    draw pile, returned 0.0, and recorded no failure."""
    from struggler.bots.strategic import HIDDEN_INFO_EVENTS, OPS_MODIFIER_EVENTS
    unknown = sorted(c for c in set(HIDDEN_INFO_EVENTS) | set(OPS_MODIFIER_EVENTS)
                     if c not in CARDS)
    assert unknown == []


def _midwar_us_engine():
    engine = Engine(seed=1)
    engine.events_enabled = True
    engine.turn = 6
    engine.phase = 'action_rounds'
    engine.action_round = 6
    engine._ars_played = 11
    return engine


def _event_value_for(engine, side, cid):
    engine.hands[side.value] = engine.hands[side.value] or ['Duck_and_Cover']
    engine._push_action_round_play(side)
    obs = engine.observe(side)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    return bot.event_value(obs, cid), bot.ops_value(obs, 1)


def test_five_year_plan_is_a_gift_when_the_ussr_hand_is_only_a_scoring_card_that_hurts():
    """The end-of-turn play: holding Five Year Plan and a scoring card that
    scores for the US, the USSR plays Five Year Plan and the random discard
    can only take the scoring card. Losing a card with negative hold value
    is a gain, and it falls out of `hold_value` rather than a special case."""
    engine = _midwar_us_engine()
    for cid in ('France', 'West_Germany', 'Italy', 'UK', 'Poland', 'East_Germany'):
        engine.board.influence[cid] = {'US': 9, 'USSR': 0}  # Europe scores heavily for the US
    engine.hands['USSR'] = ['Five_Year_Plan', 'Europe_Scoring']
    value, one_op = _event_value_for(engine, Side.USSR, 'Five_Year_Plan')
    assert value > one_op, 'dumping a scoring card that would score against you is worth more than an Op'

    # With a card worth holding instead, the same event is a loss.
    engine2 = _midwar_us_engine()
    engine2.hands['USSR'] = ['Five_Year_Plan', 'Decolonization']
    value2, _ = _event_value_for(engine2, Side.USSR, 'Five_Year_Plan')
    assert value2 < 0


def test_aldrich_ames_is_a_gift_when_the_us_holds_only_cards_it_wants_gone():
    engine = _midwar_us_engine()
    for cid in ('France', 'West_Germany', 'Italy', 'UK', 'Poland', 'East_Germany'):
        engine.board.influence[cid] = {'US': 0, 'USSR': 9}  # Europe scores heavily for the USSR
    engine.hands['US'] = ['Aldrich_Ames_Remix', 'Europe_Scoring']
    value, _ = _event_value_for(engine, Side.US, 'Aldrich_Ames_Remix')
    assert value > 0, 'the USSR must discard the one card, and it is the one the US wanted gone'


def test_hand_attack_values_are_seat_antisymmetric_in_sign():
    """Each term is a gain to the card's beneficiary, returned from our seat,
    so its sign flips with the seat for a card whose beneficiary is fixed."""
    from struggler.bots.strategic import HAND_ATTACK_EVENTS
    fixed = {'CIA_Created': 1, 'Lone_Gunman': -1, 'Grain_Sales_to_Soviets': 1,
             'Aldrich_Ames_Remix': -1, 'Five_Year_Plan': 1}
    for cid, us_sign in fixed.items():
        assert cid in HAND_ATTACK_EVENTS
        us, _ = _event_value_for(_midwar_us_engine(), Side.US, cid)
        ussr, _ = _event_value_for(_midwar_us_engine(), Side.USSR, cid)
        assert us * us_sign > 0, (cid, us)
        assert ussr * us_sign < 0, (cid, ussr)


def _play_mode_decision(cid, defcon, side, rest, action_round=6):
    """Step an engine to the PLAY_MODE decision for `cid`: the decision where
    the bot chooses Event over Ops, and the one the risk double-charge hit."""
    engine = Engine(seed=1)
    engine.events_enabled = True
    engine.turn, engine.phase, engine.action_round = 6, 'action_rounds', action_round
    engine._ars_played = 11
    engine.defcon = defcon
    engine.hands[side.value] = [cid, *rest]
    engine.hands[side.opponent.value] = ['NORAD']
    engine._push_action_round_play(side)
    engine.step(next(a for a in engine.pending_decision.options if a.payload.get('card') == cid))
    assert engine.pending_decision.kind is K.PLAY_MODE
    obs = engine.observe(side)
    bot = StrategicPlayer()
    ranked = bot.rank_actions(obs)
    keys = {a.payload['mode']: key for key, a in ranked}
    event = next(a for _, a in ranked if a.payload['mode'] == 'event')
    return bot, obs, keys, event


@pytest.mark.parametrize('cid, side, risk', [
    ('Summit', Side.USSR, 15 / 36),
    ('Missile_Envy', Side.USSR, 0.25),
    ('Five_Year_Plan', Side.US, 0.25),
])
def test_an_events_terminal_risk_is_charged_once_not_twice(cid, side, risk):
    """`event_value` already prices a firing event as
    `(1-r)*result - r*game_value`. `DefconPlanner.risk` returns
    `r + (1-r)*future` -- it *contains* that same `r` -- so charging it again
    in `safety_key` billed the same terminal chance twice.

    Where the rest of the hand is safe there is no residual at all
    (`risk == immediate`), so the priced key must be exactly the score. It
    used to be `(1-r)*score - r*game_value`: Summit at DEFCON 2 keyed at
    -974.51 against an honest -485.57, an implied loss chance of 0.79 where
    the dice give 0.4167 -- a worse price than losing the game outright.
    """
    bot, obs, keys, event = _play_mode_decision(cid, 2, side, ('Nasser',))
    immediate, total = bot.action_risk(obs, event)
    assert immediate == pytest.approx(risk, abs=1e-9), 'the fixture is meant to be the risky branch'
    assert total == pytest.approx(immediate, abs=1e-9), 'and to have no residual hand risk'
    assert keys['event'][2] == pytest.approx(bot.score(obs, event)), 'charged twice'
    # The bot must still prefer the safe Ops mode; pricing it once is not
    # pricing it away.
    assert keys['ops'][2] > keys['event'][2]


def test_a_simulated_ending_is_not_charged_again_by_event_value():
    """Summit was counted three times: `_resolve_sandbox` averages the losing
    dice branches at `game_value` already, and `event_value` then applied
    `event_risk` to that average, and `safety_key` applied the whole
    turn-loss risk on top. The sandbox owns the ending it simulated."""
    bot, obs, keys, event = _play_mode_decision('Summit', 2, Side.USSR, ('Nasser',))
    raw = bot._public_event_value(obs, 'Summit')
    assert bot._planner.event_risk('Summit') == pytest.approx(15 / 36)
    assert bot.event_value(obs, 'Summit') == pytest.approx(raw), 'sandbox ending charged twice'
    # It is a real cost -- most of a losing game's worth -- just not two of them.
    assert raw < 0
    assert -bot.game_value(obs) < raw

    # At DEFCON 3 the same event ends nothing and costs nothing.
    safe, safe_obs, _, _ = _play_mode_decision('Summit', 3, Side.USSR, ('Nasser',))
    assert safe._planner.event_risk('Summit') == 0
    assert safe.event_value(safe_obs, 'Summit') > raw


def _defcon_two_hand(side, dead=True):
    """A mid-war hand at DEFCON 2 holding, with `dead`, an opponent DEFCON
    reducer this side cannot play: its `event_value` is the certain-defeat
    sentinel, so every term that prices the hand has to meet one."""
    reducer = 'Duck_and_Cover' if side is Side.USSR else 'We_Will_Bury_You'
    benign = 'Marshall_Plan' if side is Side.USSR else 'De_Gaulle_Leads_France'
    engine = Engine(seed=1)
    engine.events_enabled = True
    engine.turn, engine.phase, engine.action_round = 6, 'action_rounds', 6
    engine._ars_played = 11
    engine.defcon = 2
    engine.board.influence['Iran'] = {'US': 2, 'USSR': 2}  # a live battleground coup target
    engine.hands[side.value] = ['NATO', reducer if dead else benign, 'Nasser']
    engine.hands[side.opponent.value] = ['Olympic_Games', 'Summit']
    engine._push_action_round_play(side)
    obs = engine.observe(side)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    return bot, obs, reducer


def test_the_certain_defeat_sentinel_never_leaves_a_value_term():
    """`LOSS` is an *ordering* sentinel, deliberately unreachable so that
    `safety_key` can test for it exactly. It is not a price, and no term that
    averages, mins or maxes card values may carry it out: the mean of a hand
    containing -1e6 is not a number, it is -333,216.

    This defect has now shipped three times -- through `ops_value` (a winning
    coup), `_resolve_sandbox` (one die face of an average), and `hold_value`
    (a card the side cannot play). So the invariant is swept over every card
    rather than pinned per-card: `event_value` returns either exactly `LOSS`
    or a real price bounded by what the game is worth, and nothing in
    between. `hold_value` is always a price -- it has no sentinel branch.
    """
    from struggler.bots.strategic import LOSS
    for side in (Side.USSR, Side.US):
        bot, obs, reducer = _defcon_two_hand(side)
        cap = bot.game_value(obs)
        assert bot.event_value(obs, reducer) == LOSS, 'the sentinel is still the sentinel'
        for cid, card in CARDS.items():
            if card.scoring:
                continue
            value = bot.event_value(obs, cid)
            assert value == LOSS or abs(value) <= cap, (side.value, cid, value, cap)
            assert abs(bot.hold_value(obs, cid, shallow=True)) <= cap, (side.value, cid)


def test_one_unplayable_card_does_not_make_ask_not_worth_the_whole_game():
    """`_hand_upgrade_value` re-derived `hold_value`'s body instead of
    calling it, so it never got that clamp. One card the US could not play
    made discarding it look like a gain of the sentinel, and Ask Not priced
    at +999,948 -- 742x the whole game, ahead of every real play on the
    board, including a winning one."""
    live, live_obs, _ = _defcon_two_hand(Side.US, dead=False)
    dead, dead_obs, _ = _defcon_two_hand(Side.US, dead=True)
    cap = dead.game_value(dead_obs)
    with_dead = dead.event_value(dead_obs, ASK)
    without = live.event_value(live_obs, ASK)
    assert with_dead > without, 'a card you cannot play is exactly what Ask Not is for'
    assert with_dead <= cap, (with_dead, cap)
    # The upgrade is worth something, not everything: one dead card cannot
    # be worth more than the game it is one card of.
    assert with_dead - without < cap, (with_dead, without, cap)


def test_grain_sales_is_worth_at_least_its_two_ops_to_the_us():
    engine = _midwar_us_engine()
    value, _ = _event_value_for(engine, Side.US, 'Grain_Sales_to_Soviets')
    obs = engine.observe(Side.US)
    bot = StrategicPlayer(); bot.rank_actions(obs)
    assert value >= bot.ops_value(obs, 2) * (1 - bot._planner.event_risk('Grain_Sales_to_Soviets')) - 1e-9


def _event_choice_keys(engine, side):
    obs = engine.observe(side)
    bot = StrategicPlayer()
    return {a.payload['choice']: key for key, a in bot.rank_actions(obs)}


def test_grain_sales_returns_a_soviet_event_and_takes_a_us_one():
    """The shown card is played in full by the US, so a Soviet event's harm
    is in its hold value and it goes back for the 2 Ops; a US card is taken.
    Both choices scored 0 before, and "take" won by option order."""
    from struggler.engine import Action, DecisionKind as K
    engine = _midwar_us_engine()
    engine.defcon = 2
    engine.hands['USSR'] = ['We_Will_Bury_You']  # its DEFCON drop is nuclear war, on the US's action
    engine.hands['US'] = ['Duck_and_Cover']
    engine._fire_event(Side.US, 'Grain_Sales_to_Soviets')
    engine.step(engine.pending_decision.options[0])  # the CHANCE reveal
    assert engine.pending_decision.context['event'] == 'Grain_Sales_to_Soviets'
    keys = _event_choice_keys(engine, Side.US)
    assert keys['return'] > keys['take'], 'We Will Bury You would fire against the US at DEFCON 2'

    engine = _midwar_us_engine()
    engine.hands['USSR'] = ['Marshall_Plan']
    engine.hands['US'] = ['Duck_and_Cover']
    engine._fire_event(Side.US, 'Grain_Sales_to_Soviets')
    engine.step(engine.pending_decision.options[0])
    keys = _event_choice_keys(engine, Side.US)
    assert keys['take'] > keys['return'], 'a 4-Op US event, and the USSR loses it'


def test_star_wars_takes_the_best_event_in_the_pile_not_the_weakest():
    """The generic card-choice rule scored a card at minus its Ops, so Star
    Wars fetched the weakest card in the discard pile. It is the strongest
    US or neutral event, or none if only Soviet events are there."""
    engine = _midwar_us_engine()
    engine.space_race = {'US': 3, 'USSR': 1}
    engine.discard_pile = ['Truman_Doctrine', 'Marshall_Plan', 'De_Gaulle_Leads_France']
    engine.board.influence['France'] = {'US': 0, 'USSR': 2}
    engine.hands['US'] = ['Duck_and_Cover']
    engine._fire_event(Side.US, 'Star_Wars')
    keys = _event_choice_keys(engine, Side.US)
    assert keys['Marshall_Plan'] > keys['Truman_Doctrine']
    assert keys['none'] > keys['De_Gaulle_Leads_France'], 'a Soviet event is worse than nothing'


def _lone_gunman_at_defcon_two():
    """The US plays Lone Gunman at DEFCON 2: the USSR gets 1 Op, and the US
    is the phasing player, so a USSR Battleground coup ends the game with the
    US losing (FAQ, card #62)."""
    engine = Engine.new_game(seed=4, events=True)
    engine.turn, engine.phase, engine.action_round = 7, 'action_rounds', 3
    engine._ars_played = 5
    engine.defcon = 2
    engine.board.influence['Iran'] = {'US': 4, 'USSR': 1}
    engine.hands['US'] = ['Lone_Gunman']
    engine.hands['USSR'] = ['Duck_and_Cover', 'Nasser']
    engine._phasing_player = Side.US
    engine._fire_event(Side.US, 'Lone_Gunman')
    return engine


def test_takes_the_winning_coup_when_the_opponent_is_the_phasing_player():
    """Nuclear war costs the *phasing* player the game, whoever spends the
    Ops. `score` knew that; `coup_survival_risk` returned maximum risk for
    any coup reaching DEFCON 1 regardless of seat, and risk outranks score,
    so the key vetoed the win -- the bot took 26 points of Influence over
    winning the game."""
    engine = _lone_gunman_at_defcon_two()
    assert engine.pending_decision.kind is K.OPS_TYPE
    assert engine.pending_decision.context['phasing_player'] == 'US'
    ranked = StrategicPlayer().rank_actions(engine.observe(Side.USSR))
    assert ranked[0][1].payload['type'] == 'coup'

    engine.step(ranked[0][1])
    target = StrategicPlayer().rank_actions(engine.observe(Side.USSR))[0][1]
    assert engine.board.countries[target.payload['country']].battleground


def test_still_refuses_the_suicide_coup_on_its_own_action_round():
    """The mirror: same board, our own Action Round, and the coup loses."""
    engine = _lone_gunman_at_defcon_two()
    engine._decision_stack.clear()
    engine._phasing_player = Side.USSR
    engine.begin_coup(Side.USSR, 3)
    ranked = StrategicPlayer().rank_actions(engine.observe(Side.USSR))
    assert engine.pending_decision.context['phasing_player'] == 'USSR'
    for key, action in ranked:
        if engine.board.countries[action.payload['country']].battleground:
            assert key[0] == -1, 'a battleground coup at DEFCON 2 is our own defeat'
            break
    else:
        raise AssertionError('no battleground target offered')


def test_hand_attack_values_do_not_depend_on_legal_option_order():
    """The hand terms are mutually recursive -- Ask Not prices the hand, which
    holds Aldrich Ames, which prices the hand, which holds Ask Not. The cycle
    breaker cached whichever card was reached first at its full value and the
    other at the estimate, so reversing the legal options moved Ask Not by 170
    raw units. Hand terms now take a deterministic shallow value for any card
    that could recurse."""
    engine = Engine.new_game(seed=3003, events=True)
    engine.turn, engine.phase, engine.action_round = 6, 'action_rounds', 3
    engine._ars_played, engine.defcon = 5, 5
    engine.hands['US'] = [ASK, 'Aldrich_Ames_Remix', 'Marshall_Plan', 'Decolonization']
    engine._push_action_round_play(Side.US)
    obs = engine.observe(Side.US)
    decision = obs.pending_decision

    forward = StrategicPlayer(); forward.rank_actions(obs)
    for permuted in (tuple(reversed(decision.options)),
                     decision.options[1:] + decision.options[:1]):
        other = StrategicPlayer()
        other.rank_actions(dataclasses.replace(
            obs, pending_decision=dataclasses.replace(decision, options=permuted)))
        for cid in obs.hand:
            assert forward.event_value(obs, cid) == other.event_value(obs, cid), cid


def test_evaluate_restores_the_whole_prepared_context_not_just_the_caches():
    """`prepare` rewrites `_scoring_flags` and `_coup_bans` from the
    observation's game_effects. `evaluate` restored the observation, urgency,
    caches and influence but not those, so a leaf evaluated under Formosan
    Resolution left the caller scoring Taiwan as a Battleground."""
    engine = Engine(seed=1)
    engine.board.influence['Taiwan']['US'] = 3
    engine._maybe_push_place_influence(Side.US, 1)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    before_flags, before_bans = bot._scoring_flags, bot._coup_bans
    before_value = bot.value(bot.board, Side.US)

    bot.evaluate(dataclasses.replace(obs, game_effects={'formosan_resolution': True,
                                                       'nato': True, 'marshall_plan': True}))
    assert bot._scoring_flags == before_flags
    assert bot._coup_bans == before_bans
    assert bot.value(bot.board, Side.US) == before_value


def _star_wars_engine(us_ahead: bool):
    engine = Engine.new_game(seed=9, events=True)
    engine.turn, engine.phase, engine.action_round = 8, 'action_rounds', 2
    engine._ars_played = 3
    engine.space_race = {'US': 4 if us_ahead else 1, 'USSR': 1}
    engine.discard_pile = ['Marshall_Plan', 'Truman_Doctrine']
    engine.board.influence['France'] = {'US': 0, 'USSR': 2}
    engine.hands['US'] = ['Duck_and_Cover']
    engine.hands['USSR'] = ['Fidel']
    return engine


def _value_from(engine, side, cid):
    engine._decision_stack.clear()
    engine._push_action_round_play(side)
    obs = engine.observe(side)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    return bot.event_value(obs, cid)


def test_star_wars_costs_the_ussr_what_it_gains_the_us():
    """The US chooses the retrieved event whoever played the card, so the
    maximum is taken over the *US's* gain. Maximising our own seat's value and
    clamping at zero priced Star Wars at nothing for the USSR, while the
    Marshall Plan it fetches lands either way."""
    engine = _star_wars_engine(us_ahead=True)
    us = _value_from(engine, Side.US, 'Star_Wars')
    ussr = _value_from(engine, Side.USSR, 'Star_Wars')
    assert us > 0 and ussr < 0, (us, ussr)


def test_hand_events_that_cannot_occur_are_worth_nothing():
    """These terms read the hand and the deck rather than the sandbox, so they
    skipped the engine's own prerequisite check."""
    from struggler.engine.events import EVENTS
    engine = _star_wars_engine(us_ahead=False)  # neither side leads the Space Race
    for cid, info in engine.board.countries.items():
        if info.region is Region.MIDDLE_EAST:
            engine.board.influence[cid] = {'US': 0, 'USSR': 0}
    for cid in ('Star_Wars', 'Our_Man_In_Tehran'):
        assert not EVENTS[cid].eligible(engine, Side.US), cid
        assert _value_from(engine, Side.US, cid) == 0.0, cid


@pytest.mark.parametrize('event,ops,countries,allow_realign', [
    ('Tear_Down_This_Wall', 3, ['Angola', 'South_Africa', 'Zaire'], True),
    ('Junta', 2, ['Cuba', 'Nicaragua', 'Panama'], True),
    ('Ortega_Elected_in_Nicaragua', 2, ['Cuba', 'Honduras', 'Costa_Rica'], False),
])
def test_a_free_coup_offer_is_priced_rather_than_declined_by_tuple_order(
        event, ops, countries, allow_realign):
    """Every branch of these three used to score 0.0 and fall through to the
    bare `return 0.0`. `sorted` is stable and the engine offers "none" first,
    so the bot declined the free Coup that is the whole point of the card,
    every time -- and symmetrically, so no gate could ever see it."""
    engine = Engine(seed=1)
    for cid in countries:
        engine.board.influence[cid][Side.USSR.value] = 2
    engine.push_free_coup_or_realign(Side.US, event, ops=ops, countries=countries,
                                     allow_realign=allow_realign)
    decision = engine.pending_decision
    assert decision.kind is K.EVENT_CHOICE

    bot = StrategicPlayer()
    obs = engine.observe(Side.US)
    ranked = bot.rank_actions(obs)
    scores = {a.payload['choice']: k[-1] for k, a in ranked}

    assert len(set(scores.values())) > 1, f'{event}: every branch still ties at {scores}'
    assert scores['coup'] > scores['none'], f'{event}: a free Coup on enemy influence should beat doing nothing'
    assert bot.choose_action(obs, []).payload['choice'] == 'coup'
    if allow_realign:
        assert 'realign' in scores


def test_a_free_coup_that_would_end_the_game_is_still_declined():
    """`none` stays the do-nothing baseline at 0, so a branch priced at the
    certain-defeat sentinel loses to it rather than being taken."""
    engine = Engine(seed=1)
    engine.defcon = 2
    engine.board.influence['Angola'][Side.USSR.value] = 2
    assert engine.board.countries['Angola'].battleground
    engine.push_free_coup_or_realign(Side.US, 'Tear_Down_This_Wall', ops=3,
                                     countries=['Angola'], allow_realign=False)
    bot = StrategicPlayer()
    obs = engine.observe(Side.US)
    assert bot.choose_action(obs, []).payload['choice'] == 'none'


def test_a_free_coup_earns_no_military_operations_credit():
    """The two ways a free Coup differs from an ordinary one are that it
    ignores DEFCON geography and does not advance the Military Operations
    track (Engine.resolve_free_op_choice). Only the second is a value."""
    engine = Engine(seed=1)
    engine.board.influence['Angola'][Side.USSR.value] = 2
    engine._maybe_push_place_influence(Side.US, 1)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)  # coup() is only ever called inside a ranking
    assert obs.military_ops.get(Side.US.value, 0) < obs.defcon, 'need a requirement deficit'
    assert bot.coup(obs, 'Angola', 3, military=False) < bot.coup(obs, 'Angola', 3)


def test_military_operations_are_priced_in_vp_not_a_flat_weight():
    """Rule 6.3.5 is exact: a side below the DEFCON level at the end of the
    turn hands the difference to its opponent as VP, so one Op of deficit
    closed is worth exactly one VP. The old flat weight of 2.0 raw priced it
    at a few percent of that, next to a VP worth ~14 raw on turn 1."""
    engine = Engine(seed=1)
    engine.board.influence['Angola'][Side.USSR.value] = 2
    engine._maybe_push_place_influence(Side.US, 1)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)  # coup() is only ever called inside a ranking

    deficit = obs.defcon - obs.military_ops.get(Side.US.value, 0)
    assert deficit > 0, 'the fixture needs an open requirement'
    credit = bot.coup(obs, 'Angola', 3) - bot.coup(obs, 'Angola', 3, military=False)

    rounds = bot._rounds_left(obs)
    expected = bot.weights.military * min(3, deficit) * bot.vp_value(obs) / rounds
    assert credit == pytest.approx(expected)
    # Spread over the rounds still to play: a full VP an Op overshot the
    # expert fixture badly on turn 1 (Korean War by 1.07 Ops), because a
    # later card would very likely have covered the requirement anyway.
    assert rounds > 1, 'the fixture should have rounds left, so the credit is discounted'
    assert 0 < credit < bot.weights.military * min(3, deficit) * bot.vp_value(obs)


def test_meeting_the_requirement_removes_the_military_credit():
    """Once Military Ops reach the DEFCON level there is nothing left to buy,
    so the credit disappears rather than paying for every further coup."""
    engine = Engine(seed=1)
    engine.board.influence['Angola'][Side.USSR.value] = 2
    engine.military_ops[Side.US.value] = engine.defcon
    engine._maybe_push_place_influence(Side.US, 1)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)  # coup() is only ever called inside a ranking
    assert bot.coup(obs, 'Angola', 3) == pytest.approx(bot.coup(obs, 'Angola', 3, military=False))


def test_training_does_not_switch_on_a_deliberately_disabled_weight():
    """`mutate` steps a zero weight with `abs(gauss)`, because a
    multiplicative step would make zero absorbing. That means any
    deliberately-disabled term left in the default field set gets switched
    *on*: a default run moved `wipe` from 0.0 to 0.27, so every training run
    to date searched a space that enables an uncalibrated term -- and with
    `wipe` non-zero the evaluator's dependency radius widens to the whole
    board, so those runs were slower than they looked too."""
    base = StrategicWeights()
    for seed in range(20):
        got = mutate(base, random.Random(seed))
        for name in UNTUNED_WEIGHTS:
            assert getattr(got, name) == getattr(base, name), name
    # Naming one explicitly is how a deliberate ablation turns it on.
    assert mutate(base, random.Random(1), ('wipe',)).wipe > 0
    assert set(TUNABLE_WEIGHTS).isdisjoint(UNTUNED_WEIGHTS)
    assert set(TUNABLE_WEIGHTS) | set(UNTUNED_WEIGHTS) == {
        f.name for f in dataclasses.fields(StrategicWeights)}
