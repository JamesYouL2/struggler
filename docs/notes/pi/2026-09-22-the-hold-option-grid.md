# The hold-option grid: nothing above 0 anywhere, and 1.0 costs

Run 35753235236 (`hold-option-base` / `-025` / `-05` / `-10`), block
74000-75023 against `bc5ef93`, 1024 paired seeds per arm. Both waves
played for every arm -- the interim looked at half the block and settled
nothing -- so this is the full block, pooled by the run's `collect`
step. The decision rule was pre-registered in the arms' own `context`
before dispatch and is quoted below unchanged.

| arm | vs `hold-option-base` (paired) | one-sided 95% | level vs `bc5ef93` |
| --- | ---: | --- | ---: |
| `hold-option-base` | -- | -- | 0.555 [0.538, 0.572] |
| `hold-option-025` | -0.004 | [-0.012, +0.005] | 0.551 |
| `hold-option-05` | -0.005 | [-0.018, +0.007] | 0.550 |
| `hold-option-10` | **-0.031** | **[-0.047, -0.016]** | 0.524 |

## The pre-registered rule, and which branch fired

As registered: *"a peak anywhere with its paired lower bound above 0
means the flexibility is worth pricing and the peak value ships (gate
first, then a MINOR bump); monotone rising through 1.0 means the peak is
at or above 1.0 and the next question is a grid above it; every arm at
or below 0 means ruling 3's term does not go into the live hold pricings
at any size tested."*

**The third branch fires.** No paired lower bound clears 0; the trend
falls rather than rises; all three point estimates are at or below 0;
and 1.0 is measurably harmful. So `hold_option` stays 0 in the live hold
pricings -- Ask Not, the hand attacks, the Missile Envy and Aldrich
picks all read `hold_value`. No gate, no bump, and no grid above 1.0:
a monotone rise is what that question needed and this is its opposite.

## What this does not settle

- **Whether the premium belongs in the planner's hold-slot demand.**
  Pre-registered as untestable here: only the assignment planner (step
  3) moves `value_as_held`'s slot price independently of the live hold
  terms, and the grid tested the live terms only. The one hint for step
  3 is that a full card's Ops of flexibility actively hurts: if the slot
  demand prices flexibility at all, it is not up there.
- **Sizes below 0.25.** Nothing is proven zero -- 0.025's interval still
  reaches +0.005. The statement is that every size tested reads
  flat-to-negative, which is not the same statement.
- **Levels do not travel.** `hold-option-base` at 0.555 [0.538, 0.572]
  says shipped HEAD is measurably ahead of `bc5ef93` *on this block*.
  The 68000 block read the other way on 2026-09-21
  (`docs/notes/claude/2026-09-21-the-fit-clears-on-a-fresh-block.md`);
  only paired differences on one block compare.

The orphan run 35752606270 (wave-2 base shards only, two readings of it
in [the status note](2026-09-22-status-the-grid-in-flight.md)) is
redundant against this reading: the verdict run played every shard
itself.

## What changes

Nothing in play. `hold_option` was 0 and stays 0, so the outcome of the
grid is a term *not* shipped. The three places that said "waiting on its
grid" now record its answer: `docs/STRATEGIC_AI.md`, the
`UNTUNED_WEIGHTS` comment in `policy.py`, and the `hold_option` entry in
`models/provenance.json`.
