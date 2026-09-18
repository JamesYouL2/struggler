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

Results are added here when the runs report. The winner's default is
then flipped and gated against the branch point.
