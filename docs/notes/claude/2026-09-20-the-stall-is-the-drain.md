# The long tail: what a stalled shard actually is

2026-09-20. Six shards of the 2026-09-19 bisect and restore grid ended with
`STALLED: no game finished in 1200s`, each reporting 255 of 256 games. The
obvious reading -- one pathological game that runs for twenty minutes -- is
wrong, and the fix that follows from it would have been wrong too.

## What the stall measures

`--stall-timeout` is **the gap between finishes across all workers**, not
the length of any one game. The comment in `benchmark.py` says so, and it
was right to: a slow game is fine while something else is completing.

But at the END of a shard that property inverts. With four workers and one
game left, the gap between finishes IS one whole game, with nothing running
alongside it to reset the clock. Every one of the six stalls reported 255 of
256 -- each lost exactly the last game. The timeout was measuring the drain,
not a hang.

## Whose games are slow

Every stalled shard was an arm against a pre-2026-09-12 anchor (`bc5ef93`,
`c997940`). Those bots predate the access rewrite, run `VALUE_RADIUS` 3 and
still carry the region-margin terms, and they were playing on a shared
runner. Locally I could not reproduce anything close:

| | games | median | max |
| --- | ---: | ---: | ---: |
| self-play, seeds 46000-46031 | 32 | 32.1 s | 54.1 s |
| against the `bc5ef93` snapshot | 16 | 36.2 s | 71.6 s |

A 1200 s game is 17x the slowest I can produce. The stalls are a slow tail
on a contended runner meeting a timeout designed for a hang.

## Two changes

**1. The stall floor adapts to the games being played**:
`max(--stall-timeout, 8 x the slowest game finished so far)`. It is still a
hang detector -- the four-hour ablation that this timeout was built for was
*unbounded*, not slow -- and it no longer fires on the drain.

**2. A separate search budget inside the event sandbox**
(`SurvivalPrior.sandbox_states`, 2000 against `max_states` 20000). Measured
over three self-play games, 2275 decisions:

| | nodes |
| --- | ---: |
| all planner nodes | 4,022,076 |
| ... at the top level | 1,628,783 (40%) |
| ... inside the sandbox | 2,393,293 (60%) |
| worst decision, top level | 19,661 |
| worst decision, sandbox | **510,698** |

Every sandbox fork built a planner with the full budget, so one decision
could spend half a million nodes searching positions that may never happen.
At 2000:

| | before | after |
| --- | ---: | ---: |
| worst decision | 530,359 nodes, 4.30 s | **131,535 nodes, 1.38 s** |
| all planner nodes, three games | 4.02M | **1.63M** |
| four whole games (turn and VP) | -- | **identical** |

## What it does not do, stated plainly

**Whole-game time barely moves**: over the same 32 seeds, median 32.1 s ->
31.2 s and p90 41.4 s -> 38.7 s, inside the noise of a parallel scan (one
seed read *slower* by 5 s, which is scheduling, since the games are
identical). Planner nodes are 60% of the planner's cost, and the planner is
not most of a game -- `delta` and `country_value` are.

So this bounds the tail; it does not make the bot fast. The stall fix is the
adaptive floor. The budget is worth having because a decision that spends
half a million nodes on hypotheticals and changes no outcome is waste
whatever the clock says.

## The corpus is not the oracle here

`test_parity_corpus` reproduces unchanged -- and so it does with
`sandbox_states=1`, which would cripple the search. The corpus positions
rank a single decision, and the sandbox planners they build never reach even
2000 nodes. **A negative control caught that**: the measurement that mattered
was whole games, where the budget does bite and the outcomes are identical.
