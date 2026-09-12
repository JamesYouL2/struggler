#!/usr/bin/env python
"""Measure `spread(turn)`: the VP scale over which a game's outcome flips.

Why this exists. The value function prices one VP at `per_vp(turn) =
vp_base * vp_swing ** ((turn - 1) / 9)`, and `vp_swing` was a guess. Under
`P(win) = F(v_eff / s)` the marginal value of a VP at par is `1 / (4s)`,
so

    per_vp(turn) ~ 1 / spread(turn)
    vp_swing      = spread(turn 1) / spread(turn 10)

which makes `vp_swing` a ratio of standard deviations rather than a taste
parameter. This reads the `vp_by_turn` traces `benchmark.play_game`
records into every report.

    python scripts/vp_spread.py logs/game/*/report.json

**The fit is against the outcome, not against the final VP**, and that is
deliberate. A third of these games end by nuclear war or Wargames, where
the final track reading is not what decided the result -- a side that
loses to DEFCON at +3 did not finish at +3. Regressing the *winner* on the
VP at turn `t` needs no ruling on what those endings "should" score, and
it measures the quantity the model actually wants: how steeply win
probability moves with a VP. The standard deviation of the final track is
printed beside it as a cross-check, and the two agreeing is evidence; the
logistic slope is the number to use.

One caveat, stated rather than corrected: games that ended before turn `t`
do not contribute to `spread(t)`, and those are exactly the swingiest
games, so late spreads are conditioned on survival. That conditioning is
the right one -- the bot only ever asks what a VP is worth on turn 8 while
it is playing turn 8 -- but these are not unconditional variances.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys

# `engine.vp` is signed with the US positive: the probe game finished at
# vp=-7 on the track and the USSR won it.
US_POSITIVE = True


def traces(paths):
    """Every game's (vp_by_turn, final_vp, us_won), deduplicated by seed.

    A mirror report plays the same seed from both seats; with identical
    bots that is literally the same game recorded twice, and counting it
    twice would halve the honest sample size without saying so.
    """
    seen = {}
    for path in paths:
        with open(path) as stream:
            report = json.load(stream)
        for game in report.get('games', []):
            by_turn = game.get('vp_by_turn')
            if not by_turn or not game.get('finished') or not game.get('winner'):
                continue
            key = (game['seed'], tuple(sorted(by_turn.items())))
            seen[key] = ({int(k): v for k, v in by_turn.items()},
                         game['vp'], game['winner'] == 'US')
    return list(seen.values())


def logistic_slope(xs, ys, iterations=50):
    """Fit `P(y) = sigmoid(a + b*x)` by Newton-Raphson; return `(a, b)`.

    Two parameters and one predictor, so this is a 2x2 solve and needs no
    dependency. Returns None when the sample is separable -- every game
    above some VP won and every one below lost -- because the slope then
    diverges and any finite number reported would be an artefact of where
    the iteration was cut off. That happens exactly where it should: late
    turns, where the track has nearly decided the game.
    """
    a = b = 0.0
    for _ in range(iterations):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, a + b * x))))
            r, wgt = y - p, p * (1.0 - p)
            g0 += r
            g1 += r * x
            h00 += wgt
            h01 += wgt * x
            h11 += wgt * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            return None
        da = (h11 * g0 - h01 * g1) / det
        db = (h00 * g1 - h01 * g0) / det
        a, b = a + da, b + db
        if abs(da) < 1e-10 and abs(db) < 1e-10:
            break
    else:
        return None
    return (a, b) if abs(b) < 100.0 else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('reports', nargs='+')
    parser.add_argument('--min-games', type=int, default=10,
                        help='skip a turn with fewer decided games than this')
    args = parser.parse_args(argv)

    games = traces(args.reports)
    if not games:
        print('no finished, decided games with a vp_by_turn trace -- reports '
              'predate the trace, or nothing finished', file=sys.stderr)
        return 1

    at_turn: dict[int, list[tuple[float, float]]] = {}
    final_swing: dict[int, list[float]] = {}
    for by_turn, final, us_won in games:
        for turn, vp in by_turn.items():
            sign = 1.0 if US_POSITIVE else -1.0
            at_turn.setdefault(turn, []).append((sign * vp, 1.0 if us_won else 0.0))
            final_swing.setdefault(turn, []).append(final - vp)

    print(f'{len(games)} decided games')
    print(f'{"turn":>4} {"n":>5} {"P(US)":>6} {"slope":>7} {"spread":>7} '
          f'{"sd(swing)":>9} {"per_vp":>7}')
    spreads = {}
    for turn in sorted(at_turn):
        sample = at_turn[turn]
        if len(sample) < args.min_games:
            continue
        xs = [x for x, _ in sample]
        ys = [y for _, y in sample]
        base = statistics.fmean(ys)
        sd = statistics.stdev(final_swing[turn]) if len(final_swing[turn]) > 1 else float('nan')
        fit = logistic_slope(xs, ys)
        if fit is None:
            print(f'{turn:>4} {len(sample):>5} {base:>6.2f} {"sep":>7} {"--":>7} '
                  f'{sd:>9.2f} {"--":>7}')
            continue
        _a, b = fit
        spread = float('inf') if b == 0 else 1.0 / abs(b)
        spreads[turn] = spread
        print(f'{turn:>4} {len(sample):>5} {base:>6.2f} {b:>7.3f} {spread:>7.2f} '
              f'{sd:>9.2f} {abs(b) / 4.0:>7.4f}')

    if len(spreads) < 2:
        print('\nnot enough turns with a finite slope to take a ratio', file=sys.stderr)
        return 1
    lo, hi = min(spreads), max(spreads)
    print(f'\nvp_swing = spread(T{lo}) / spread(T{hi}) = '
          f'{spreads[lo]:.2f} / {spreads[hi]:.2f} = {spreads[lo] / spreads[hi]:.2f}')
    print('(per_vp is dP(win)/dVP at par -- the shape, not the level; '
          'vp_base still sets where the curve sits.)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
