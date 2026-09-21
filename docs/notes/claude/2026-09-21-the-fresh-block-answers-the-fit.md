# The fresh block answers it: +0.054 [+0.031, +0.078], and `battleground` goes

2026-09-21. Run 35614516089, `fit-fresh-base` / `fit-fresh-on`, block
68000-69023 against `bc5ef93`, paired. This is step 3 of
[the VP rebuild plan](2026-09-20-finishing-the-vp-rebuild.md), re-run on a
block the fit was neither fitted nor tested on, because
[the 64000 block can no longer give a 1024-seed reading](2026-09-21-fit-vs-bc5ef93.md).

| arm | vs | score | one-sided 95% | seeds | US seat | USSR seat | shards |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| `fit-fresh-base` (fit off) | bc5ef93 | 0.480 | [0.463, 0.497] | 1021 | 0.539 | 0.422 | 8 ok |
| `fit-fresh-on` (`country_vp_scale` 2.795) | bc5ef93 | **0.534** | [0.517, 0.551] | 1023 | 0.580 | 0.489 | 8 ok |

**Paired: +0.054 [+0.031, +0.078] over 1020 shared seeds.**

## The pre-registered rule, applied

From `.github/experiments.json`, written into the arm before dispatch:

> PRE-REGISTERED, before dispatch: paired lower bound above 0 on the full
> 1024 seeds means the fit is a measurable gain and step 4 (deleting
> battleground, control and the un-fitted half of country_value) becomes a
> normal change with an anchored arm behind it; at or below 0 means two
> independent blocks agree it is not measurable, and the refit at current
> main is the next move rather than another block.

The lower bound is **+0.031**. **Step 4 happens**, and the refit branch is
not taken.

Two honest deductions from the rule as written, neither of which changes
the answer:

- It said "the full 1024 seeds" and the reading is **1020**. Four shards
  hit `--max-seconds 9000` and exited 6, which
  [is what that exit code is for](2026-09-20-the-stall-is-the-drain.md):
  the games still running were abandoned, the partial report was written,
  and the pooled arms are 1021 and 1023 seeds with 1020 shared. Four seeds
  short of the pre-registration. At a lower bound of +0.031 this is not a
  knife edge -- it was a knife edge at 64000, which is exactly why that
  block was abandoned -- but the line was drawn at 1024 and it is being
  crossed at 1020, and that is worth writing down rather than rounding away.
- The run's own conclusion is `failure`, for those four shards. The verdict
  came from `collect`, which succeeded; every arm pooled `8 ok`.

## What the two arms say separately, which is not the same thing

The paired difference is the decision. The levels are the diagnosis, and
they say something the 64000 block did not:

- `fit-fresh-base` reads **0.480 [0.463, 0.497]** against `bc5ef93`. The
  upper bound is below 0.500. **HEAD with the fit off is a measurable loss
  to `bc5ef93` on this block** -- where on 64000 the same arm read 0.512
  and where HEAD is generally described as level with that anchor.
- `fit-fresh-on` reads **0.534 [0.517, 0.551]**, clearing 0.500 on its own
  interval, as it did on 64000 (0.530).

So +0.054 is not +0.054 of pure gain over `bc5ef93`. Roughly +0.020 of it
is the fit climbing out of a hole this block digs for the base arm, and
about **+0.034** is what the fitted bot clears `bc5ef93` by outright --
with the wider unpaired interval, since the seats are not differenced.

**This is the block-variance point the shipped anchors keep making**, and
it is why the paired difference is the statistic the rule was written on:
the two arms moved by 0.032 and 0.004 respectively between blocks, and the
paired difference by 0.031. Levels travel badly between blocks; paired
differences travel.

The seat split reproduces: both seats gain (US 0.539 -> 0.580, USSR 0.422
-> 0.489) and the **USSR gains more**, the third block in a row to say so,
and the seat the fit lost in against `07d553a`.

## And the answer to the question the 64000 block could not answer

That block's `+0.023 [-0.001, +0.047]` is now explained. On a fresh block
the same weights read `+0.054 [+0.031, +0.078]`, and the two intervals
overlap heavily: one sample fell low, the other high, and neither is
evidence that the weights changed. **The -0.001 was the block.** Two
independent blocks now agree on the sign; they disagree only on the size,
by about one standard error each way.

See [the shared-seed-block caution](2026-09-18-drift-located-at-v0.2.1-v0.2.3.md)
for why that was worth two dispatches rather than one.

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
