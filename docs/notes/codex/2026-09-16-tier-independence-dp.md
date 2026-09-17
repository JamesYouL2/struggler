# 2026-09-16 — Tier expectation: the independence count-DP

Follows the control-forecast-v2 note; still unwired (no consumer), CI
suite on the push, safety gate dispatched per slice.

## What changed

`expected_tier_payout` no longer refuses a stochastic forecast. The tier
payout is a function of FOUR COUNTS (controlled countries and controlled
battlegrounds per side) plus the total battleground count, and that
distribution is exactly convolvable under per-member independence: a
four-count DP over the members, each contributing three outcomes
(US/USSR/uncontrolled, with or without its battleground flag).

- **Degenerate forecasts keep the snapshot path** (`region_vp` minus the
  bonus) -- exactness unchanged, pinned everywhere as before.
- **The DP is pinned degenerate-exact against `region_vp` at every
  Formosan/Shuttle override combination** -- the pin that caught a REAL
  pre-existing defect: `expected_country_bonus` ignored Formosan
  promotion, while `region_vp` and the engine both pay the promoted
  Taiwan in the 10.1.2 bonus. The bonus now takes the overrides and
  threads them identically in every path (a Formosan-promoted Taiwan
  counts as a battleground; a Shuttle-ignored member contributes
  nothing anywhere).
- **Europe Control** stays the auto-victory branch: `control_vp is
  None` only for Europe, so the DP maps it to +/-`EUROPE_CONTROL_VP`
  (40, via stakes' `AUTO_VICTORY_VP` -- "40 VP for now" was already the
  live value and needed no change).
- Overrides ride the SNAPSHOT, not the outcome (a Formosan-promoted
  Taiwan is a battleground in every draw; a Shuttle-ignored member reads
  uncontrolled in every draw) -- documented in the module.

## The approximation, named

Members are independent draws over (US, USSR, uncontrolled). The README
contemplates exactly this as a first implementation and an assumption:
players pursue a region across several countries with one Ops budget, so
the draws are correlated in truth -- independence UNDERSTATES domination
tail risk. What it buys: no per-country tier share to double-count, no
modal substitution, and an exact expectation given the approximation.
Calibrating the DP against correlated truth is a measurement (the
h0-calibration run does this against realized payouts); it is not
computed here.

## Checks

- `test_stochastic_tier_expectation_is_the_named_independence_dp`:
  simplex sums to 1 at h=1/2/5 in every region and override combination;
  the degenerate-through-DP == region_vp-snapshot pin.
- `test_stochastic_tier_matches_monte_carlo_independence`: 4096-draw MC
  on Asia agrees with the DP within 0.08.
- Forecast tests 18/18, ruff clean; full suite via CI on push.

## Measurement: is the degenerate horizon-0 read the right imminent price?

The maintainer asked whether "horizon == 0 doesn't need to be exactly 1".
Measured over 40 strategic-vs-strategic games (seeds 7000-7039, script
`logs/forecast-h0/forecast_calibration.py`), for every region scoring that
actually fired, comparing at turn start:

```
region                  n   |errA|  |errB|    errA    errB
EUROPE                 67   1.925   2.650   -0.343  -1.022
ASIA                   83   1.831   2.871   -0.072   1.358
MIDDLE_EAST            81   1.963   2.279   -0.160   0.518
AFRICA                 39   1.179   1.867   -0.205  -0.197
CENTRAL_AMERICA        46   2.152   2.685   -0.413  -1.303
SOUTH_AMERICA          45   2.044   2.702   -0.311  -0.421
ALL                   361   1.875   2.544   -0.230  -0.001
```

A = degenerate-now (current board, P=1); B = the fitted h1 forecast with
the DP tier. A wins ABSOLUTE error in every region (1.88 vs 2.54); B is
nearly unbiased where A carries a -0.23 systematic under-read -- the
board moves between turn start and the scoring, and the snap read
ignores everything that happens first. Verdict: keep `horizon 0`
exact-degenerate (the acceptance criterion and the better imminent
price); the imminent-TURN read stays probabilized. The bias is a
consumer-level question (the old policy's `_scoring_weight_uncached`
already shapes bucket 1 differently when the card is held), not a
forecast-level one.

## Where this leaves the rebuild

Both hard modeling pieces the integration step needed now exist: the
schedule masses (buckets 1-3) and a stochastic forecast whose tier
expectation no longer raises. The next named step is the integration
itself -- mass x P(occurs) x discount x E[payout] per opportunity into
the ranking path -- which is the one-corpus-recapture, one-gate step.
