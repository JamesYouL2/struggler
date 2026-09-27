"""Fit and test win-probability models on held-out games -- no MCTS needed.

The question (maintainer, 2026-09-27): does a logistic fit predict game
outcomes better than the current bot, and what does clipping at
[0.05, 0.95] (or the maintainer's [0.10, 0.90]) cost or buy? That is an
offline prediction question: positions from finished games, fitted on
some seeds and scored on seeds the fit never saw. Playing strength is a
separate question for search (docs/notes/codex/2026-09-27-linear-value-learning.md).

Input: `scripts/collect_winprob.py` rows, one per turn start per seat,
labelled with the engine's winner (1 / 0.5 draw / 0).

Split BY SEED, so both seats and every turn of a game stay together:
seed % 5 in {0, 1, 2} train, 3 validation (picks the L2 strength), 4 test.
Every number reported is on the test games only.

Models:

- `constant`: the training win rate;
- `vp`: logistic on banked VP;
- `leaf as-is`: the current MCTS leaf exactly as `MCTSPlayer.leaf_return`
  scores it, `p = (1 + tanh(leaf_raw / 100)) / 2`, no fitting;
- `leaf calibrated`: the same raw bot value, logistic-calibrated
  (a + b * value) -- the fairest reading of "the current bot";
- `leaf calibrated x turn`: plus a turn interaction;
- `09-10 shape`: vp + board_vp * turn / 10 (the archived fit);
- `logistic`: the richer public-feature model.

Pure Python (the repo carries no numpy): Newton's method with L2 on
standardised features.

    uv run python scripts/fit_winprob.py logs/winprob/samples-600.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys

EPS = 1e-6


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def logloss(ps, ys) -> float:
    return -sum(y * math.log(min(1 - EPS, max(EPS, p))) + (1 - y) * math.log(min(1 - EPS, max(EPS, 1 - p)))
                for p, y in zip(ps, ys)) / len(ys)


def brier(ps, ys) -> float:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)


def solve(a, b):
    """Gauss-Jordan with partial pivoting: a x = b."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        if abs(m[c][c]) < 1e-12:
            m[c][c] = 1e-12
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


class Logistic:
    """L2-regularised logistic regression with soft labels, on standardised
    features; column 0 of every row is the intercept and is not penalised."""

    def __init__(self, l2: float):
        self.l2 = l2

    def fit(self, xs, ys, iters: int = 30):
        d = len(xs[0])
        self.mu = [0.0] + [sum(x[j] for x in xs) / len(xs) for j in range(1, d)]
        self.sd = [1.0] + [max(1e-9, math.sqrt(sum((x[j] - self.mu[j]) ** 2 for x in xs) / len(xs)))
                           for j in range(1, d)]
        zs = [self._std(x) for x in xs]
        w = [0.0] * d
        for _ in range(iters):
            grad = [0.0] * d
            hess = [[0.0] * d for _ in range(d)]
            for z, y in zip(zs, ys):
                p = sigmoid(sum(wi * zi for wi, zi in zip(w, z)))
                r = p - y
                s = p * (1 - p)
                for i in range(d):
                    grad[i] += r * z[i]
                    zi = s * z[i]
                    for j in range(i, d):
                        hess[i][j] += zi * z[j]
            n = len(zs)
            for i in range(d):
                grad[i] = grad[i] / n + (self.l2 * w[i] if i else 0.0)
                for j in range(i, d):
                    hess[i][j] = hess[i][j] / n + (self.l2 if i == j and i else 0.0)
                    hess[j][i] = hess[i][j]
            step = solve(hess, grad)
            w = [wi - si for wi, si in zip(w, step)]
            if max(abs(s) for s in step) < 1e-9:
                break
        self.w = w
        return self

    def _std(self, x):
        return [(x[j] - self.mu[j]) / self.sd[j] for j in range(len(x))]

    def predict(self, x) -> float:
        return sigmoid(sum(wi * zi for wi, zi in zip(self.w, self._std(x))))


FEATURES = {
    'vp': lambda r: [1.0, r['vp']],
    'leaf calibrated': lambda r: [1.0, r['leaf_raw'] / 100.0],
    'leaf calibrated x turn': lambda r: [1.0, r['leaf_raw'] / 100.0, r['leaf_raw'] / 100.0 * r['turn'] / 10.0],
    '09-10 shape': lambda r: [1.0, r['vp'], r['board_vp'] * r['turn'] / 10.0],
    'logistic': lambda r: [
        1.0, r['vp'], r['vp'] * r['turn'] / 10.0, r['board_vp'], r['board_vp'] * r['turn'] / 10.0,
        r['turn'] / 10.0, 1.0 if r['side'] == 'US' else 0.0, r['defcon'],
        r['space'] - r['opp_space'], r['china'], r['hand_scoring'], r['hand_ops'] / 10.0,
        max(0, r['vp'] - 12), max(0, -r['vp'] - 12),
    ],
}
L2_GRID = (0.0, 1e-4, 1e-3, 1e-2, 1e-1)


