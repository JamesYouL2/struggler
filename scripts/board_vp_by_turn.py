#!/usr/bin/env python
"""What a Battleground is worth, by turn, in Ops and in VP.

The maintainer's reading: the large miscalibration is not the VP-vs-turn
curve (`vp_swing`, measured near-flat) but that **board value matters less
and less over the game** -- `vp_value` grows ~3.4x across a game while a
Battleground's `delta` grows only ~1.28x, so a Battleground falls from
~3.5 VP to ~1.3 VP.

This measures both halves on real corpus positions, under several
`scoring_discount` values, because the two are coupled: `ops_value(1)` is a
max over uses and rises with urgency too, so steepening the discount may
move a Battleground's VP or may cancel against the denominator. The
scale-invariance result (`Q/O = (1-r)(S/O) - 40er`) says board weights
cancel exactly; `scoring_discount` is not a board weight, but it moves every
region at once, so whether it behaves like one is an empirical question.

    python scripts/board_vp_by_turn.py [--discounts 0.8,0.6,0.5]
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import statistics

from struggler.engine import Engine, Side
from struggler.bots.strategic import StrategicPlayer, StrategicWeights

CORPUS = pathlib.Path('tests/corpus/positions.json.gz')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--discounts', default='0.8,0.6,0.5')
    ap.add_argument('--per-turn', type=int, default=4)
    # The parity corpus samples turns 1/3/5/7/9 only and must keep doing so --
    # it is the exactness oracle and `test_parity_corpus.py` rebuilds a bot per
    # record, so doubling it doubles the slowest test in the suite. A side
    # capture (`capture_corpus.py --turns 1,2,3,...`) goes in its own file and
    # is what fills in the even turns.
    ap.add_argument('--corpus', default=str(CORPUS))
    a = ap.parse_args(argv)
    discounts = [float(x) for x in a.discounts.split(',')]

    with gzip.open(a.corpus, 'rt') as f:
        corpus = json.loads(f.read())
    sample, seen = [], collections.Counter()
    for rec in corpus['records']:
        if seen[rec['turn']] < a.per_turn:
            seen[rec['turn']] += 1
            sample.append(rec)

    print(f'{len(sample)} corpus positions; 2 Ops into the best empty '
          f'stability-2 Battleground')
    print('ops = delta / ops_value(1)  -- how many Ops the Battleground is worth')
    print('vp  = delta / vp_value      -- the same thing denominated in VP')
    print()
    header = f'{"discount":>9} ' + ' '.join(f'{"T" + str(t):>13}' for t in sorted(seen))
    print(header)
    print(f'{"":>9} ' + ' '.join(f'{"ops":>6}{"vp":>7}' for _ in seen))

    for g in discounts:
        cells, rows = [], collections.defaultdict(lambda: ([], [], [], []))
        for rec in sample:
            engine = Engine.deserialize(rec['engine'])
            obs = engine.observe(Side(rec['side']))
            bot = StrategicPlayer(StrategicWeights(scoring_discount=g))
            bot.rank_actions(obs)
            one_op, vpv = bot.ops_value(obs, 1), bot.vp_value(obs)
            empty = any_bg = 0.0
            for cid, info in engine.board.countries.items():
                if not info.battleground:
                    continue
                gain = bot.delta(obs, cid, own=2)
                any_bg = max(any_bg, gain)
                inf = engine.board.influence[cid]
                if info.stability == 2 and not inf['US'] and not inf['USSR']:
                    empty = max(empty, gain)
            if one_op and vpv:
                # The empty stability-2 Battleground is the clean comparison
                # but it stops existing: by turn 7 every one is contested, so
                # that column goes blank exactly where the answer matters.
                # `any` keeps a reading at every turn at the cost of comparing
                # slightly different things turn to turn.
                if empty:
                    rows[rec['turn']][0].append(empty / one_op)
                    rows[rec['turn']][1].append(empty / vpv)
                if any_bg:
                    rows[rec['turn']][2].append(any_bg / one_op)
                    rows[rec['turn']][3].append(any_bg / vpv)
        for t in sorted(seen):
            ops, vp, aops, avp = rows[t]
            cells.append(f'{statistics.fmean(ops):>6.2f}{statistics.fmean(vp):>7.2f}'
                         if ops else f'{"--":>6}{"--":>7}')
        print(f'{g:>9.2f} ' + ' '.join(cells) + '   empty stability-2')
        cells = []
        for t in sorted(seen):
            _o, _v, aops, avp = rows[t]
            cells.append(f'{statistics.fmean(aops):>6.2f}{statistics.fmean(avp):>7.2f}'
                         if aops else f'{"--":>6}{"--":>7}')
        print(f'{"":>9} ' + ' '.join(cells) + '   best Battleground, any')

    print()
    print('If the `ops` row is flat across discounts, scoring_discount cancels')
    print('against ops_value(1) exactly as the board weights do, and no setting')
    print('of it can change what a Battleground is worth. If it moves, the')
    print('bucket model has a lever and the weight A/Bs below are measuring it.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
