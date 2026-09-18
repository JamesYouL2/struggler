# Fitted fixed country weights, proportional to turn and deck

2026-09-18. The maintainer's choice, after
[the linear-weights note](2026-09-18-the-potential-as-per-position-linear-weights.md):
fixed per-country weights, proportional to the turn-and-deck scoring mass,
fitted to the exact potential rather than guessed. The reason given is
consistency: they are deterministic, explainable, and cost nothing. Europe
Control is priced at a fixed 40 VP, with experiments allowed. Branch
`feat/fitted-country-weights`.

## What was built (the four steps)

1. **The fit.** `scripts/fit_country_weights.py fit` plays self-play games
   and records every real decision's board and that side's scoring masses
   by horizon. For each country and side it computes the exact
   mass-weighted gain of controlling the country instead of leaving it
   uncontrolled. That gain is the tier change from `forecast.tier_weights`
   plus the 10.1.2 bonus. It then fits `a[c][s]` by least squares against
   the mass. The output is `src/struggler/data/fitted_country_weights.json`,
   recording the revision, the generator's hash, the seeds and the
   in-sample R².
2. **The wiring.** `StrategicWeights.country_vp_scale`, in board units per
   VP. At 0 (as shipped) nothing changes: the old path runs untouched, and
   the parity corpus reproduces. Set, `importance` becomes
   `scale * (a[c][s] * M_region + sea[c] * M_sea)`, where the masses are the
   same `urgency` the tiers already multiplied and Southeast Asia's own
   payout (2 for Thailand, 1 otherwise) is exact. `country_value` prices
   our control at our weight and theirs at theirs. It stays zero-sum across
   the seats (tested).
3. **Europe.** `europe_control_vp` is 40, the whole track, as ruled. It is
   a weight only so the arms can try 20 and 60. The fit itself was made at
   40.
4. **The auditor.** `scripts/fit_country_weights.py check` reports, on
   held-out games, the R² of the fixed weights against the exact gains and
   the VP a region loses when the fixed favourite differs from the exact
   best.

## The fit (16 games, seeds 40000-40015, 4002 positions)

Held-out audit (8 games, seeds 41000-41007, 2806 positions):

| region | R² in-sample | R² held-out | regret mean / p90, VP per unit mass | exact best gain |
| --- | ---: | ---: | --- | ---: |
| Europe | 0.84 | **0.63** | 0.114 / 0.106 | 3.94 |
| Asia | 0.96 | 0.96 | 0.000 / 0.000 | 3.08 |
| Middle East | 0.98 | 0.98 | 0.072 / 0.218 | 1.67 |
| Africa | 0.98 | 0.98 | 0.064 / 0.186 | 1.95 |
| Central America | 0.98 | 0.97 | 0.078 / 0.336 | 2.67 |
| South America | 0.97 | 0.96 | 0.042 / 0.117 | 2.02 |

- **Europe is the one region a fixed weight does not describe.** Control
  at 40 VP is worth a great deal near the threshold and almost nothing far
  from it. The mean pick regret stays small (3% of the best gain) because
  the favourite is usually right; the R² says the level is wrong often.
  That is what the Europe arms test.
- **Regret here is top-pick only, over every member of the region,
  reachable or not.** It is a floor on the shape error, not what a game
  loses.

The weights also fix the defect the provenance ledger records against
`battleground` ("importance() returns the same 9.31 for Iraq, South Korea,
Saudi Arabia and Israel"):

- **Battlegrounds now differ.** Europe's run from Poland (4.27 VP per unit
  of mass to the US) down to Italy (2.55). The Middle East's are all about
  1.6.
- **The sides differ.** Poland is worth 4.27 to the US and 2.17 to the
  USSR: a US Poland breaks Soviet domination. West Germany, Cuba and
  Mexico are worth more to the USSR, which collects the adjacency bonus
  there.
- **The ratio is steeper.** A battleground is worth 6-8x a plain country,
  against the tiers' 3.3x.

`matched_scale` is 2.79: at that scale, importance's total over the fit
sample equals the tiers'. It is a level-matching choice, not a
measurement.

## Experiments

Arms on seeds 32000-33023, 1024 each, against this branch's defaults (fit
off, which is the hand-safety fixes' code). Every arm after the first is
paired with the first (`compare_to`):

- `fitted-matched`: the fit at 2.79;
- `fitted-half` and `fitted-double`: its size, at 1.40 and 5.59;
- `fitted-no-region`: the old region term off. The fitted weights already
  carry tier changes, so that term may count them twice;
- `fitted-eu20` and `fitted-eu60`: Europe Control at 20 and 60 VP.

Plus one Europe-only arm, dispatched separately:

- `europe-curve-k10`: Europe as `20 * tanh(net VP / 10)`, with Control at
  exactly the +20 of an automatic victory (maintainer). The fit is off, so
  the arm is isolated.

**Why k is a judgment.** `scripts/fit_europe_curve.py` tried to fit k to
the exact potential and could not. Over 2130 self-play positions (seeds
40000-40007) no side held or neared Europe Control, so the potential sees
Europe as roughly linear in its current score. k ran to the grid edge (a
straight line), and R² was 0.732 against the tier step's 0.736. At k=10,
domination with two bonus battlegrounds reads 14.3 of 20, and presence
reads 5.8.

**Other regions ("good overall?").** The same script fits `C * tanh(x/k)`
per region:

| region | tier step R² | curve R² |
| --- | ---: | ---: |
| Central America | 0.62 | 0.72 |
| South America | 0.87 | 0.91 |
| Africa | 0.67 | 0.68 |
| Asia | 0.84 | 0.84 |
| Middle East | 0.81 | 0.80 |

Asia and the Middle East fit to a straight line. A curve would help the
small regions, where returns diminish. That is a candidate arm, not yet
run.

## Results (run 35367356155, 1024 seeds 32000-33023, against the fit off)

| arm | score | one-sided 95% | paired vs fitted-matched |
| --- | ---: | --- | --- |
| **fitted-matched (2.795)** | **0.518** | **[0.502, 0.534]** | -- |
| fitted-half (1.40) | 0.482 | [0.465, 0.499] | -0.036 [-0.059, -0.013] |
| fitted-double (5.59) | 0.492 | [0.475, 0.509] | -0.026 [-0.048, -0.004] |
| fitted-no-region | 0.451 | [0.434, 0.468] | -0.067 [-0.089, -0.045] |
| fitted-eu20 | 0.512 | [0.496, 0.528] | -0.005 [-0.009, -0.002] |
| fitted-eu60 | 0.513 | [0.497, 0.529] | -0.004 [-0.007, -0.001] |

- **The fit beats the guessed tiers, measurably**, and at the matched
  scale; half and double both lose. The size is bounded on both sides.
- **The region term is not double counting**; removing it costs 0.067.
  The fitted weights price a country's marginal, while the region term
  prices the tier the region is in now. Both are needed.
- **Europe Control at 40 VP (the ruling) beats 20 and 60**, by a little on
  each side. It is bounded, not just chosen.
- The gain is in the US seat (0.612) more than the USSR (0.424); the
  opponent is the tiers, same code otherwise.

**Default flipped to 2.795** on this branch, gated by its PR against main
(PR #4's hand safety plus the drift CI). PR #6's gate: ACCEPTED, 0.507
+/- 0.036 over 76 seeds.

**The Europe curve (run 35387907944, fit off, k=10): 0.486 [0.471,
0.501]** against the tiers. That leans worse without being measurably
worse, so it is not adopted. `europe_curve` stays in the code, off, for a
different k or for a curve in every region.
