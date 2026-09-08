"""The cheap policy below the MCTS root: guards kept, plans served, rankings cached."""
from conftest import bare_engine
from struggler.bots.rollout import RolloutPolicy, information_key
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Action, DecisionKind as K, Side


def coup_position(us_in_nigeria=2):
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.defcon = 4
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


def test_immediate_guard_still_refuses_a_certain_loss():
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.defcon = 2
    engine.hands['USSR'] = ['Duck_and_Cover', 'Nasser']
    engine.space_race_attempts['USSR'] = 1  # no space escape this turn
    engine._push_action_round_play(Side.USSR)
    ranked = RolloutPolicy().rank_actions(engine.observe(Side.USSR))
    by_card = {a.payload['card']: key for key, a in ranked}
    assert by_card['Duck_and_Cover'][1] == -1.0  # firing it now ends the game
    assert by_card['Nasser'][1] == 0.0
    assert ranked[0][1].payload['card'] == 'Nasser'


def test_ops_plan_serves_the_same_coup_target_as_the_full_policy():
    reference = run_ops(coup_position(), StrategicPlayer())
    policy = RolloutPolicy()
    served = run_ops(coup_position(), policy)
    assert reference[0].payload['type'] == 'coup'
    assert served[:2] == reference[:2]
    assert (policy.misses, policy.served) == (1, 1)  # the target came from the plan
    # With influence preferred instead, the plan is simply not consulted.
    reference = run_ops(coup_position(1), StrategicPlayer())
    served = run_ops(coup_position(1), RolloutPolicy())
    assert reference[0].payload['type'] == 'influence'
    assert served[0] == reference[0]


def test_placement_plan_spends_every_op_legally_and_restores_the_board():
    engine = bare_engine()
    engine.phase = 'action_rounds'
    engine.board.influence['Italy']['US'] = 1
    engine._push_ops_type(Side.US, 4)
    policy = RolloutPolicy()
    obs = engine.observe(Side.US)
    influence = policy.rank_actions(obs)[0][1]
    engine.step(Action(K.OPS_TYPE, {'type': 'influence'}))
    before = {c: dict(v) for c, v in policy.board.influence.items()}
    placed = run_ops(engine, policy)
    assert policy.board.influence == before  # planning left no trace
    assert len(placed) == 4
    assert engine.pending_decision is None or engine.pending_decision.kind is not K.PLACE_INFLUENCE
    total = sum(engine.board.influence[c]['US'] for c in engine.board.countries)
    assert total == 1 + 4


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
