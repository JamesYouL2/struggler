#!/usr/bin/env python
"""Baseline profiles for Option C (docs/RUST_PORT_PLAN.md): a strategic full
game, and MCTS at 24 simulations on three corpus positions (opening,
scoring card in hand, hazardous late-game hand). Prints wall time and the
share of a few named paths; proportions are the point, absolute times
depend on the machine and on what else is running.

    PYTHONPATH=src python scripts/profile_baseline.py
"""
from __future__ import annotations

import cProfile
import gzip
import json
import pstats
import sys
import time

from struggler.engine import Engine, Side
from struggler.bots.benchmark import play
from struggler.bots.mcts import MCTSPlayer

PATHS = {
    'defcon planner': ('bots/defcon.py', None),
    'evaluator delta': ('bots/strategic.py', 'delta'),
    'country_value': ('bots/strategic.py', 'country_value'),
    '_access': ('bots/strategic.py', '_access'),
    'region_margin': ('bots/strategic.py', 'region_margin'),
    'rank_actions': ('bots/strategic.py', 'rank_actions'),
    'engine step': ('engine/core.py', 'step'),
    'enum access': ('enum.py', None),
}


def shares(pr: cProfile.Profile, total: float) -> dict[str, float]:
    stats = pstats.Stats(pr).stats
    out = {}
    for label, (file_part, func) in PATHS.items():
        if func is None:  # exclusive time of a whole module
            t = sum(v[2] for k, v in stats.items() if file_part in k[0])
        else:  # cumulative time of one function
            t = sum(v[3] for k, v in stats.items() if file_part in k[0] and k[2] == func)
        out[label] = t / total if total else 0.
    return out


def profile(label, fn):
    pr = cProfile.Profile()
    t0 = time.time()
    pr.enable()
    result = fn()
    pr.disable()
    wall = time.time() - t0
    total = sum(v[2] for v in pstats.Stats(pr).stats.values())
    s = shares(pr, total)
    print(f'{label}: {wall:.1f}s profiled | ' + ', '.join(f'{k} {v:.0%}' for k, v in s.items()))
    return result


def corpus_position(pred):
    with gzip.open('tests/corpus/positions.json.gz', 'rt') as f:
        for rec in json.load(f)['records']:
            if pred(rec):
                return rec
    raise LookupError('no corpus position matches')


def mcts_on(rec):
    engine = Engine.deserialize(rec['engine'])
    side = Side(rec['side'])
    bot = MCTSPlayer(simulations=24)
    return bot.choose_action(engine.observe(side), [])


def main():
    profile('strategic full game seed 4000', lambda: play(('strategic', 'strategic', 4000, 'US', 24, 0, None, None)))
    opening = corpus_position(lambda r: r['turn'] == 1 and r['kind'] == 'action_round_play')
    scoring = corpus_position(lambda r: r['kind'] == 'action_round_play' and r['turn'] >= 3
                              and any(c.endswith('_Scoring') for c in Engine.deserialize(r['engine']).hands[r['side']]))
    hazardous = corpus_position(lambda r: r['kind'] == 'action_round_play' and r['turn'] >= 5
                                and Engine.deserialize(r['engine']).defcon <= 3
                                and r.get('planner', {}).get('hazardous') and any(r['planner']['hazardous'].values()))
    for label, rec in (('MCTS opening', opening), ('MCTS scoring', scoring), ('MCTS hazardous', hazardous)):
        print(f"  position: seed {rec['seed']} T{rec['turn']} AR{rec['action_round']} {rec['side']}")
        profile(label, lambda rec=rec: mcts_on(rec))


if __name__ == '__main__':
    main()
