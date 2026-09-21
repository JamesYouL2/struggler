# Deleting `battleground`: what shipped, and the proof it is the measured bot

2026-09-21. The landing record for step 4 of
[the VP rebuild plan](2026-09-20-finishing-the-vp-rebuild.md).

**The reading is not here.** Run 35614516089 (`fit-fresh-base` /
`fit-fresh-on`, block 68000-69023 against `bc5ef93`, paired) is read in
[the fresh-block note](2026-09-21-the-fit-clears-on-a-fresh-block.md),
which pools it with the 64000 block to +0.038 [+0.022, +0.055] and shows
their 0.031 difference is 1.5 SE -- ordinary sampling error, not one block
being right and the other wrong. This note had its own copy of that
reading until the two were compared; a second telling of one measurement
is the shape this repo keeps getting bitten by, so it was cut rather than
kept "for completeness".

What matters here in one line: **paired +0.054 [+0.031, +0.078] over 1020
shared seeds, lower bound above the zero pre-registered in the arm's own
`context` before dispatch.** Step 4 goes ahead; the refit branch the plan
named as the alternative is not taken.

## What ships

`country_vp_scale` ships at **2.795**, and the guessed tiers are deleted:
`StrategicWeights.battleground`, `StrategicWeights.control`,
`importance`'s tier fallback and `country_value`'s un-fitted half. The
fitted branch is now the only branch; `_fitted_country_value` is folded
into `country_value` because there is no longer a second implementation
to be a second implementation *of*.

**2.795, not 2.7949857573867254.** The file's `matched_scale` is the
long one, and it is not what was measured: the arm was dispatched with
`{"country_vp_scale": 2.795}` and three dispatches across two blocks all
played that truncation. Shipping the full-precision value would ship a bot
no arm has ever played, for no reason -- rankings are decided by strict
comparison, so the difference is not nothing, it is just unmeasured. The
truncation is now the weight and `matched_scale` is provenance for where
it came from.

The parity corpus is **re-captured in this commit**, which is the first
re-capture since the fitted weights existed. It had to be: its records
pin `country_vp_scale: 0.0` and two weights that no longer exist, so every
record was a recording of a code path being deleted. See the commit for
the before/after delta.

## The deletion IS the arm, demonstrated rather than argued

The arm did not play this code. It played `origin/main`'s tree
(5de60d0, `src` 3e15825) with `--bot-weights {"country_vp_scale": 2.795}`.
What is being merged deletes the tier branch outright and bakes the scale
into the default. Those are the same bot only if the un-fitted branch was
genuinely unreachable at a non-zero scale -- which is the claim the whole
deletion rests on, and "it should be" is not a measurement.

So it was measured. The parity corpus was re-captured on the pre-deletion
tree with the arm's override applied, and compared with the corpus this
branch ships:

| | measured config (5de60d0 + override) | shipped (28adb67, tiers deleted) |
| --- | ---: | ---: |
| records | 355 | 355 |
| identical position, side and kind | — | **355 / 355** |
| identical full ranking (values, keys, order) | — | **355 / 355** |
| identical country/region/ops/event tables | — | **355 / 355** |

**Zero differences, bit for bit.** Same games reached from the same seeds,
same decisions, same numbers. The deletion is not "equivalent up to
floating point"; it is the same bot, so the +0.054 [+0.031, +0.078]
transfers to the merge candidate without an argument in between.

The two commits stacked on top do not move it either: the strict
weights-load cannot change play, and the sandbox's potential term is inert
at `potential = 0`, which the corpus passing unchanged on 15caae4 is the
proof of.

## What this does NOT settle

- **The weights are still fitted on `598e4d1`**, two structural changes
  back. That argument for a refit was never about the sign; it was about
  how much more there is. It is now a *potential gain on top of a shipped
  one*, not a rescue of an unshipped one, which makes it a lower priority
  than it was this morning and a better-posed question.
- **Nothing about the region layer.** Step 5 -- the `potential` term and
  the sandbox gap in `_delta`'s contract -- is untouched and still needs
  its own 1024-seed verdict. The fit replaces `battleground`; it does not
  replace `region_potential`, and the 2026-09-18 measurement that removing
  the region term under the fitted weights costs 0.067 still stands.
- **The deletion itself is not separately measured.** It is arithmetically
  the arm: with `country_vp_scale` non-zero, `country_value` already took
  the fitted path and `access` already threaded its side, so removing the
  dead branch cannot move a value. The corpus re-capture is what proves
  that claim rather than asserting it.
