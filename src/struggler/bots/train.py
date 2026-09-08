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
from multiprocessing import Pool
from pathlib import Path

from struggler.bots.greedy import GreedyPlayer
from struggler.bots.naive import RandomPlayer
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import Engine, Side
from struggler.runner import play_game


def _play(job: tuple) -> dict:
    """One evaluation game; a plain function so a worker pool can run it."""
    weights, seed, side_value, opponent, rival = job
    side = Side(side_value)
    other = (StrategicPlayer(rival) if opponent == 'strategic' else
             RandomPlayer(seed=seed + 100000) if opponent == 'random' else GreedyPlayer())
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    winner = play_game(engine, {side: StrategicPlayer(weights), side.opponent: other})
    return dict(seed=seed, side=side.value, winner=winner.value if winner else None,
                score=0.5 if winner is None else float(winner is side),
                turn=engine.turn, vp=engine.vp)


def _run(jobs: list[tuple], workers: int) -> list[dict]:
    if workers <= 1 or len(jobs) <= 1:
        return [_play(j) for j in jobs]
    with Pool(min(workers, len(jobs))) as pool:
        return pool.map(_play, jobs, chunksize=1)


def evaluate(weights: StrategicWeights, seeds: list[int], opponent: str = 'greedy',
             rival: StrategicWeights | None = None, workers: int = 1) -> dict:
    if not seeds:
        raise ValueError('evaluation requires at least one seed')
    if opponent not in ('greedy', 'random', 'strategic'):
        raise ValueError(f'unknown opponent: {opponent}')
    jobs = [(weights, seed, side.value, opponent, rival) for seed in seeds for side in (Side.US, Side.USSR)]
    records = _run(jobs, workers)
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


def mutate(weights: StrategicWeights, rng: random.Random, fields: tuple[str, ...] | None = None,
           scale: float = .25) -> StrategicWeights:
    """Seeded log-normal perturbation of `fields` (default: every weight)."""
    values = asdict(weights)
    names = fields or tuple(values)
    unknown = set(names) - set(values)
    if unknown:
        raise ValueError(f'unknown weight fields: {sorted(unknown)}')
    def perturb(v: float) -> float:
        # Log-normal keeps positive weights positive; a zero weight would be
        # stuck forever under a multiplicative step, so it takes a small
        # absolute one instead.
        return v * math.exp(rng.gauss(0, scale)) if v else abs(rng.gauss(0, scale))
    return StrategicWeights(**{k: perturb(v) if k in names else v for k, v in values.items()})


def train(initial: StrategicWeights, *, seed: int, pairs: int, generations: int, population: int, output: str,
          anchor: str = 'strategic', fields: tuple[str, ...] | None = None, workers: int = 1) -> StrategicWeights:
    """Evolutionary search for weights that beat a frozen anchor.

    The anchor is the *initial* weights playing as the strategic opponent
    (the default; `anchor='greedy'` keeps the old weak opponent), so every
    generation's score means the same thing and drift toward a moving target
    is impossible. `fields` restricts mutation to named weights."""
    if min(pairs, generations, population) < 1:
        raise ValueError('pairs, generations and population must be positive')
    if anchor not in ('strategic', 'greedy'):
        raise ValueError(f'unknown anchor: {anchor}')
    rng = random.Random(seed)
    champion = initial
    trace = []
    for generation in range(generations):
        seeds = list(range(seed + generation*pairs, seed + (generation+1)*pairs))
        candidates = [champion] + [mutate(champion, rng, fields) for _ in range(population-1)]
        jobs = [(c, s, side.value, anchor, initial) for c in candidates for s in seeds for side in (Side.US, Side.USSR)]
        records = _run(jobs, workers)
        per = len(seeds)*2
        scores = [sum(r['score'] for r in records[i*per:(i+1)*per])/per for i in range(population)]
        best = max(range(population), key=lambda i: scores[i])  # ties keep the incumbent
        champion = candidates[best]
        row = dict(generation=generation, anchor=anchor, seeds=seeds, scores=scores, selected=best,
                   fields=list(fields) if fields else 'all', weights=asdict(champion))
        trace.append(row)
        champion.save(output, training_seed=seed, anchor=anchor, trace=trace)
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
    parser.add_argument('--anchor', choices=['strategic', 'greedy'], default='strategic',
                        help='Frozen training opponent: the initial weights as strategic (default) or greedy')
    parser.add_argument('--fields', help='Comma-separated weight names to mutate (default: all)')
    parser.add_argument('--rival', help='JSON weights for the strategic evaluation opponent (default: handcrafted)')
    parser.add_argument('--workers', type=int, default=1, help='Parallel games (processes)')
    args = parser.parse_args()
    if min(args.pairs, args.generations, args.population, args.workers) < 1:
        parser.error('pairs, generations, population and workers must be positive')
    weights = StrategicWeights.load(args.model) if args.model else StrategicWeights()
    if args.command == 'train':
        fields = tuple(f.strip() for f in args.fields.split(',')) if args.fields else None
        train(weights, seed=args.seed, pairs=args.pairs, generations=args.generations,
              population=args.population, output=args.output, anchor=args.anchor,
              fields=fields, workers=args.workers)
    else:
        rival = StrategicWeights.load(args.rival) if args.rival else None
        result = evaluate(weights, list(range(args.seed, args.seed+args.pairs)), args.opponent,
                          rival, workers=args.workers)
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'records'}, indent=2))


if __name__ == '__main__':
    main()
