# 2026-09-16 — Factor 1: one-region expected-scoring prototype (Africa)

First deliverable of the value-function rebuild: `bots/strategic/forecast.py`
plus `tests/test_forecast.py` (9 tests). New module, NOT wired into any
ranking -- the old evaluator and its corpus are untouched. Africa first: 18
countries, 5 battlegrounds, tier thresholds that bite, no superpower
adjacency, no Europe auto-victory.

## Interface

`forecast_controls(t, pos, region, horizon)` -> per-member `(p_us, p_ussr, p_open)`.
`expected_country_bonus` (linear, exact under any forecast) +
`expected_tier_payout` (once per region, exact under a degenerate forecast) =
`expected_payout` (`Breakdown(total, bonus, tier)`, US-signed).
`region_potential(..., seat, ...)` signs it for the seat.
`marginal(..., forecast, i, holder)` is potential-after minus potential-before.
`force` builds the after-forecast so call sites never realign members by hand.

## The five README answers, as implemented

1. **Partial influence -> control probability:** current-control threshold
   (the `Position` rule) to degenerate 0/1 mass. Partial progress earns
   nothing yet; the Sep-13 control-odds fits are the curve's evidence, and
   their conditioning (on the scoring occurring) must survive the replacement.
2. **Access / Ops cost / overprotection:** not inputs yet, by design. Access
   gates acquisition, pointwise cost is the influence to tip the margin past
   stability, overprotection currently scores as bare control. Named inputs of
   the next forecast.
3. **Horizon:** accepted and carried, but the first approximation is
   horizon-invariant (current control everywhere). Schedule + per-cycle
   retention shape it later; retention is per scoring cycle, never per turn.
4. **Tiers without multi-count:** computed once per region from the joint
   implied controls through `region_vp`'s own counting (a scratch snapshot,
   no live-path edits); per-country values are derived differences, never
   summed back into a total.
5. **Correlation:** deterministic is exact via the shared board. Stochastic
   raises `NotImplementedError` -- no silent independence approximation
   (misprices domination), no modal substitution (Jensen).

## Checks

Immediate potential == `region_vp` in all six regions (incl. the Europe
stand-in) and == `Board.score_region` under every Formosan/Shuttle override
combination. Synthetic Africa board pins the tier/bonus split exactly (US
Algeria/Nigeria/Zaire + Cameroon flips presence 1 -> domination 4, bonus
fixed at 3, marginal 3.0). Stepwise marginals telescope in either order.
Stochastic forecast: bonus still linear-exact, tier raises. Ruff clean (45
pre-existing hits on HEAD untouched); full suite green (see commit).

## Baseline (pre-integration, 2026-09-16)

`benchmark --expert models/expert_valuations.json --seeds 4000` on the
unwired tree (identical bot to `origin/main`, so this is the main baseline
the end-gate compares against):

- PLACEMENT US: **11 inversions in 11 ranked**; bot order Pakistan > Egypt >
  Iraq > France > South_Korea > Japan > Israel > Mexico > South_Africa >
  Cuba > Panama. Israel-first is still the worst single inversion
  (Israel 7th where the expert ranks it first).
- PLACEMENT USSR: **6 inversions in 5 ranked**; bot order South_Korea >
  Israel > Iraq > Saudi_Arabia > Lebanon.
- ORDER BROKEN x2 (Suez/Arab-Israeli, Marshall/US-Japan), 29 misses
  (tolerance + unpriced cards/footholds).

Safety gate on the unwired branch (expect ~0.5, no behavior change):
run `35108484196`, `decide=1 vary=0` vs `origin/main` `18abdba`.

## Deferred, explicitly

Joint control distribution (the stochastic tier model), schedule/occurrence
mass, Ops-denomination of the potential, residual discount. One rebuild, one
recapture, one gate at the end -- none of that ships until the integrated
candidate is evaluated.
