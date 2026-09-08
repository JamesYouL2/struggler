"""Public-information, event mechanics, and neural training regressions."""
import dataclasses
import random

import pytest

from struggler.bots.event_value import EventValuePlayer, TimingPrior, ValueNetwork
from struggler.bots.event_value.features import FEATURE_NAMES, card_state, encode, score
from struggler.bots.event_value.scenarios import event_score, expected_score
from struggler.bots.event_value.train import examples, metrics
from struggler.engine import Engine, Region, Side


def test_event_locations_and_scoring_timing():
    engine = Engine(seed=0)
    engine.turn = 4
    engine.hands['US'] = ['Nasser']
    obs = engine.observe(Side.US)
    prior = TimingPrior()
    assert card_state(obs, 'Nasser') == 'hand'
    assert prior.exposure(obs, 'Nasser', Region.MIDDLE_EAST) > 0
    scoring_in_hand = dataclasses.replace(obs, hand=obs.hand+('Middle_East_Scoring',))
    assert prior.exposure(scoring_in_hand, 'Nasser', Region.MIDDLE_EAST) < prior.exposure(obs, 'Nasser', Region.MIDDLE_EAST)
    for field in ('removed_cards', 'discard_pile'):
        hidden = dataclasses.replace(obs, hand=(), **{field: ('Nasser',)})
        assert prior.exposure(hidden, 'Nasser', Region.MIDDLE_EAST) == 0
    assert card_state(dataclasses.replace(obs, turn=1), 'Sadat_Expels_Soviets') == 'future'


@pytest.mark.parametrize('card,country,side', [
    ('Nasser', 'Egypt', Side.US), ('Sadat_Expels_Soviets', 'Egypt', Side.USSR),
    ('Fidel', 'Cuba', Side.US), ('Portuguese_Empire_Crumbles', 'Angola', Side.US),
])
def test_event_exposure_reduces_vulnerable_regions_value(card, country, side):
    engine = Engine(seed=0)
    engine.turn = 4
    engine.board.influence[country][side.value] = 3
    engine.hands[side.value] = [card]
    obs = engine.observe(side)
    region = engine.board.countries[country].region
    before = engine.serialize()
    live = expected_score(obs, region)
    removed = expected_score(dataclasses.replace(obs, hand=(), removed_cards=(card,)), region)
    assert live < removed
    assert engine.serialize() == before


def test_war_uses_exact_dice_and_neighbor_control():
    engine = Engine(seed=0)
    engine.board.influence['South_Korea']['US'] = 3
    obs = engine.observe(Side.USSR)
    before = score(engine.board, obs, Region.ASIA)
    # With no defending neighbors, Korea succeeds on 4,5,6.
    seized = Engine(seed=0)
    seized.board.influence['South_Korea']['USSR'] = 3
    after = score(seized.board, obs, Region.ASIA)
    assert event_score(obs, Region.ASIA, 'Korean_War') == pytest.approx((before+after)/2)
    for neighbor in engine.board.neighbors('South_Korea'):
        if neighbor in engine.board.countries:
            engine.board.influence[neighbor]['US'] = engine.board.countries[neighbor].stability
    protected = engine.observe(Side.USSR)
    gain = event_score(protected, Region.ASIA, 'Korean_War') - score(engine.board, protected, Region.ASIA)
    assert gain < (after-before)/2


def test_nasser_sadat_sequence_matches_both_engine_orders():
    engine = Engine(seed=0)
    engine.turn = 4
    engine.hands['US'] = ['Nasser', 'Sadat_Expels_Soviets']
    engine.board.influence['Egypt']['US'] = 4
    obs = engine.observe(Side.US)
    prior = TimingPrior(trigger_rate=1, unseen_horizon=1)
    outcomes = []
    for cards in (('Nasser','Sadat_Expels_Soviets'), ('Sadat_Expels_Soviets','Nasser')):
        copy = Engine.deserialize(engine.serialize())
        for card in cards:
            copy._fire_event(Side.US, card)
        outcomes.append(score(copy.board, obs, Region.MIDDLE_EAST))
    assert expected_score(obs, Region.MIDDLE_EAST, prior) == pytest.approx(sum(outcomes)/2)
    assert outcomes[0] != outcomes[1]


def test_network_training_checkpoint_and_schema(tmp_path):
    rows = examples(32, 41, TimingPrior())
    assert all(len(x) == len(FEATURE_NAMES) for x, _ in rows)
    # Reproducible, small supervised fit, checked against real teacher labels.
    model = ValueNetwork(hidden=8, seed=2)
    before = metrics(model, rows)['mse']
    rng = random.Random(2)
    for _ in range(30):
        model.fit_epoch(rows, rng=rng)
    assert metrics(model, rows)['mse'] < before
    path = tmp_path/'network.json'
    model.save(path)
    restored = ValueNetwork.load(path)
    assert [restored.predict(x) for x, _ in rows] == [model.predict(x) for x, _ in rows]
    import json
    data = json.loads(path.read_text())
    data['features'][0] = 'changed'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='schema'):
        ValueNetwork.load(path)


def test_neural_policy_keeps_defcon_guard_and_does_not_mutate_state():
    engine = Engine(seed=0)
    engine.defcon = 2
    engine.board.influence['Mexico']['USSR'] = 5
    engine._push_ops_type(Side.US, 3)
    obs = engine.observe(Side.US)
    before = engine.serialize()
    player = EventValuePlayer(ValueNetwork())
    action = player.choose_action(obs, [])
    assert action in obs.pending_decision.options
    assert action.payload['type'] != 'coup'
    assert engine.serialize() == before
    assert player.board.influence == obs.influence


def test_removed_events_have_exact_zero_neural_correction():
    from struggler.bots.event_value.features import EVENTS
    engine = Engine(seed=0)
    engine.removed_cards = list(EVENTS)
    obs = engine.observe(Side.US)
    model = ValueNetwork()
    model.bias = 10  # even arbitrary learned parameters cannot resurrect cards
    assert model.predict(encode(obs, engine.board, Region.MIDDLE_EAST)) == 0


def test_exclusively_hostile_exposure_cannot_be_learned_as_a_bonus():
    engine = Engine(seed=0)
    engine.turn = 4
    engine.hands['USSR'] = ['Sadat_Expels_Soviets']
    engine.removed_cards = ['Nasser']
    engine.board.influence['Egypt']['USSR'] = 3
    obs = engine.observe(Side.USSR)
    model = ValueNetwork()
    model.bias = 5
    assert model.predict(encode(obs, engine.board, Region.MIDDLE_EAST)) == 0