def split(rows):
    parts = {'train': [], 'val': [], 'test': []}
    for r in rows:
        k = r['seed'] % 5
        parts['train' if k < 3 else 'val' if k == 3 else 'test'].append(r)
    return parts


def fit_all(parts):
    """Every model's test predictions, plus what each fit chose."""
    train, val, test = parts['train'], parts['val'], parts['test']
    y = lambda rs: [r['score'] for r in rs]
    preds, chosen = {}, {}
    base = sum(y(train)) / len(train)
    preds['constant'] = [base] * len(test)
    preds['leaf as-is'] = [(1.0 + math.tanh(r['leaf_raw'] / 100.0)) / 2.0 for r in test]
    for name, f in FEATURES.items():
        best = None
        for l2 in L2_GRID:
            m = Logistic(l2).fit([f(r) for r in train], y(train))
            ll = logloss([m.predict(f(r)) for r in val], y(val))
            if best is None or ll < best[0]:
                best = (ll, l2, m)
        _, l2, _m = best
        m = Logistic(l2).fit([f(r) for r in train + val], y(train + val))  # refit on train + val
        preds[name] = [m.predict(f(r)) for r in test]
        chosen[name] = {'l2': l2, 'weights': [round(w, 4) for w in m.w]}
    return preds, chosen


def clip(ps, lo, hi):
    return [min(hi, max(lo, p)) for p in ps]


def calibration(ps, ys, edges=(0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1.0001)):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        idx = [i for i, p in enumerate(ps) if lo <= p < hi]
        if idx:
            out.append((f'{lo:.2f}-{min(hi, 1):.2f}', len(idx), sum(ps[i] for i in idx) / len(idx),
                        sum(ys[i] for i in idx) / len(idx)))
    return out


def bootstrap_diff(rows, pa, pb, ys, reps: int = 2000, seed: int = 1):
    """Paired, grouped by game: test log loss of A minus B, 90% interval."""
    by_seed = {}
    for i, r in enumerate(rows):
        by_seed.setdefault(r['seed'], []).append(i)
    seeds = sorted(by_seed)
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        idx = [i for s in (rng.choice(seeds) for _ in seeds) for i in by_seed[s]]
        diffs.append(logloss([pa[i] for i in idx], [ys[i] for i in idx])
                     - logloss([pb[i] for i in idx], [ys[i] for i in idx]))
    diffs.sort()
    point = logloss(pa, ys) - logloss(pb, ys)
    return point, diffs[int(0.05 * reps)], diffs[int(0.95 * reps)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('samples')
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    data = json.load(open(args.samples))
    rows = data['rows'] if isinstance(data, dict) and 'rows' in data else data
    rows = [r for r in rows if 'score' in r and 'leaf_raw' in r]
    parts = split(rows)
    test = parts['test']
    ys = [r['score'] for r in test]
    print(f"{len(rows)} rows from {len({r['seed'] for r in rows})} games; "
          f"test {len(test)} rows / {len({r['seed'] for r in test})} games")
    preds, chosen = fit_all(parts)
    report = {'rows': len(rows), 'test_rows': len(test), 'models': {}, 'chosen': chosen}
    print(f"\n{'model':24} {'log loss':>9} {'Brier':>7}   {'@[.05,.95]':>10} {'@[.10,.90]':>10}   {'share >.95 or <.05':>18}")
    for name, ps in preds.items():
        ext = sum(1 for p in ps if p > .95 or p < .05) / len(ps)
        c05, c10 = clip(ps, .05, .95), clip(ps, .10, .90)
        row = {'logloss': logloss(ps, ys), 'brier': brier(ps, ys),
               'logloss_clip05': logloss(c05, ys), 'logloss_clip10': logloss(c10, ys),
               'brier_clip05': brier(c05, ys), 'brier_clip10': brier(c10, ys), 'extreme_share': ext}
        report['models'][name] = row
        print(f"{name:24} {row['logloss']:9.4f} {row['brier']:7.4f}   {row['logloss_clip05']:10.4f} "
              f"{row['logloss_clip10']:10.4f}   {ext:18.1%}")
    best_bot = min(('leaf as-is', 'leaf calibrated', 'leaf calibrated x turn'),
                   key=lambda n: report['models'][n]['logloss'])
    point, lo, hi = bootstrap_diff(test, preds['logistic'], preds[best_bot], ys)
    report['logistic_minus_best_bot'] = {'best_bot': best_bot, 'point': point, 'lo90': lo, 'hi90': hi}
    print(f"\nlogistic minus {best_bot}, test log loss, paired by game: {point:+.4f} [{lo:+.4f}, {hi:+.4f}] (90%)")
    for name in ('leaf as-is', best_bot, 'logistic'):
        print(f"\ncalibration, {name} (bin, n, mean predicted, observed):")
        for b, n, mp, ob in calibration(preds[name], ys):
            print(f"  {b:>10} {n:5d}  {mp:.3f}  {ob:.3f}")
        report['models'][name]['calibration'] = calibration(preds[name], ys)
    if args.out:
        json.dump(report, open(args.out, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
