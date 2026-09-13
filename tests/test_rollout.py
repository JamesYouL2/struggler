"""The cheap policy below the MCTS root: guards kept, plans served, rankings cached."""
from conftest import bare_engine
from struggler.bots.rollout import RolloutPolicy, information_key
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Action, DecisionKind as K, Side


def coup_position(us_in_nigeria=2):
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.defcon = 4
    engine.turn = 4  # Africa scores from the Mid War: the coup there is worth taking
    engine.board.influence['Angola']['USSR'] = 1
    engine.board.influence['Zaire']['USSR'] = 1
    engine.board.influence['Nigeria']['USSR'] = 1
    engine.board.influence['Nigeria']['US'] = us_in_nigeria
    engine._push_ops_type(Side.US, 3)
    return engine


def run_ops(engine, policy):
    """Play one Ops spend to completion with `policy`; return the actions taken."""
    taken = []
    while engine.pending_decision is not None and engine.pending_decision.kind in (
            K.OPS_TYPE, K.COUP_TARGET, K.REALIGNMENT_TARGET, K.PLACE_INFLUENCE):
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            action = d.options[0]
        else:
            action = policy.rank_actions(engine.observe(d.actor))[0][1]
        assert action in d.options
        taken.append(action)
        engine.step(action)
    return taken


def hazard_position(defcon):
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.defcon = defcon
    engine.hands['USSR'] = ['Duck_and_Cover', 'Nasser']
    engine.space_race_attempts['USSR'] = 1  # no space escape this turn
    engine._push_action_round_play(Side.USSR)
    return engine.observe(Side.USSR)


def risks(policy, obs):
    """Turn-loss risk per card. Read from `action_risk`, not from the ranking
    key: risk is priced into the score for card plays rather than carried as
    a separate element, so the key no longer exposes it."""
    ranked = policy.rank_actions(obs)
    return {a.payload['card']: policy.action_risk(obs, a)[1] for _, a in ranked}


def influence_position():
    """A board with a legal but unattractive coup target, so the Ops-type
    choice really is about which is worth more. `coup_position(1)` used to
    serve: it stopped once the influence branch was priced by the same greedy
    spend as `ops_value`, because the old best-single-country-times-Ops
    estimate had overpriced that spend by 58% (188 against 119)."""
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.defcon = 4
    engine.turn = 4
    engine.board.influence['Italy']['US'] = 1
    engine.board.influence['France']['USSR'] = 1  # stability 3: a poor coup
    engine._push_ops_type(Side.US, 4)
    return engine


def test_hazardous_hand_near_defcon_2_keeps_the_full_survival_search():
    obs = hazard_position(2)
    assert risks(RolloutPolicy(), obs) == risks(StrategicPlayer(), obs)
    assert risks(RolloutPolicy(), obs)['Duck_and_Cover'] == 1.0


def test_immediate_guard_ignores_later_rounds_when_defcon_is_high():
    obs = hazard_position(4)
    cheap = risks(RolloutPolicy(), obs)
    assert (cheap['Duck_and_Cover'], cheap['Nasser']) == (0.0, 0.0)
    # At DEFCON 3 the same hand is one opponent drop from a forced loss.
    obs = hazard_position(3)
    assert risks(RolloutPolicy(), obs) == risks(StrategicPlayer(), obs)


def test_ops_plan_serves_the_same_coup_target_as_the_full_policy():
    reference = run_ops(coup_position(), StrategicPlayer())
    policy = RolloutPolicy()
    served = run_ops(coup_position(), policy)
    assert reference[0].payload['type'] == 'coup'
    assert served[:2] == reference[:2]
    assert (policy.misses, policy.served) == (1, 1)  # the target came from the plan
    # With influence preferred instead, the plan is simply not consulted.
    reference = run_ops(influence_position(), StrategicPlayer())
    served = run_ops(influence_position(), RolloutPolicy())
    assert reference[0].payload['type'] == 'influence'
    assert served[0] == reference[0]


def test_placement_plan_spends_every_op_legally_and_restores_the_board():
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.board.influence['Italy']['US'] = 1
    engine._push_ops_type(Side.US, 4)
    policy = RolloutPolicy()
    obs = engine.observe(Side.US)
    policy.rank_actions(obs)  # primes the policy's board; the ranking itself is not asserted
    engine.step(Action(K.OPS_TYPE, {'type': 'influence'}))
    before = {c: dict(v) for c, v in policy.board.influence.items()}
    placed = run_ops(engine, policy)
    assert policy.board.influence == before  # planning left no trace
    assert len(placed) == 4
    assert engine.pending_decision is None or engine.pending_decision.kind is not K.PLACE_INFLUENCE
    total = sum(engine.board.influence[c]['US'] for c in engine.board.countries)
    assert total == 1 + 4


def test_the_placement_plan_keeps_the_snapshot_in_step(monkeypatch):
    """`_placement_plan` commits and rolls back points on `policy.board` while
    a ranking basis is active, so it is the one write site the `delta` fallback
    would not cover: outside a ranking `delta` re-reads the board, but the plan
    sets `_base_regions` itself. Under CHECK_SNAPSHOT every `delta` compares
    the snapshot with the board it is supposed to describe."""
    from struggler.bots import strategic
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.board.influence['Italy']['US'] = 1
    engine._push_ops_type(Side.US, 4)
    policy = RolloutPolicy()
    obs = engine.observe(Side.US)
    policy.rank_actions(obs)
    engine.step(Action(K.OPS_TYPE, {'type': 'influence'}))
    monkeypatch.setattr(strategic, 'CHECK_SNAPSHOT', True)
    placed = run_ops(engine, policy)
    assert len(placed) == 4
    assert policy._position.matches(policy.board)


def test_rankings_are_cached_per_information_key_until_reset():
    engine = coup_position()
    policy = RolloutPolicy()
    obs = engine.observe(Side.US)
    first = policy.rank_actions(obs)
    assert (policy.hits, policy.misses) == (0, 1)
    assert policy.rank_actions(engine.observe(Side.US)) is first
    assert (policy.hits, policy.misses) == (1, 1)
    policy.reset()
    policy.rank_actions(obs)
    assert (policy.hits, policy.misses) == (0, 1)


def test_information_key_ignores_decision_ids_but_not_hidden_counts():
    engine = coup_position()
    obs = engine.observe(Side.US)
    engine._next_decision_id += 5
    engine._decision_stack[-1] = engine._decision_stack[-1].__class__(
        **{**engine._decision_stack[-1].__dict__, 'id': 99})
    assert information_key(engine.observe(Side.US)) == information_key(obs)
    engine.draw_pile.append('Nasser')
    assert information_key(engine.observe(Side.US)) != information_key(obs)
