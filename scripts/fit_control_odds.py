#!/usr/bin/env python
"""Fit P(a side controls a country when its region scores) under each
candidate form, and score every form on seeds it was not fitted on.

Reads the rows `scripts/measure_control_odds.py` writes. Every form is a
logistic regression over a different transform of the same measured features,
so the forms differ only in SHAPE and compete on held-out log-loss:

    table         P by (controller now, stability), smoothed -- the baseline,
                  and the shape CONVERSION_P and the retention table already have
    A reciprocal  1/(1+c_me), 1/(1+c_opp)    the maintainer's division, made finite
    B share       log(1+c_opp) - log(1+c_me) the contest share (1+c_opp)^k / sum, one k
    C exponential exp(-c/lambda), lambda from a grid
    D linear      c_me, c_opp, reach
    D full        D linear with stability and controller as categories

and each of A-D again with `over_me` and `over_opp` added, which is the
maintainer's question of whether overprotection moves the odds beyond the Ops
it adds to a break.

The split is by seed parity (even fits, odd scores), so a form cannot win by
memorising one game's correlated rows. The rows' features are small integers,
so they are grouped into distinct feature combinations with counts, and the
fit is weighted Newton over the groups: seconds, in pure Python.

    python scripts/fit_control_odds.py logs/control-odds/rows.jsonl.gz --horizon 1

It reports fit quality, not what the formula should be.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections import defaultdict

KEY = ('controller', 'stability', 'c_me', 'c_opp', 'over_me', 'over_opp', 'reach_me', 'reach_opp')
LAMBDAS = (0.5, 1.0, 2.0, 3.0, 4.0, 6.0)


def load(path, horizon: int, battlegrounds_only: bool = True):
    """Resolved rows at `horizon` as {'train'|'test': {feature key: [n, successes]}},
    and how many were censored."""
    groups = {'train': defaultdict(lambda: [0, 0]), 'test': defaultdict(lambda: [0, 0])}
    censored = 0
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f:
        for line in f:
            row = json.loads(line)
            if row['horizon'] != horizon or (battlegrounds_only and not row['battleground']):
                continue
            if row['outcome'] is None:
                censored += 1
                continue
            cell = groups['test' if row['seed'] % 2 else 'train'][tuple(row[k] for k in KEY)]
            cell[0] += 1
            cell[1] += row['outcome'] == 'me'
    return groups, censored


def _over(r):
    return [r['over_me'], r['over_opp']]


def _reach(r):
    return [float(r['reach_me']), float(r['reach_opp'])]


def _categories(r):
    return ([float(r['stability'] == s) for s in (2, 3, 4)]
            + [float(r['controller'] == 'me'), float(r['controller'] == 'them')])


FORMS = {
    'A reciprocal': lambda r, lam: [1 / (1 + r['c_me']), 1 / (1 + r['c_opp'])],
    'B share': lambda r, lam: [math.log1p(r['c_opp']) - math.log1p(r['c_me'])],
    'C exponential': lambda r, lam: [math.exp(-r['c_me'] / lam), math.exp(-r['c_opp'] / lam)],
    'D linear': lambda r, lam: [r['c_me'], r['c_opp'], *_reach(r)],
    'D full': lambda r, lam: [r['c_me'], r['c_opp'], *_reach(r), *_categories(r)],
}
for _name, _fn in list(FORMS.items()):
    FORMS[_name + ' +over'] = (lambda fn: lambda r, lam: [*fn(r, lam), *_over(r)])(_fn)


def _sigmoid(z: float) -> float:
    z = max(-35., min(35., z))
    return 1 / (1 + math.exp(-z))


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [[*row, b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        if abs(m[col][col]) < 1e-15:
            continue
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.] * n
    for r in reversed(range(n)):
        if abs(m[r][r]) >= 1e-15:
            x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def _design(groups, fn, lam):
    return [([1., *map(float, fn(dict(zip(KEY, key, strict=True)), lam))], n, s)
            for key, (n, s) in groups.items()]


def _nll(design, beta, ridge):
    total = ridge * sum(b * b for b in beta[1:]) / 2
    for x, n, s in design:
        p = min(max(_sigmoid(sum(b * v for b, v in zip(beta, x, strict=True))), 1e-12), 1 - 1e-12)
        total -= s * math.log(p) + (n - s) * math.log(1 - p)
    return total


def fit(groups, fn, lam=None, ridge: float = 1e-3, iters: int = 60) -> list[float]:
    """Weighted logistic regression by Newton's method with backtracking.
    The small ridge keeps separable cells (a country nobody can break) from
    sending a coefficient to infinity; the intercept is not penalised."""
    design = _design(groups, fn, lam)
    p = len(design[0][0])
    beta = [0.] * p
    loss = _nll(design, beta, ridge)
    for _ in range(iters):
        grad = [0.] * p
        hess = [[0.] * p for _ in range(p)]
        for x, n, s in design:
            mu = _sigmoid(sum(b * v for b, v in zip(beta, x, strict=True)))
            r, w = s - n * mu, n * mu * (1 - mu)
            for i in range(p):
                grad[i] += r * x[i]
                wi = w * x[i]
                row = hess[i]
                for j in range(i, p):
                    row[j] += wi * x[j]
        for i in range(p):
            if i:
                grad[i] -= ridge * beta[i]
                hess[i][i] += ridge
            hess[i][i] += 1e-12
            for j in range(i):
                hess[i][j] = hess[j][i]
        step = _solve(hess, grad)
        scale = 1.
        while scale > 1e-6:
            trial = [b + scale * d for b, d in zip(beta, step, strict=True)]
            trial_loss = _nll(design, trial, ridge)
            if trial_loss <= loss:
                break
            scale /= 2
        else:
            break
        converged = loss - trial_loss < 1e-10 * max(1., abs(loss))
        beta, loss = trial, trial_loss
        if converged:
            break
    return beta


def predictor(beta, fn, lam):
    def predict(key):
        x = [1., *map(float, fn(dict(zip(KEY, key, strict=True)), lam))]
        return _sigmoid(sum(b * v for b, v in zip(beta, x, strict=True)))
    return predict


def table_predictor(groups, alpha: float = 1.):
    """P by (controller, stability), Laplace-smoothed toward the controller's rate."""
    by_cell, by_controller = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for key, (n, s) in groups.items():
        r = dict(zip(KEY, key, strict=True))
        for table, k in ((by_cell, (r['controller'], r['stability'])), (by_controller, r['controller'])):
            table[k][0] += n
            table[k][1] += s

    def predict(key):
        r = dict(zip(KEY, key, strict=True))
        n0, s0 = by_controller.get(r['controller'], (0, 0))
        prior = (s0 + alpha) / (n0 + 2 * alpha)
        n, s = by_cell.get((r['controller'], r['stability']), (0, 0))
        return (s + alpha * prior * 2) / (n + 2 * alpha)
    return predict


