# Why access moved from -0.011 to -0.055

Two readings of the same question, "what does the bot lose without
`access`?", disagree by about 2.7 combined standard errors. Both played
against `bc5ef93`:

| reading | run | seeds | base vs bc5ef93 | access off vs bc5ef93 | paired |
| --- | --- | ---: | ---: | ---: | ---: |
| the 2026-09-24 sweep (`ablate-access`) | 35937042894 | 1150 | 0.540 | 0.530 | -0.011 [-0.032, +0.011] |
| the deletion (`access-deleted`) | 36253272931 | 2048 | 0.581 | 0.526 | **-0.055 [-0.071, -0.039]** |

## What was ruled out

- **An accounting defect in the sweep.** It predates the pooling fixes of
  #55, but its data is clean. Each arm lost one seed to a stalled shard,
  and 1150 of 1151 seeds paired.
- **A deletion that did more than `access = 0`.** The branch and the
  parent at `access` 0.0 rank all 178 sampled corpus positions
  identically ([the deletion note](2026-09-26-deleting-access.md)).

## What the levels say

The access-OFF arm scored about the same in both runs, 0.530 and 0.526.
It is the base that moved, from 0.540 to 0.581. Since the sweep, the bot
with access has gained about four points against `bc5ef93`, and the bot
without it has not. Between the two runs, play changed in these ways:

- `region` 1.3 -> 2.6 (#50);
- `military` 1.0 -> 2.0 (#51);
- the space abilities were folded (#52);
- event choices were priced by board value (#61).

The first two are each worth several points (the phase-2 grid), and
`region` is the term most plausibly dependent on `access`. A doubled
region tier rewards reaching the battlegrounds that flip it, and `access`
is what prices reaching them.

## The test, and the rule before the number

Two arms play the current code (`src` is byte-identical to `e434b93`,
the access run's base) with the sweep-era weights `region` 1.3 and
`military` 1.0. They use the SAME seeds as the deletion run,
140000-142047 plus reserve 142100-142227, against `bc5ef93`, with waves
off:

- `oldw-base`: `{region: 1.3, military: 1.0}`;
- `oldw-access-off`: `{region: 1.3, military: 1.0, access: 0.0}`,
  compared to `oldw-base`.

Read the paired access effect at the old weights, and compare it with
-0.055 at the new weights on the same seeds. Every arm is played on
identical seeds, so the interaction (the difference of the two
differences) can be computed seed by seed from the four arms' shard
reports, across the two runs.

1. **Old-weights effect covers -0.011 and excludes -0.055**, or the
   seed-level interaction has a confidence interval excluding 0: the
   region/military change is what made `access` load-bearing. `access`
   stays. The sweep was right about its own bot and should not have been
   read forward onto a re-weighted one.
2. **Old-weights effect is also near -0.055** (its CI includes -0.055
   and excludes -0.011): region/military is NOT the cause. Next is a
   bisect over #52 and #61 (#61 prices event choices through
   `country_value`, which includes `access`).
3. **In between** (the CI includes both): not resolved at this sample.
   Say so, and do not pick.

A side reading that comes free: `oldw-base` against the deletion run's
`access-base` on the same seeds prices the region/military change itself,
with access in.

## The reading

(Filled in at read time.)
