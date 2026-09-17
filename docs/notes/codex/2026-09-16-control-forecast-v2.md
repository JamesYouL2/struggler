# 2026-09-16 — Control forecast v2: the measured logistic reads the board

Still unwired (the forecasts' consumers do not exist yet), so the suite and
corpus need no gate of its own; CI suite runs on the push as usual.

## What changed

`forecast.forecast_controls` no longer maps the board to degenerate
0/1 masses at every horizon. Horizon 0 (a scoring NOW) stays degenerate --
the acceptance criterion is that immediate scoring reproduces the engine's
payout exactly, which a probability cannot. Horizon 1+ reads the September
13 control-odds fits' best shape, "D full +over"
(`docs/notes/claude/2026-09-13-control-odds-fits.md`): a 12-parameter
logistic over exact Ops-to-control under the doubling rule
(`rules_math.ops_to_control`), each side's reach, stability and controller
as categories, and overprotection both ways.

- **Conditioning survives**: the rows resolved only when the region
  actually scored (censored dropped); the fit's P is P(control | the
  scoring happens), which is exactly what the rebuild README requires the
  forecast to be, and the schedule's occurrence masses multiply it -- the
  two are never the same quantity.
- **Both seats agree by construction**: per member, `p_us` and `p_ussr`
  come from the same row-relative function read for each side, so no
  seat's view can mass-idle the other's.
- **Horizon clamp**: the matches cover scoring horizons 1 and 2 only;
  every later opportunity borrows the horizon-2 fit, documented at
  `p_control_at_scoring`, not silent.
- **p_open** takes what the two sigmoids leave, clamped at 0 -- the fit
  is read per side and nothing enforces their sum; the triple always
  sums to one.
- **Same linear-exactness**: `expected_country_bonus` and
  `expected_southeast_asia_payout` are linear in the probabilities, so a
  stochastic forecast prices them exactly. `expected_tier_payout` still
  raises on any stochastic member -- the joint control distribution
  (README's "hardest modeling choice", the count-DP under a documented
  independence approximation being the candidate) is separate work and
  not guessed at here.

## Verification

- Betas verified against source: re-ran `fit_control_odds.py` over the
  recorded rows (`logs/control-odds/20260913-055843/rows.jsonl.gz`,
  192 games); horizon-1 "D full +over" reproduced to the printed digits,
  and the fit's table cells fall where the measured ones do (me
  0.57/0.77/0.86/0.88 vs measured 0.66/0.81/0.89/0.94; `none` 0.43/0.19 vs
  0.44/0.21; `them` 0.22/0.01 vs 0.16/0.012). The beta-to-feature order is
  checked, not assumed -- the first attempt had it backwards and the
  representative rows screamed it.
- Tests: horizon-0 degeneracy preserved; horizon 1/2/5 masses valid and
  summable to one; horizon clamping; representative-board shape pins
  (held > contested; enemy stab-4 ground near-lost; overprotection
  raises the hold, the maintainer's own question, in `over_me`'s
  +1.633).
- The immediate tests (`expected_tier_payout` under every Formosan/
  Shuttle override combination, `region_potential == region_vp` in all six
  regions) must stay untouched and do: they run at horizon 0 only.

## Known limits, named

- Fitted on battleground rows only; non-battleground members read an
  extrapolating function (documented in the module).
- Measured under the OLD policy's games and one deck state; the README
  forbids reading better prediction on those games as strength.
- Horizon clamping means bucket 3 and bucket 5 share the horizon-2 shape.
- No ranking consumes any of it; the two-state merge's
  `retention_p`-compounded consumer is still the live pricing until the
  integrated candidate lands.