def score(groups, predict) -> tuple[float, float, int]:
    """Mean log-loss and Brier score per row."""
    n_total, ll, brier = 0, 0., 0.
    for key, (n, s) in groups.items():
        p = min(max(predict(key), 1e-12), 1 - 1e-12)
        ll -= s * math.log(p) + (n - s) * math.log(1 - p)
        brier += s * (1 - p) ** 2 + (n - s) * p ** 2
        n_total += n
    return ll / n_total, brier / n_total, n_total


def calibration(groups, predict, bins: int = 10):
    cells = [[0, 0, 0.] for _ in range(bins)]
    for key, (n, s) in groups.items():
        p = predict(key)
        cell = cells[min(bins - 1, int(p * bins))]
        cell[0] += n
        cell[1] += s
        cell[2] += p * n
    return [(i / bins, n, s / n, sp / n) for i, (n, s, sp) in enumerate(cells) if n]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('rows')
    ap.add_argument('--horizon', type=int, default=1)
    ap.add_argument('--all-countries', action='store_true')
    ap.add_argument('--out', help='write coefficients and scores here as JSON')
    args = ap.parse_args(argv)
    groups, censored = load(args.rows, args.horizon, battlegrounds_only=not args.all_countries)
    train, test = groups['train'], groups['test']
    if not train or not test:
        print('no resolved rows on one side of the seed split', file=sys.stderr)
        return 1
    results = []
    predict = table_predictor(train)
    results.append({'form': 'table', 'lam': None, 'beta': None, 'params': None,
                    'train': score(train, predict)[0], 'test': score(test, predict)})
    for name, fn in FORMS.items():
        best = None
        for lam in (LAMBDAS if name.startswith('C') else (None,)):
            beta = fit(train, fn, lam)
            train_ll = score(train, predictor(beta, fn, lam))[0]
            if best is None or train_ll < best[0]:
                best = (train_ll, lam, beta)
        train_ll, lam, beta = best
        results.append({'form': name, 'lam': lam, 'beta': beta, 'params': len(beta), 'train': train_ll,
                        'test': score(test, predictor(beta, fn, lam))})
    results.sort(key=lambda r: r['test'][0])
    table_test = next(r for r in results if r['form'] == 'table')['test'][0]
    print(f'horizon {args.horizon}: {sum(n for n, _ in train.values())} train rows, '
          f'{results[0]["test"][2]} test rows ({len(train)} / {len(test)} distinct), {censored} censored')
    print(f'\n{"form":24}{"lambda":>7}{"params":>7}{"train LL":>10}{"test LL":>10}'
          f'{"vs table":>10}{"Brier":>8}')
    for r in results:
        ll, brier, _ = r['test']
        print(f'{r["form"]:24}{r["lam"] if r["lam"] is not None else "":>7}{r["params"] or "":>7}'
              f'{r["train"]:>10.4f}{ll:>10.4f}{ll - table_test:>+10.4f}{brier:>8.4f}')
    for r in results:
        if r['beta'] is not None:
            print(f'  {r["form"]}: beta = [' + ', '.join(f'{b:+.3f}' for b in r['beta']) + ']')
    top = results[0]
    fn = FORMS.get(top['form'])
    best_predict = table_predictor(train) if fn is None else predictor(top['beta'], fn, top['lam'])
    print(f'\ncalibration of "{top["form"]}" on the test seeds:')
    print(f'{"bin":>6}{"n":>8}{"observed":>10}{"predicted":>11}')
    for lo, n, observed, predicted in calibration(test, best_predict):
        print(f'{lo:>6.1f}{n:>8}{observed:>10.3f}{predicted:>11.3f}')
    print('\n  Lower test log-loss is a better SHAPE for P(control at scoring).'
          '\n  It is not a strength measurement, and nothing here is wired into the bot.')
    if args.out:
        with open(args.out, 'w') as f:
            json.dump({'horizon': args.horizon, 'censored': censored, 'results': results, 'key': KEY},
                      f, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
