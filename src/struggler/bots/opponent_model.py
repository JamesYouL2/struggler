"""Learned opponent priors for the DEFCON survival planner.

`DefconPlanner` needs two probabilities between our card plays: that the
opponent removes a card from our hand (Aldrich Ames, Terrorism, Grain Sales,
Missile Envy) and that the opponent lowers DEFCON. `SurvivalPrior` carries
flat defaults; this module replaces them with a small network fitted to what
actually happened in recorded games.

Labels are real, not invented: replaying a game log, each of our headline or
action-round card picks becomes a row, and the label is whether a card we
held then was gone from our hand at our next pick (removals made by our own
decisions do not count) and whether DEFCON fell on an opponent-attributed
step in between. Features use only `Observation` -- public information.

Train from the checked-in game logs:

    python -m struggler.bots.opponent_model --logs 'logs/game-check/*.json' \\
        --output models/opponent-model-v1.json

Use it: STRUGGLER_OPPONENT_MODEL=models/opponent-model-v1.json for the
`strategic` and `event-value` players.

A model describes the opponents in its logs. Bot-vs-bot games rarely event
Grain Sales, Aldrich Ames, or Terrorism; strong humans always event the
first two and Terrorism when behind or with Iranian Hostage Crisis, so a
checkpoint fitted to bot logs under-predicts hand attacks against humans.
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path

from struggler.engine import DecisionKind as K, Observation, Period, Side
from struggler.engine.cards import action_rounds, load_cards
from struggler.engine.core import SANDBOX_LOG
from struggler.engine.replay import decode_action, make_engine

CARDS = load_cards()
ATTACK_CARDS = ('Aldrich_Ames_Remix', 'Terrorism', 'Grain_Sales_to_Soviets', 'Missile_Envy')
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')
ENTRY_TURN = {Period.EARLY_WAR: 1, Period.MID_WAR: 4, Period.LATE_WAR: 8}
TRAP_KEYS = {'bear_trap': Side.USSR, 'quagmire': Side.US}
PICK_KINDS = (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY)
HEADS = ('hand_attack', 'defcon_drop')


def card_state(obs: Observation, card: str) -> str:
    if card in obs.removed_cards:
        return 'removed'
    if card in obs.hand:
        return 'hand'
    if card in obs.discard_pile:
        return 'discard'
    if obs.turn < ENTRY_TURN[CARDS[card].period]:
        return 'future'
    return 'unseen'


def rounds_left(obs: Observation) -> int:
    return max(0, action_rounds(obs.turn) - max(1, obs.action_round) + 1)


def feature_names() -> tuple[str, ...]:
    names = ['us', 'headline', 'turn', 'round', 'rounds_left', 'defcon', 'vp', 'hand',
             'opponent_hand', 'draw', 'unseen_share', 'opponent_military_deficit',
             'own_military_deficit', 'iranian_hostage', 'opponent_trapped', 'opponent_red_scared']
    for card in ATTACK_CARDS:
        names += [f'{card}:{s}' for s in STATES] + [f'{card}:unseen_share']
    return tuple(names)


FEATURE_NAMES = feature_names()


def encode(obs: Observation) -> list[float]:
    """Public-information features; the order is part of the checkpoint format."""
    side, opp = obs.side, obs.side.opponent
    unseen = obs.opponent_hand_size / max(1, obs.opponent_hand_size + obs.draw_pile_size)
    x = [float(side is Side.US), float(obs.phase == 'headline'), obs.turn/10, obs.action_round/8,
         rounds_left(obs)/8, obs.defcon/5, obs.vp*(1 if side is Side.US else -1)/20,
         len(obs.hand)/10, obs.opponent_hand_size/10, obs.draw_pile_size/60, unseen,
         max(0, obs.defcon-obs.military_ops.get(opp.value, 0))/5,
         max(0, obs.defcon-obs.military_ops.get(side.value, 0))/5,
         float(bool(obs.game_effects.get('iranian_hostage'))),
         float(any(obs.game_effects.get(k) and s is opp for k, s in TRAP_KEYS.items())),
         float(obs.turn_effects.get('red_scare') == opp.value)]
    for card in ATTACK_CARDS:
        state = card_state(obs, card)
        x += [float(state == s) for s in STATES]
        x.append(unseen if state == 'unseen' else 0.0)
    return x


# -- labels from recorded games ---------------------------------------------


@dataclass
class _Pending:
    features: list[float]
    expected: set[str]      # cards we held; our own decisions prune this
    defcon: int
    attacked: bool = False  # an opponent-attributed step removed one of them
    dropped: bool = False   # an opponent-attributed step lowered DEFCON


class Labeler:
    """Turn a stream of engine steps into (features, labels) rows per side.

    Pure bookkeeping over what `observe_pick` / `observe_step` are told, so
    it is testable without a game: `observe_pick` when a side is about to
    pick its headline or action-round card, `observe_step` after every
    engine step with the side responsible for it and both hands.
    """

    def __init__(self):
        self.pending: dict[Side, _Pending] = {}
        self.rows: list[tuple[list[float], dict[str, int]]] = []

    def observe_pick(self, side: Side, obs: Observation, hand, defcon: int) -> None:
        self.close(side, hand, defcon)
        self.pending[side] = _Pending(encode(obs), set(hand), defcon)

    def observe_step(self, responsible: Side | None, hands_after, defcon_after: int,
                     turn_changed: bool, terminal: bool) -> None:
        for side, pending in list(self.pending.items()):
            hand = set(hands_after[side.value])
            if responsible is side:
                pending.expected &= hand  # our own play, space, discard, payment
            else:
                if pending.expected - hand:
                    pending.attacked = True
                if defcon_after < pending.defcon:
                    pending.dropped = True
            pending.defcon = defcon_after  # our own coup is not the opponent's drop
            if turn_changed or terminal:
                self.close(side, hands_after[side.value], defcon_after)

    def close(self, side: Side, hand, defcon: int) -> None:
        pending = self.pending.pop(side, None)
        if pending is None:
            return
        attacked = pending.attacked or bool(pending.expected - set(hand))
        self.rows.append((pending.features, {'hand_attack': int(attacked), 'defcon_drop': int(pending.dropped)}))


def collect_rows(log: dict) -> list[tuple[list[float], dict[str, int]]]:
    """Replay one game log and label every headline/action-round pick in it."""
    engine = make_engine(log)
    engine.log = SANDBOX_LOG  # a replay is not a live game
    labeler = Labeler()
    last_responsible = None
    for action_data in log['actions']:
        decision = engine.pending_decision
        if decision is None:
            break
        if decision.kind in PICK_KINDS and decision.actor in (Side.US, Side.USSR):
            side = decision.actor
            labeler.observe_pick(side, engine.observe(side), engine.hands[side.value], engine.defcon)
        responsible = decision.context.get('phasing_player')
        responsible = (Side(responsible) if responsible else
                       decision.actor if decision.actor is not Side.CHANCE else last_responsible)
        last_responsible = responsible
        turn = engine.turn
        engine.step(decode_action(action_data))
        labeler.observe_step(responsible, engine.hands, engine.defcon, engine.turn != turn, engine.is_terminal)
    for side in list(labeler.pending):
        labeler.close(side, engine.hands[side.value], engine.defcon)
    return labeler.rows


# -- model --------------------------------------------------------------------


def _sigmoid(v: float) -> float:
    return 1/(1+math.exp(-max(-30, min(30, v))))


class OpponentModel:
    """One tanh hidden layer, two sigmoid heads, no third-party dependencies."""

    def __init__(self, hidden: int = 8, seed: int = 0):
        if hidden < 1:
            raise ValueError('hidden width must be positive')
        self.hidden = hidden
        self.width = len(FEATURE_NAMES)
        rng = random.Random(seed)
        self.w = [[rng.gauss(0, 1/math.sqrt(self.width)) for _ in range(self.width)] for _ in range(hidden)]
        self.b = [0.0]*hidden
        self.out = {h: [0.0]*hidden for h in HEADS}
        self.bias = {h: 0.0 for h in HEADS}

    @property
    def parameter_count(self) -> int:
        return self.hidden*(self.width+1) + len(HEADS)*(self.hidden+1)

    def forward(self, x):
        if len(x) != self.width:
            raise ValueError('feature width does not match checkpoint')
        h = [math.tanh(sum(a*b for a, b in zip(row, x))+bias) for row, bias in zip(self.w, self.b)]
        return {head: _sigmoid(sum(a*b for a, b in zip(h, self.out[head]))+self.bias[head]) for head in HEADS}, h

    def predict(self, x) -> dict[str, float]:
        return self.forward(x)[0]

    def priors(self, obs: Observation) -> dict[str, float]:
        """The two `SurvivalPrior` probabilities for this observation."""
        return self.predict(encode(obs))

    def fit_epoch(self, rows, *, rng, rate=0.05, batch_size=32):
        """Mini-batch SGD on the summed cross-entropy of both heads."""
        order = list(range(len(rows)))
        rng.shuffle(order)
        for start in range(0, len(order), batch_size):
            batch = order[start:start+batch_size]
            dw = [[0.0]*self.width for _ in range(self.hidden)]
            db = [0.0]*self.hidden
            do = {h: [0.0]*self.hidden for h in HEADS}
            dbias = {h: 0.0 for h in HEADS}
            for index in batch:
                x, labels = rows[index]
                p, h = self.forward(x)
                back = [0.0]*self.hidden
                for head in HEADS:
                    error = p[head]-labels[head]
                    dbias[head] += error
                    for j in range(self.hidden):
                        do[head][j] += error*h[j]
                        back[j] += error*self.out[head][j]
                for j in range(self.hidden):
                    grad = back[j]*(1-h[j]*h[j])
                    db[j] += grad
                    for k, value in enumerate(x):
                        dw[j][k] += grad*value
            step = rate/len(batch)
            for head in HEADS:
                self.bias[head] -= step*dbias[head]
                for j in range(self.hidden):
                    self.out[head][j] -= step*do[head][j]
            for j in range(self.hidden):
                self.b[j] -= step*db[j]
                for k in range(self.width):
                    self.w[j][k] -= step*dw[j][k]

    def save(self, path, **metadata):
        data = dict(version=1, features=FEATURE_NAMES, heads=HEADS, hidden=self.hidden,
                    w=self.w, b=self.b, out=self.out, bias=self.bias, metadata=metadata)
        Path(path).write_text(json.dumps(data, indent=2)+'\n')

    @classmethod
    def load(cls, path) -> 'OpponentModel':
        data = json.loads(Path(path).read_text())
        if data.get('version') != 1 or data.get('features') != list(FEATURE_NAMES) or data.get('heads') != list(HEADS):
            raise ValueError('incompatible opponent-model feature schema')
        model = cls(data['hidden'])
        if (len(data['w']) != model.hidden or any(len(r) != model.width for r in data['w'])
                or len(data['b']) != model.hidden
                or any(len(data['out'][h]) != model.hidden for h in HEADS)):
            raise ValueError('invalid network shape')
        numbers = [v for row in data['w'] for v in row] + data['b']
        numbers += [v for h in HEADS for v in data['out'][h]] + [data['bias'][h] for h in HEADS]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers):
            raise ValueError('nonfinite or nonnumeric network parameter')
        model.w, model.b = data['w'], data['b']
        model.out = {h: list(data['out'][h]) for h in HEADS}
        model.bias = {h: float(data['bias'][h]) for h in HEADS}
        return model


# -- evaluation and training --------------------------------------------------


def metrics(model: OpponentModel | None, rows) -> dict:
    """Log-loss and Brier score per head; `model=None` scores the base rate."""
    result = {}
    for head in HEADS:
        positives = sum(labels[head] for _, labels in rows)
        rate = positives/len(rows)
        base = max(1e-6, min(1-1e-6, rate))
        losses, briers = [], []
        for x, labels in rows:
            p = model.predict(x)[head] if model else base
            p = max(1e-6, min(1-1e-6, p))
            y = labels[head]
            losses.append(-(y*math.log(p)+(1-y)*math.log(1-p)))
            briers.append((p-y)**2)
        result[head] = dict(positives=positives, rate=rate,
                            log_loss=sum(losses)/len(rows), brier=sum(briers)/len(rows),
                            base_rate_log_loss=-(base*math.log(base)+(1-base)*math.log(1-base)),
                            base_rate_brier=base*(1-base))
    return result


def calibration(model: OpponentModel, rows, head: str, buckets: int = 5) -> list[dict]:
    """Observed rate per predicted-probability bucket, for reading a checkpoint."""
    binned = [[] for _ in range(buckets)]
    for x, labels in rows:
        p = model.predict(x)[head]
        binned[min(buckets-1, int(p*buckets))].append((p, labels[head]))
    return [dict(bucket=i, count=len(b), predicted=sum(p for p, _ in b)/len(b), observed=sum(y for _, y in b)/len(b))
            for i, b in enumerate(binned) if b]


def by_defcon(model: OpponentModel, rows, head: str) -> list[dict]:
    """Observed versus predicted rate per DEFCON level: the planner reads
    these priors mostly at DEFCON 2 and 3, so a flat average would mislead."""
    index = FEATURE_NAMES.index('defcon')
    groups: dict[int, list] = {}
    for x, labels in rows:
        groups.setdefault(round(x[index]*5), []).append((model.predict(x)[head], labels[head]))
    return [dict(defcon=d, count=len(g), predicted=sum(p for p, _ in g)/len(g), observed=sum(y for _, y in g)/len(g))
            for d, g in sorted(groups.items())]


def split_games(games, seed):
    """Whole games stay in one split (60/20/20), so positions never leak across."""
    order = list(games)
    random.Random(seed).shuffle(order)
    n = len(order)
    cut1, cut2 = max(1, int(n*0.6)), max(2, int(n*0.8))
    return order[:cut1], order[cut1:cut2], order[cut2:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--logs', default='logs/game-check/*.json', help='Glob of replay logs to learn from')
    parser.add_argument('--epochs', type=int, default=600)
    parser.add_argument('--hidden', type=int, default=8)
    parser.add_argument('--rate', type=float, default=0.3, help='SGD learning rate')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--output', default='models/opponent-model-v1.json')
    args = parser.parse_args(argv)
    if min(args.epochs, args.hidden) < 1 or args.rate <= 0:
        parser.error('epochs, hidden and rate must be positive')
    start = time.monotonic()
    games = []
    for path in sorted(glob.glob(args.logs)):
        log = json.loads(Path(path).read_text())
        if not isinstance(log, dict) or not log.get('new_game') or not log.get('actions'):
            continue
        try:
            rows = collect_rows(log)
        except (ValueError, KeyError) as error:
            print(json.dumps(dict(skipped=path, reason=str(error)[:120])), flush=True)
            continue
        if rows:
            games.append((path, rows))
    if len(games) < 3:
        parser.error('need at least three replayable games')
    train_games, valid_games, test_games = split_games(games, args.seed)
    train = [r for _, rows in train_games for r in rows]
    valid = [r for _, rows in valid_games for r in rows]
    test = [r for _, rows in test_games for r in rows]
    model = OpponentModel(args.hidden, args.seed)
    rng = random.Random(args.seed)
    best, best_loss, best_epoch = copy.deepcopy(model), float('inf'), 0
    for epoch in range(1, args.epochs+1):
        model.fit_epoch(train, rng=rng, rate=args.rate)
        loss = sum(m['log_loss'] for m in metrics(model, valid).values())
        if loss < best_loss:
            best, best_loss, best_epoch = copy.deepcopy(model), loss, epoch
        if epoch % 50 == 0:
            print(json.dumps(dict(epoch=epoch, validation_log_loss=loss)), flush=True)
    report = dict(seed=args.seed, games=len(games), train_games=len(train_games),
                  validation_games=len(valid_games), test_games=len(test_games),
                  samples=len(train), validation_samples=len(valid), test_samples=len(test),
                  epochs=args.epochs, rate=args.rate, selected_epoch=best_epoch, parameters=best.parameter_count,
                  validation=metrics(best, valid), test=metrics(best, test),
                  test_calibration={h: calibration(best, test, h) for h in HEADS},
                  test_by_defcon={h: by_defcon(best, test, h) for h in HEADS},
                  seconds=time.monotonic()-start, logs=args.logs,
                  target='per card pick: opponent removed a held card / lowered DEFCON before our next pick')
    best.save(args.output, **report)
    Path(args.output+'.report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
