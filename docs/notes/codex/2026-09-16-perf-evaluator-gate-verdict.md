# 2026-09-16 — Perf evaluator gate verdict: memoised route_weight, empty-side guards

`a904c7e` perf(evaluator): memoise `route_weight`, skip empty-side access
walks. 1.33–1.54x measured per game, behavior-identical by construction.

## What changed (3 edits, `evaluator.py` only)

- `route_weight` memoised — pure in its args, ~6M calls over a handful of
  distinct keys.
- Route counting in `access` switched from genexpr-sum to a manual loop
  (integer-exact).
- `country_value` skips each side's access walk when that side holds
  nothing there (`x False` is 0.0 for these finite sums, so the
  substitution is bitwise-exact).

Measured, same-seed game-time comparison before/after: 1.33–1.54x.
No weight, ranking, or corpus change — no recapture needed or done.

## Gate

Run `35050445243` on `perf/evaluator-tables-fusion` (`a904c7e`),
`decide=0 vary=0`: workflow `success`, gate job `success`. That IS the
verdict per the project's polling rule — with one caveat: the run's logs
have since expired (`gh run view --log` returns empty), so the literal
`ACCEPTED` line was never re-eyeballed after the fact. Basing the merge on
workflow+job success plus the behavior-identical construction, the green
full suite (863 passed on the branch), and green CI `tests` on `main`
after landing.

## Landing anomaly worth recording

`a904c7e` reached `origin/main` linearly — no merge commit, unknown actor
(possibly the maintainer pushing directly). So there was no branch left to
merge: `main`, `origin/main`, and `perf/evaluator-tables-fusion` all point
at `a904c7e`. This note is the missing verdict record for that landing.
The one-verdict-per-branch / never-merge-before-ACCEPT discipline is
unaffected — it just arrived without the usual merge commit.
