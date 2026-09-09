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
    'engine step (cumulative)': ('engine/core.py', 'step'),
    'enum access (exclusive)': ('enum.py', None),
}
# Rows named with a function are cumulative; module rows are exclusive of
# callees in other modules. Neither set is disjoint; do not add them.


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


REPORT = []


def profile(label, fn, repeats=3):
    """Unprofiled wall time over `repeats` runs, then one profiled run for
    the shares; everything goes into REPORT for the JSON file."""
    plain = []
    for _ in range(repeats):
        t0 = time.time()
        result = fn()
        plain.append(time.time() - t0)
    pr = cProfile.Profile()
    t0 = time.time()
    pr.enable()
    fn()
    pr.disable()
    wall = time.time() - t0
    total = sum(v[2] for v in pstats.Stats(pr).stats.values())
    s = shares(pr, total)
    print(f'{label}: unprofiled {min(plain):.1f}-{max(plain):.1f}s (x{repeats}), profiled {wall:.1f}s | '
          + ', '.join(f'{k} {v:.0%}' for k, v in s.items()))
    REPORT.append({'label': label, 'unprofiled_seconds': plain, 'profiled_seconds': wall, 'shares': s,
                   'result': result if isinstance(result, dict) else None})
    return result


def corpus_position(pred):
    with gzip.open('tests/corpus/positions.json.gz', 'rt') as f:
        for rec in json.load(f)['records']:
            if pred(rec):
                return rec
    raise LookupError('no corpus position matches')


def mcts_on(rec, *, search_all=False):
    """Run the search and return its statistics; a position where MCTS
    falls back to the plain policy (no scoring card in hand, or sampling
    failure) is a hard error, not a silent non-profile."""
    engine = Engine.deserialize(rec['engine'])
    side = Side(rec['side'])
    bot = MCTSPlayer(simulations=24, search_all=search_all)
    action = bot.choose_action(engine.observe(side), [])
    if bot.last_search is None:
        raise RuntimeError(f"no search ran for seed {rec['seed']} T{rec['turn']} AR{rec['action_round']} {rec['side']}")
    return {'action': action.payload, **{k: (v if isinstance(v, (int, float, bool, str)) else str(v))
                                          for k, v in bot.last_search.items()}}


def main():
    import argparse, os, platform, subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='logs/game-check/baseline-profile.json')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    profile('strategic full game seed 4000', lambda: play(('strategic', 'strategic', 4000, 'US', 24, 0, None, None)),
            args.repeats)
    # MCTS searches only turns with a scoring card in hand: the opening
    # candidate must have one (Astra: record 6, seed 4000 T1 AR1 US).
    opening = corpus_position(lambda r: r['turn'] == 1 and r['kind'] == 'action_round_play'
                              and any(c.endswith('_Scoring') for c in Engine.deserialize(r['engine']).hands[r['side']]))
    scoring = corpus_position(lambda r: r['kind'] == 'action_round_play' and r['turn'] >= 3
                              and any(c.endswith('_Scoring') for c in Engine.deserialize(r['engine']).hands[r['side']]))
    hazardous = corpus_position(lambda r: r['kind'] == 'action_round_play' and r['turn'] >= 5
                                and Engine.deserialize(r['engine']).defcon <= 3
                                and any(op == 'hazardous' and result
                                        for op, _card, result in r.get('planner', {}).get('probes', ())))
    for label, rec, search_all in (('MCTS opening', opening, False),
                                   ('MCTS scoring', scoring, False),
                                   ('MCTS hazardous', hazardous, True)):
        print(f"  position: seed {rec['seed']} T{rec['turn']} AR{rec['action_round']} {rec['side']}")
        profile(label, lambda rec=rec, search_all=search_all: mcts_on(rec, search_all=search_all), args.repeats)
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', 'src'], capture_output=True, text=True).stdout.strip()
    with open(args.out, 'w') as f:
        json.dump({'source_revision': revision, 'dirty': bool(dirty), 'python': sys.version,
                   'platform': platform.platform(), 'cpu_count': os.cpu_count(),
                   'corpus': 'tests/corpus/positions.json.gz', 'cases': REPORT}, f, indent=1)
    print(f'report -> {args.out}')


if __name__ == '__main__':
    main()
