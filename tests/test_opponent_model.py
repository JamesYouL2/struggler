"""Learned opponent priors: public features, real labels, and planner wiring."""
import json
import random

import pytest

from conftest import bare_engine
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.bots.opponent_model import (
    FEATURE_NAMES, HEADS, Labeler, OpponentModel, collect_rows, encode, metrics,
)
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Side


def test_features_are_public_information_only():
    e = bare_engine()
    e.turn = 8  # Terrorism is a Late War card; before turn 8 it is 'future'
    e.hands['US'] = ['Fidel', 'Nasser']
    e.hands['USSR'] = ['Terrorism', 'Aldrich_Ames_Remix', 'Blockade']
    obs = e.observe(Side.US)
    x = encode(obs)
    assert len(x) == len(FEATURE_NAMES)
    # Swapping the opponent's hidden cards for others of the same count changes nothing.
    e.hands['USSR'] = ['Decolonization', 'Warsaw_Pact_Formed', 'COMECON']
    assert encode(e.observe(Side.US)) == x
    # What *is* public moves the features: the attack card seen in the discard.
    e.discard_pile.append('Terrorism')
    y = encode(e.observe(Side.US))
    assert y != x and y[FEATURE_NAMES.index('Terrorism:discard')] == 1
    assert x[FEATURE_NAMES.index('Terrorism:unseen')] == 1


def _obs(side=Side.USSR):
    e = bare_engine()
    e.turn = 4
    return e.observe(side)


def _labeler_with_pick(hand=('CIA_Created', 'Fidel', 'Nasser'), defcon=3):
    labeler = Labeler()
    labeler.observe_pick(Side.USSR, _obs(), list(hand), defcon)
    return labeler


def test_labels_count_only_opponent_removals_and_drops():
    hands = {'US': [], 'USSR': ['CIA_Created', 'Fidel', 'Nasser']}
    # Our own play removes Fidel: not an attack.
    labeler = _labeler_with_pick()
    hands['USSR'] = ['CIA_Created', 'Nasser']
    labeler.observe_step(Side.USSR, hands, 3, False, False)
    # The opponent's Aldrich Ames takes Nasser: an attack.
    hands['USSR'] = ['CIA_Created']
    labeler.observe_step(Side.US, hands, 3, False, False)
    labeler.observe_pick(Side.USSR, _obs(), hands['USSR'], 3)  # our next pick closes the row
    assert labeler.rows[0][1] == {'hand_attack': 1, 'defcon_drop': 0}

    # Grain Sales reveals then returns a card: gone mid-way, back by our next pick.
    labeler = _labeler_with_pick()
    hands['USSR'] = ['CIA_Created', 'Fidel']
    labeler.observe_step(Side.US, hands, 3, False, False)
    hands['USSR'] = ['CIA_Created', 'Fidel', 'Nasser']
    labeler.observe_step(Side.US, hands, 3, False, False)
    labeler.close(Side.USSR, hands['USSR'], 3)
    assert labeler.rows[0][1]['hand_attack'] == 1  # an intermediate removal still counts as exposure

    # Our own coup lowers DEFCON: not the opponent's drop; theirs afterwards is.
    labeler = _labeler_with_pick(defcon=4)
    labeler.observe_step(Side.USSR, hands, 3, False, False)
    labeler.observe_step(Side.US, hands, 3, False, False)
    labeler.close(Side.USSR, hands['USSR'], 3)
    assert labeler.rows[0][1]['defcon_drop'] == 0
    labeler = _labeler_with_pick(defcon=4)
    labeler.observe_step(Side.US, hands, 3, False, False)
    labeler.observe_step(Side.US, hands, 3, True, False)  # turn ends: row closes
    assert labeler.rows[0][1]['defcon_drop'] == 1 and not labeler.pending


def test_collect_rows_from_a_real_replay_log():
    with open('tests/replays/events.json') as f:
        log = json.load(f)
    rows = collect_rows(log)
    assert rows and all(len(x) == len(FEATURE_NAMES) for x, _ in rows)
    assert all(set(labels) == set(HEADS) and all(v in (0, 1) for v in labels.values()) for _, labels in rows)
    # Both sides pick cards, and a headline pick is a row too.
    assert any(x[FEATURE_NAMES.index('us')] == 1 for x, _ in rows)
    assert any(x[FEATURE_NAMES.index('headline')] == 1 for x, _ in rows)


def test_model_learns_a_separable_signal_and_round_trips(tmp_path):
    rng = random.Random(3)
    rows = []
    for _ in range(200):
        x = [rng.random() for _ in FEATURE_NAMES]
        seen = x[FEATURE_NAMES.index('Aldrich_Ames_Remix:unseen')] > 0.5
        rows.append((x, {'hand_attack': int(seen), 'defcon_drop': int(x[FEATURE_NAMES.index('defcon')] > 0.5)}))
    model = OpponentModel(hidden=6, seed=1)
    before = metrics(model, rows)
    fit_rng = random.Random(1)
    for _ in range(150):
        model.fit_epoch(rows, rng=fit_rng, rate=0.3)
    after = metrics(model, rows)
    for head in HEADS:
        assert after[head]['log_loss'] < before[head]['log_loss']
        assert after[head]['log_loss'] < after[head]['base_rate_log_loss']
    path = tmp_path/'opponent.json'
    model.save(path)
    restored = OpponentModel.load(path)
    assert [restored.predict(x) for x, _ in rows[:5]] == [model.predict(x) for x, _ in rows[:5]]
    data = json.loads(path.read_text())
    data['features'][0] = 'changed'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='schema'):
        OpponentModel.load(path)


class _Stub:
    def __init__(self, attack, drop):
        self.values = {'hand_attack': attack, 'defcon_drop': drop}

    def priors(self, obs):
        return dict(self.values)


def test_learned_priors_replace_the_flat_ones_in_the_planner():
    e = bare_engine()
    e.turn = 3
    e.phase = 'action_rounds'
    e.action_round = 5
    e.defcon = 2
    e.hands['USSR'] = ['CIA_Created', 'Fidel', 'Nasser']
    e.china_card_available = False  # otherwise it is a spare safe play
    e.board.influence['Cuba']['USSR'] = 2
    obs = e.observe(Side.USSR)
    bot = StrategicPlayer(survival_prior=SurvivalPrior(opponent_hand_attack=0.1))
    assert bot.planner_for(obs).risk() == pytest.approx(0.1)
    bot = StrategicPlayer(opponent_model=_Stub(attack=0.6, drop=0.2))
    planner = bot.planner_for(obs)
    assert planner.prior.opponent_hand_attack == 0.6 and planner.prior.opponent_lowers_defcon == 0.2
    assert planner.risk() == pytest.approx(0.6)
