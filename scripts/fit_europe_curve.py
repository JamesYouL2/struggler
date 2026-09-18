"""Fit Europe's continuous curve, and ask whether the other regions want one.

Europe's tiers step from domination (7 + bonuses) straight to Control, an
automatic victory. `StrategicWeights.europe_curve` replaces that with

    f(x) = 20 * tanh(x / k),     Control = +/-20 exactly

where x is the net VP Europe would score now and 20 is the automatic
victory above par (`stakes.AUTO_VICTORY_VP`). This fits k to the exact
potential: the expected Europe payout at the next scoring
(`forecast.expected_payout`, horizon 1), with Control priced at the same 20.

For every other region it also fits `C * tanh(x / k)` (both free) and reports
its R^2 beside the tier step's (the best multiple of the region score now),
so "should every region be a curve?" has a number behind it.

    uv run python scripts/fit_europe_curve.py --seeds 40000-40007
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import logging
import math
import os
import statistics
import sys

from struggler.engine import Engine, Region
from struggler.bots.strategic import evaluator as ev, forecast as fcst
from struggler.bots.strategic.stakes import AUTO_VICTORY_VP

sys.path.insert(0, os.path.dirname(__file__))
from fit_country_weights import play, seed_range  # the sibling script, after the path insert


def points(record: dict) -> list[tuple[str, float, bool, float]]:
    """(region, x now, x is Control, exact E at horizon 1) per region."""
    logging.disable(logging.CRITICAL)
    ev.EUROPE_CONTROL_VP = AUTO_VICTORY_VP  # the fit's price of Control, read at call time
    t = ev.terrain()
    engine = Engine(seed=0)
    for c, (us, ussr) in record['influence'].items():
        engine.board.influence[c]['US'], engine.board.influence[c]['USSR'] = us, ussr
    pos = ev.Position(t).sync(engine.board)
    out = []
    for region in Region:
        x = ev.region_vp(t, pos, region, europe_control_vp=AUTO_VICTORY_VP)
        control = region is Region.EUROPE and abs(x) == AUTO_VICTORY_VP and ev.europe_control(t, pos) is not None
        y = fcst.expected_payout(t, fcst.forecast_controls(t, pos, region, 1)).total
        out.append((region.name, x, control, y))
    return out


def r2(ys, preds) -> float:
    mu = statistics.mean(ys)
    tot = sum((y - mu) ** 2 for y in ys)
    return 1 - sum((y - p) ** 2 for y, p in zip(ys, preds, strict=True)) / tot if tot else float('nan')


def curve(x, control, cap, k):
    if control:
        return math.copysign(cap, x)
    return cap * math.tanh(x / k)


def best_k(rows, cap) -> tuple[float, float]:
    ys = [y for _, _, y in rows]
    grid = [0.5 + 0.25 * i for i in range(120)]
    return max(((r2(ys, [curve(x, c, cap, k) for x, c, _ in rows]), k) for k in grid))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seeds', required=True)
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args(argv)
    with cf.ProcessPoolExecutor(args.workers) as pool:
        records = [r for game in pool.map(play, seed_range(args.seeds)) for r in game]
        rows = [p for part in pool.map(points, records, chunksize=16) for p in part]
    print(f'{len(records)} positions', file=sys.stderr)
    for region in Region:
        data = [(x, c, y) for name, x, c, y in rows if name == region.name]
        ys = [y for _, _, y in data]
        scale = sum(x * y for x, _, y in data) / (sum(x * x for x, _, _ in data) or 1)
        step = r2(ys, [scale * x for x, _, _ in data])
        if region is Region.EUROPE:
            fit, k = best_k(data, AUTO_VICTORY_VP)
            print(f'{region.name:16s} tier step R^2 {step:.3f}   20*tanh(x/k) R^2 {fit:.3f} at k={k:.2f}'
                  f'   (Control rows: {sum(c for _, c, _ in data)})')
        else:
            best = max(((*best_k(data, cap), cap) for cap in [2 + 0.5 * i for i in range(40)]))
            print(f'{region.name:16s} tier step R^2 {step:.3f}   C*tanh(x/k) R^2 {best[0]:.3f}'
                  f' at C={best[2]:.1f}, k={best[1]:.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
