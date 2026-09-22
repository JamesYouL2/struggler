# The refit at current main: candidate, audit, and the rule before the number

Branch `exp/refit-country-weights` (the candidate commit sits on
`cec39ca`), arm `refit-vs-shipped` = **run 35777206185**, dispatched
2026-09-22 19:58 UTC on seeds 76000-77023 plus held 88000-88127 (1152
seeds), against `cec39ca` -- the same tree minus the refit. Openings
italy/austria (a ref is involved). **The decision rule below was written
and committed before any number was visible**, and lives verbatim in the
arm's own `context`:

> PRE-REGISTERED before dispatch: the refit (fresh
> fitted_country_weights.json fitted at cec39ca -- the shipped file had
> source_revision 598e4d1, two structural changes back -- with
> country_vp_scale at 2.793, round(2.793341679085859, 3), the exact
> default this branch ships) REPLACES the shipped weights iff the
> one-sided 95% lower bound of this arm against the shipped bot (anchor
> cec39ca, the same tree minus the refit) is above 0.500. An interval
> straddling 0.500 keeps the shipped weights -- on identical held-out
> positions the auditor could not rank the fits (R^2 0.635 vs 0.665 in
> Europe, Europe top-pick regret 0.462 both, refit better
> Africa/Asia/Middle East, worse Central/South America), so play decides
> -- and an upper bound below 0.500 keeps them and records why.
> matched_scale chains (it matches the shipped level, not the deleted
> tiers), so this arm tests the SHAPE change from fitting at current-main
> play with the level deliberately held; the new weights and the new
> scale ship together or not at all.

## What the refit is

`scripts/fit_country_weights.py fit --seeds 40000-40015` at `cec39ca`:
16 games, 4645 positions, 390180 country rows. New `a[c][s]`, and
`matched_scale` **2.793341679085859**. It **chains** -- it matches the
level of whatever is shipped, the deleted tiers no longer being the
reference -- so the candidate deliberately moves only the shape. The
scale goes 2.795 to **2.793** as `round(matched, 3)`, the rule
`test_the_shipped_scale_is_the_truncation_every_arm_actually_played`
states: what an arm plays is what ships. In-sample R^2: Europe 0.576,
Asia 0.965, Middle East 0.980, Africa 0.982, Central America 0.979,
South America 0.977.

## The auditor cannot rank the two fits

Held-out, seeds 41000-41007 (2300 positions), **both fits judged on
identical positions** -- the shipped file run through `check` on the same
new positions the refit was audited on:

| region | R^2 refit / shipped | regret mean refit / shipped |
| --- | --- | --- |
| Europe | 0.665 / 0.635 | 0.462 / 0.462 |
| Asia | 0.966 / 0.960 | 0.000 / 0.000 |
| Middle East | 0.980 / 0.981 | 0.050 / 0.053 |
| Africa | 0.987 / 0.988 | 0.048 / 0.058 |
| Central America | 0.979 / 0.976 | 0.086 / 0.053 |
| South America | 0.977 / 0.978 | 0.069 / 0.012 |

Better in Africa, Asia and the Middle East; worse in Central and South
America; Europe a wash at a large shape error *both* fits share -- a
fixed weight cannot describe Control at 40 VP near its threshold, which
is the 2026-09-18 note's finding standing unchanged. These are
regression residuals over positions, not paired games: **nothing here is
a strength claim.** Play decides, which is what the arm is for.

## The candidate state -- all of it ships together or not at all

The refit file, `country_vp_scale` at 2.793, the scale pin in
`test_fitted_country_weights.py`, the ledger's `country_vp_scale` entry
(both fits recorded, the refit named), and the parity corpus re-captured
at 441 records (it follows the bot's play). 21 tests green on the
branch: the fitted-weights module, the provenance ledger, and the full
parity corpus.

## A mistake this step almost kept: `uv run pytest` tested the wrong tree

The first test run in the worktree reported `hold_option` missing from
the ledger and `country_vp_scale` still 2.795 -- both impossible on that
branch, which has no `hold_option` at all. The cause: `uv run pytest`
found no pytest in the worktree venv (the `test` extra was not synced),
fell back to the PATH's pytest -- the main tree's venv -- and imported
the main tree's package. The corpus capture had been right (its records
pin 2.793) because `uv run python` resolves the venv interpreter; only
the bare *command* fell through. Now: `uv sync --frozen --extra test`,
then `./.venv/bin/python -m pytest`, sanity-printing `policy.__file__`
first. The `queue` skill warns about exactly this interpreter-path
class, and the tell was a failure that cannot exist. Read an impossible
failure as wrong-tree evidence before believing it.

## The reading (run 35777206185, pooled 21:21 UTC)

| arm | vs `cec39ca` | one-sided 95% | seats (US / USSR) |
| --- | ---: | --- | --- |
| `refit-vs-shipped` | **0.483** | **[0.468, 0.498]** | 0.556 / 0.410 |

**The rule's third branch fires: the upper bound is below 0.500.** Not
a null -- a measurable loss. The shipped weights stand
(`country_vp_scale` 2.795, the `598e4d1` fit) and the refit is dropped:
PR #41 closed, branch deleted. As registered: "an upper bound below
0.500 keeps them and records why." What the number says, and no more:
even with the level held by `matched_scale`, re-fitting the shape to
current-main play made the bot measurably worse over 1152 paired seeds.
The old shape being two structural changes stale did not make it wrong
-- stale was not broken.

What that does *not* say: why. The auditor could not rank the fits and
play ranked them against the refit -- whether the exact potential is the
wrong target, whether current-main self-play positions under-represent
the states that decide games, or whether the level-holding
`matched_scale` chain moved something the shape did not, is not
identified by this reading. The seat split (US 0.556 / USSR 0.410) is
the one hint: whatever the refit lost, it lost mostly as the USSR.

The "unfinished business" line in the provenance ledger is closed by
this measurement: the weights are now "measured at 2.795, and a refit at
current main read measurably worse" -- a different standing than
"stale".
