# Drift panel 2026-09-24: every anchor is behind us now

Run 36014499810 (`drift.yml` on `main@351fa7a` -- post PR #47, the
planner at `hand_assignment` 0 and `reply_ops` still present but dead;
both are inert, so this is the shipped bot of its day). The designed
five-anchor panel, 1024 seeds each, level readings, no waves, default
block 6000-7023, italy/austria books. All five verdicts `ok`, and one
shard (`bc5ef93 [3/8]`) flaked mid-run -- the 255-of-256 shape the tail
reserve (PR #49) now fixes for experiments; drift carries no reserve
path yet, which is why that arm pooled 1023.

| anchor | score | one-sided 95% | verdict |
| --- | ---: | --- | --- |
| `v0.1.0` | 0.582 | [0.565, 0.599] | ok |
| `07d553a` | 0.562 | [0.545, 0.579] | ok |
| `v0.3.4` | 0.547 | [0.531, 0.563] | ok |
| `v0.2.1` | 0.538 | [0.520, 0.556] | ok |
| `bc5ef93` | 0.529 | [0.512, 0.546] | ok |

## What changed since the panel was designed

`drift.yml`'s header still records the 2026-09-19 world: *"v0.2.1 is the
strongest tag, and the one main still trails"*, and `bc5ef93` *"beats
main by 0.034"*. Both are inverted now, and measurably so -- every one
of the five intervals sits above 0.500, including the two that used to
lead. The canary's rule ("an upper bound below 0.500 is a measurable
loss") has nothing to flag and nothing to locate: **no full-list dispatch
is needed**.

What moved in between is documented where it landed: the fitted country
weights shipped (+0.054 [+0.031, +0.078], run 35614516089), the region
margin was deleted, `vp_swing` went to its measured peak at 3.0. This
reading is the aggregate of that stretch against the standing panel.

## What this does not settle

Levels are not comparable across blocks: the header's 0.466 and 0.483
readings came from other dispatches' samples, so "inverted" is a
statement about two readings of the same instrument, not a paired
comparison. Nothing here attributes the reversal to any one change -- it
is the whole shipped stack. And a panel of five detects; it does not
locate. Nothing flagged, so nothing needed locating.
