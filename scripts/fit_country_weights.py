"""Fit the strategic bot's fixed per-country weights from the exact potential.

The scoring potential values a country, at one position, by its exact
per-position linear weights (`forecast.tier_weights`): what the region's
expected payout is with that country forced to each holder. A fixed weight
per country cannot follow the position, but it can follow the part that
moves most -- the turn and the deck -- by being proportional to the region's
scoring mass, which the bot already computes as `urgency`:

    importance(c, s) = country_vp_scale * (a[c][s] * M_region + sea[c] * M_sea)

`a[c][s]` is the VP a region's future scorings pay side `s` for controlling
`c` instead of leaving it uncontrolled (tier change plus the 10.1.2 bonus),
per unit of mass, fitted by least squares over self-play positions:

    y = sum_h M_h * g[c, h, s]      (the exact mass-weighted gain)
    a = sum(M * y) / sum(M^2)       (M = sum_h M_h)

Southeast Asia's own payout is exact and fixed (2 for Thailand, 1 otherwise)
and rides its card's mass, as `urgency` already carries it.

    uv run python scripts/fit_country_weights.py fit --seeds 40000-40015 \
        --out src/struggler/bots/strategic/fitted_country_weights.json
    uv run python scripts/fit_country_weights.py check --seeds 41000-41007 \
        --weights src/struggler/bots/strategic/fitted_country_weights.json

`check` is the exact potential used as an auditor (step 4 of the
2026-09-18 plan). On held-out games it reports how much of each country's
exact gain the fixed weights explain (R^2) and the VP a region loses when
the fixed weights pick a different country than the exact gain would.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import datetime
import hashlib
import json
import logging
import os
import statistics
import subprocess
import sys
from pathlib import Path

from struggler.engine import Engine, Region, Side
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import evaluator as ev, forecast as fcst, valuation
from struggler.bots.strategic.public_cards import SCORING_CARD_REGION

SEA = 'Southeast_Asia_Scoring'
REGION_CARD = {r: c for c, r in SCORING_CARD_REGION.items()}


def seed_range(text: str) -> list[int]:
    lo, _, hi = text.partition('-')
    return list(range(int(lo), int(hi or lo) + 1))


def play(seed: int) -> list[dict]:
    """One self-play game; a record per decision with a real choice: the
    board as influence, the side to act, and that side's region masses by
    horizon. Duplicate (board, side, masses) rows are dropped."""
    logging.disable(logging.CRITICAL)
    weights = StrategicWeights()
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(weights), Side.USSR: StrategicPlayer(weights)}
    seen, out = set(), []
    while not engine.is_terminal and engine.pending_decision is not None:
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        obs = engine.observe(d.actor)
        if len(d.options) > 1 and engine.phase != 'setup':
            masses = {}
            for region in Region:
                per_h = collections.defaultdict(float)
                for mass, h in valuation.shaped_masses(obs, REGION_CARD[region], weights):
                    per_h[h] += mass
                masses[region.name] = [per_h[1], per_h[2]]
            masses['SEA'] = sum(m for m, _ in valuation.shaped_masses(obs, SEA, weights))
            influence = {c: (v['US'], v['USSR']) for c, v in engine.board.influence.items()}
            key = (tuple(sorted(influence.items())), d.actor.value,
                   tuple(round(x, 9) for r in Region for x in masses[r.name]))
            if key not in seen:
                seen.add(key)
                out.append({'seed': seed, 'turn': engine.turn, 'side': d.actor.value,
                            'influence': influence, 'masses': masses})
        engine.step(bots[d.actor].choose_action(obs, []))
    return out


def gains(numbered) -> list[tuple[int, str, int, str, float, float]]:
    """(record, region, country index, side, M, y) for every member of every
    region: the exact mass-weighted gain of controlling it, for the record's
    side."""
    n, record = numbered
    logging.disable(logging.CRITICAL)
    t = ev.terrain()
    engine = Engine(seed=0)
    for c, (us, ussr) in record['influence'].items():
        engine.board.influence[c]['US'], engine.board.influence[c]['USSR'] = us, ussr
    pos = ev.Position(t).sync(engine.board)
    s = ev.US if record['side'] == 'US' else ev.USSR
    sign = 1 if s == ev.US else -1
    rows = []
    for region in Region:
        m1, m2 = record['masses'][region.name]
        if m1 == 0 and m2 == 0:
            continue
        tables = {h: fcst.tier_weights(t, fcst.forecast_controls(t, pos, region, h)) for h in (1, 2)}
        members = t.members[region]
        for k, i in enumerate(members):
            bonus = float(t.battleground[i]) + float(i in t.home[1 - s])
            y = 0.0
            for h, m in ((1, m1), (2, m2)):
                w_us, w_ussr, w_open = tables[h][k]
                tier = (w_us - w_open) if s == ev.US else (w_ussr - w_open)
                y += m * (sign * tier + bonus)
            rows.append((n, region.name, i, record['side'], m1 + m2, y))
    return rows


def collect(seeds: list[int], workers: int) -> tuple[list[dict], list[tuple]]:
    with cf.ProcessPoolExecutor(workers) as pool:
        records = [r for game in pool.map(play, seeds) for r in game]
        rows = [row for part in pool.map(gains, enumerate(records), chunksize=8) for row in part]
    return records, rows


def fit(rows) -> dict:
    num, den = collections.defaultdict(float), collections.defaultdict(float)
    for _, _region, i, side, m, y in rows:
        num[i, side] += m * y
        den[i, side] += m * m
    return {key: num[key] / den[key] for key in num if den[key] > 0}


def r_squared(rows, a) -> dict[str, float]:
    by_region = collections.defaultdict(list)
    for _, region, i, side, m, y in rows:
        if m > 0:
            by_region[region].append((y / m, a.get((i, side), 0.0)))
    out = {}
    for region, pairs in by_region.items():
        mu = statistics.mean(y for y, _ in pairs)
        tot = sum((y - mu) ** 2 for y, _ in pairs)
        res = sum((y - p) ** 2 for y, p in pairs)
        out[region] = 1 - res / tot if tot else float('nan')
    return out


def regret(rows, a) -> dict[str, tuple[float, float, float]]:
    """Per region, over (record, side): the exact gain of the exact best
    member minus the exact gain of the fixed weights' favourite, per unit
    of mass -- mean, p90, and the mean exact best, in VP."""
    groups = collections.defaultdict(list)
    for n, region, i, side, m, y in rows:
        groups[region, side, n].append((i, m, y))
    out = collections.defaultdict(list)
    for (region, side, _), members in groups.items():
        m = members[0][1]
        if m <= 0:
            continue
        true_best = max(y for _, _, y in members) / m
        fixed_pick = max(members, key=lambda x: a.get((x[0], side), 0.0))[2] / m
        out[region].append((true_best - fixed_pick, true_best))
    report = {}
    for region, xs in out.items():
        losses = sorted(x for x, _ in xs)
        report[region] = (statistics.mean(losses), losses[int(0.9 * len(losses))],
                          statistics.mean(b for _, b in xs))
    return report


def git_revision() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('mode', choices=('fit', 'check'))
    parser.add_argument('--seeds', required=True)
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                        help='processes; half the cores by default (the standing rule)')
    parser.add_argument('--out', type=Path, default=Path('src/struggler/bots/strategic/fitted_country_weights.json'))
    parser.add_argument('--weights', type=Path, default=Path('src/struggler/bots/strategic/fitted_country_weights.json'))
    args = parser.parse_args(argv)
    seeds = seed_range(args.seeds)
    records, rows = collect(seeds, args.workers)
    t = ev.terrain()
    print(f'{len(seeds)} games, {len(records)} positions, {len(rows)} country rows', file=sys.stderr)
    if args.mode == 'fit':
        a = fit(rows)
        # The scale at which the new fit reproduces the SHIPPED importance
        # level, so a refit can be switched on without moving it.
        #
        # This matched the guessed `battleground`/`control` tiers until
        # 2026-09-21, when those weights were deleted (docs/notes/claude/
        # 2026-09-21-the-fresh-block-answers-the-fit.md). The reference is
        # now the fitted weights in force times the scale in force -- which
        # means matched_scale CHAINS: refit twice and the second matches
        # the first, not the tiers. That is the intended meaning (keep the
        # level where the shipped bot has it) but it is not the old one.
        #
        # A country the shipped file does not cover is an error, not a
        # zero, for the same reason `_fitted_table` says so.
        old = new = 0.0
        scale = StrategicWeights().country_vp_scale
        shipped = json.loads(ev.FITTED_WEIGHTS_PATH.read_text())['weights']
        for _, _region, i, side, m, _y in rows:
            old += scale * shipped[t.ids[i]][side] * m
            new += a.get((i, side), 0.0) * m
        data = {
            'what': 'Fixed per-country control weights fitted to the exact scoring potential; '
                    'see scripts/fit_country_weights.py and docs/notes/claude/'
                    '2026-09-18-fitted-country-weights.md',
            'units': 'VP of future regional scoring per unit of scoring mass, for controlling the '
                     'country instead of leaving it uncontrolled (tier change + 10.1.2 bonus)',
            'europe_control_vp': ev.EUROPE_CONTROL_VP,
            'matched_scale': old / new,
            'source_revision': git_revision(),
            'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'seeds': args.seeds,
            'positions': len(records),
            'captured': datetime.date.today().isoformat(),
            'in_sample_r2': r_squared(rows, a),
            'weights': {t.ids[i]: {s: round(a[i, s], 6) for s in ('US', 'USSR') if (i, s) in a}
                        for i in sorted({i for i, _ in a})},
        }
        args.out.write_text(json.dumps(data, indent=2) + '\n')
        print(json.dumps({k: data[k] for k in ('matched_scale', 'positions', 'in_sample_r2')}, indent=2))
        return 0
    data = json.loads(args.weights.read_text())
    a = {(t.index[c], s): v for c, per in data['weights'].items() for s, v in per.items()}
    print('held-out R^2 by region:', {k: round(v, 3) for k, v in r_squared(rows, a).items()})
    for region, (mean, p90, best) in sorted(regret(rows, a).items()):
        print(f'  {region:16s} regret mean {mean:.3f} p90 {p90:.3f} VP/mass (best gain {best:.2f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
