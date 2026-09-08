"""Reproducible paired-seat evaluation and evolutionary policy optimization.

Usage: python -m struggler.bots.train evaluate --pairs 20
       python -m struggler.bots.train train --output model.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict
from pathlib import Path

from struggler.bots.greedy import GreedyPlayer
from struggler.bots.naive import RandomPlayer
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import Engine, Side
from struggler.runner import play_game


def evaluate(weights: StrategicWeights, seeds: list[int], opponent: str = 'greedy', rival: StrategicWeights | None = None) -> dict:
    if not seeds:
        raise ValueError('evaluation requires at least one seed')
    if opponent not in ('greedy', 'random', 'strategic'):
        raise ValueError(f'unknown opponent: {opponent}')
    records = []
    for seed in seeds:
        for side in (Side.US, Side.USSR):
            other = (StrategicPlayer(rival) if opponent == 'strategic' else
                     RandomPlayer(seed=seed + 100000) if opponent == 'random' else GreedyPlayer())
            engine = Engine.new_game(seed=seed)
            winner = play_game(engine, {side: StrategicPlayer(weights), side.opponent: other})
            records.append(dict(seed=seed, side=side.value, winner=winner.value if winner else None,
                                score=0.5 if winner is None else float(winner is side),
                                turn=engine.turn, vp=engine.vp))
    scores = [r['score'] for r in records]
    mean = sum(scores) / len(scores)
    # Paired seeds are the sampling unit; seats within a pair are correlated.
    paired = [(scores[i]+scores[i+1])/2 for i in range(0, len(scores), 2)]
    se = (math.sqrt(sum((p-mean)**2 for p in paired) / (len(paired)-1) / len(paired))
          if len(paired) > 1 else None)
    return dict(opponent=opponent, pairs=len(seeds), games=len(records), score_rate=mean,
                wins=sum(r['score'] == 1 for r in records), draws=sum(r['score'] == .5 for r in records),
                by_side={side.value: sum(r['score'] for r in records if r['side'] == side.value)/len(seeds) for side in (Side.US, Side.USSR)},
                paired_standard_error=se, records=records)


def train(initial: StrategicWeights, *, seed: int, pairs: int, generations: int, population: int, output: str) -> StrategicWeights:
    if min(pairs, generations, population) < 1:
        raise ValueError('pairs, generations and population must be positive')
    rng = random.Random(seed)
    champion = initial
    trace = []
    for generation in range(generations):
        seeds = list(range(seed + generation*pairs, seed + (generation+1)*pairs))
        # Evaluate the incumbent and mutations against the same frozen rival
        # and seeds. Half of generations use the greedy anchor to limit drift.
        opponent = 'greedy' if generation % 2 == 0 else 'strategic'
        candidates = [champion] + [StrategicWeights(**{
            k: v * math.exp(rng.gauss(0, .25)) for k, v in asdict(champion).items()
        }) for _ in range(population-1)]
        results = [evaluate(c, seeds, opponent, champion) for c in candidates]
        best = max(range(population), key=lambda i: results[i]['score_rate'])
        champion = candidates[best]
        row = dict(generation=generation, opponent=opponent, seeds=seeds,
                   scores=[r['score_rate'] for r in results], selected=best)
        trace.append(row)
        champion.save(output, training_seed=seed, trace=trace)
        print(json.dumps(row), flush=True)
    return champion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['evaluate', 'train'])
    parser.add_argument('--model', help='JSON weights; omitted uses handcrafted defaults')
    parser.add_argument('--output', default='strategic-model.json')
    parser.add_argument('--report', help='Write full evaluation JSON, including per-game records')
    parser.add_argument('--opponent', choices=['greedy', 'random', 'strategic'], default='greedy')
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--pairs', type=int, default=10)
    parser.add_argument('--generations', type=int, default=5)
    parser.add_argument('--population', type=int, default=5)
    args = parser.parse_args()
    if min(args.pairs, args.generations, args.population) < 1:
        parser.error('pairs, generations and population must be positive')
    weights = StrategicWeights.load(args.model) if args.model else StrategicWeights()
    if args.command == 'train':
        train(weights, seed=args.seed, pairs=args.pairs, generations=args.generations,
              population=args.population, output=args.output)
    else:
        result = evaluate(weights, list(range(args.seed, args.seed+args.pairs)), args.opponent)
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'records'}, indent=2))


if __name__ == '__main__':
    main()
