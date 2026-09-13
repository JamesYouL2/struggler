#!/usr/bin/env python
"""What each value term costs to compute: `rank_actions` over corpus positions
with one term's weight set to zero (or its neutral value), against shipped.

The question is "which removal would speed the bot up", and a zero weight only
answers it where the code skips the work at zero -- a multiplier of 0.0 still
pays for what it multiplies. So this times the real ranking, not a count of
lines, and a term whose zero reads the same speed as shipped is one whose code
still runs. Deleting that code would be the saving, and it is not measured
here.

Arms are interleaved per position -- every position ranked once by every arm
before the next position -- so machine drift and contention spread evenly
across arms instead of landing on whichever ran last. Still a wall-clock
measure: run it on a quiet machine, and read ratios, not seconds.

    python scripts/term_cost.py --stride 4 --passes 2
"""
from __future__ import annotations

import argparse
import dataclasses
import gzip
import json
import statistics
import time

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.engine import Engine, Side

CORPUS = 'tests/corpus/positions.json.gz'

ARMS = {
    'shipped': {},
    'access=0': {'access': 0.0},
    'progress=0': {'progress': 0.0},
    'reply_model=0': {'reply_model': 0.0},
    'margin guesses=0': {'margin_battleground': 0.0, 'margin_country': 0.0},
    'first_mover=0': {'first_mover': 0.0},
    'reserve=0': {'reserve': 0.0},
    'region=0': {'region': 0.0},
    'coup_discount=1': {'coup_discount': 1.0},
    'scoring_hand=1': {'scoring_hand': 1.0},
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stride', type=int, default=4, help='every Nth corpus record')
    ap.add_argument('--passes', type=int, default=2)
    args = ap.parse_args(argv)
    with gzip.open(CORPUS) as f:
        records = json.loads(f.read())['records'][::args.stride]
    fields = {f.name for f in dataclasses.fields(StrategicWeights)}
    for arm in ARMS.values():
        assert set(arm) <= fields, f'not a weight: {set(arm) - fields}'
    seconds = {name: 0.0 for name in ARMS}
    for p in range(args.passes):
        for i, rec in enumerate(records):
            engine = Engine.deserialize(rec['engine'])
            obs = engine.observe(Side(rec['side']))
            prior = SurvivalPrior(**rec['prior'])
            names = list(ARMS)
            names = names[i % len(names):] + names[:i % len(names)]  # rotate the order too
            for name in names:
                weights = StrategicWeights(**{**rec['weights'], **ARMS[name]})
                bot = StrategicPlayer(weights, survival_prior=prior)
                t = time.perf_counter()
                bot.rank_actions(obs)
                seconds[name] += time.perf_counter() - t
        print(f'  pass {p + 1}/{args.passes} done', flush=True)
    base = seconds['shipped']
    print(f'\n{len(records)} corpus positions x {args.passes} passes')
    print(f"{'arm':20} {'seconds':>9} {'vs shipped':>11}")
    for name, s in sorted(seconds.items(), key=lambda kv: kv[1]):
        print(f'{name:20} {s:9.2f} {s / base:10.3f}x')
    print('\nWall clock on this machine: ratios, not seconds. A ratio near 1.000 means the')
    print('code for that term still runs at zero; the saving would come from deleting it.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
