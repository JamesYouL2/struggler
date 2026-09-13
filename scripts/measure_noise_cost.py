#!/usr/bin/env python
"""What does a random legal move cost?

`LLMPlayer` retries once on an invalid response and then falls back to a
RANDOM legal move (`bots/llm/player.py`, `_MAX_RETRIES`). So a model's
schema-failure rate is not a nuisance -- it is a rate of random moves, and
the question "is this cheap model good enough" is partly the question "how
much does a random move cost", which needs no model and no API to answer.

Plays the strategic bot against a copy of itself whose decisions are
replaced, with probability q, by a uniform choice among the legal options.
The score curve against q converts a schema-failure rate into board points.

It does NOT say how strong any LLM is. It says what the HARNESS costs when
the model fails, which is the floor under any model's result and the reason
a 2%-invalid model cannot be evaluated at all.

    python scripts/measure_noise_cost.py --seeds 4000-4015 --rates 0,0.02,0.05,0.25,1.0
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import random
import statistics
import sys

from struggler.engine import Engine, Side
from struggler.bots.strategic import StrategicPlayer


class Noisy:
    """The strategic bot, with `q` of its decisions replaced by a coin flip."""

    def __init__(self, q: float, seed: int):
        self.inner = StrategicPlayer()
        self.q = q
        self.rng = random.Random(seed)
        self.noised = 0
        self.decisions = 0

    def choose_action(self, observation, history):
        self.decisions += 1
        if self.q and self.rng.random() < self.q:
            self.noised += 1
            return self.rng.choice(list(observation.pending_decision.options))
        return self.inner.choose_action(observation, history)


def play(job):
    q, seed, side_value = job
    side = Side(side_value)
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    noisy = Noisy(q, seed)
    players = {side: noisy, side.opponent: StrategicPlayer()}
    steps = 0
    while not engine.is_terminal and steps < 20000:
        steps += 1
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        engine.step(players[d.actor].choose_action(engine.observe(d.actor), []))
    winner = engine.winner
    result = 0.5 if winner is None else float(winner is side)
    return q, result, noisy.noised, noisy.decisions, engine.turn


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='4000-4015')
    ap.add_argument('--rates', default='0,0.01,0.02,0.05,0.10,0.25,1.0')
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition('-')
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    rates = [float(r) for r in args.rates.split(',')]
    # Both sides, so a side bias cannot be read as a noise effect.
    jobs = [(q, s, sv) for q in rates for s in seeds for sv in ('US', 'USSR')]

    got: dict[float, list] = {q: [] for q in rates}
    noised: dict[float, list] = {q: [] for q in rates}
    turns: dict[float, list] = {q: [] for q in rates}
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for q, result, n, d, turn in pool.map(play, jobs):
            got[q].append(result)
            noised[q].append(n / d if d else 0.)
            turns[q].append(turn)

    n_games = len(seeds) * 2
    print(f'{n_games} games per rate, both sides, seeds {args.seeds}\n')
    print(f'{"q":>6} {"score":>8} {"+/-":>7} {"actual q":>9} {"mean turn":>10}')
    for q in rates:
        v = got[q]
        m = statistics.fmean(v)
        se = (statistics.pstdev(v) / len(v) ** 0.5) if len(v) > 1 else 0.
        print(f'{q:>6.2f} {m:>8.3f} {1.96*se:>7.3f} {statistics.fmean(noised[q]):>9.3f} '
              f'{statistics.fmean(turns[q]):>10.1f}')
    print('\n  score is the NOISY side\'s result against a clean strategic bot.')
    print('  A rate whose score is inside the q=0 interval is a rate at which')
    print('  a model\'s failures are invisible; one below it is a rate at which')
    print('  any model evaluated at it is being measured through the damage.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
