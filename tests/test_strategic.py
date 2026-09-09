"""Tactical regressions and the observation-only policy contract."""
import dataclasses

import pytest

from struggler.bots.strategic import CARDS, StrategicPlayer, StrategicWeights
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
    weights = [bot.scoring_weight(o, 'Iran') for o in (dead, live, held)]
    assert weights[0] < weights[1] < weights[2]  # scored < live < held
    from struggler.bots.greedy import _sync_board
    _sync_board(bot.board, live)
    deltas = [bot.delta(o, 'Iran', own=3) for o in (dead, live, held)]  # +3 takes control: the region score moves
    assert deltas[0] < deltas[1] < deltas[2]
    # A live Early War region scores this cycle and after the reshuffle; a
    # scored one only after the reshuffle; a Mid War region from turn 4.
    d = bot.weights.scoring_discount
    assert bot.scoring_weight(live, 'Iran') > 1 > bot.scoring_weight(dead, 'Iran')
    assert bot.scoring_weight(dataclasses.replace(live, turn=1), 'Brazil') == d ** 3
    assert bot.scoring_weight(dataclasses.replace(live, turn=5), 'Brazil') > 1
    # Southeast Asia Scoring reaches Thailand but not Japan, even with Asia Scoring dead.
    asia_dead = dataclasses.replace(live, turn=5, discard_pile=('Asia_Scoring',))
    assert bot.scoring_weight(asia_dead, 'Thailand') > bot.scoring_weight(asia_dead, 'Japan')
    # Battleground control is worth more where more scoring is still to come.
    bot.prepare(live)
    live_value = bot.delta(live, 'Iran', own=3)
    bot.prepare(dead)
    assert bot.delta(dead, 'Iran', own=3) < live_value


def test_mutation_can_be_restricted_to_named_weights():
    base = StrategicWeights()
    rng = random.Random(5)
    only = mutate(base, rng, ('scoring_discount', 'scoring_hand'))
    changed = {k for k, v in dataclasses.asdict(only).items() if v != getattr(base, k)}
    assert changed == {'scoring_discount', 'scoring_hand'}
    everything = mutate(base, rng)
    assert all(v != getattr(base, k) for k, v in dataclasses.asdict(everything).items())
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
