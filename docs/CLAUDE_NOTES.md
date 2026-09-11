

## 2026-09-11 — The gate's time budget: under an hour, and why ten minutes is not close

The maintainer's constraint, recorded because every change that makes a
decision more expensive spends it: **`scripts/gate.sh` must stay under an
hour, and they would prefer ten minutes.** Their own read is that ten is
a pipe dream. It is, on this machine, and the arithmetic says by how
much.

Where it stands. The forward-search gate (`gate-01de83f`) ran **46m09s**
wall, 08:17:38 to 09:03:47, and that was *with* a poke measurement and a
test suite competing for the same eight cores. Uncontended it is nearer
35 minutes. Under the ceiling, not comfortably, and it grew when the
search landed -- the search is per-placement work on the hottest path.

Why ten minutes is not a matter of trimming seeds. `benchmark.ACCEPTANCE`
requires **150 finished games** over at least two disjoint samples, which
is not a number to negotiate: it is what makes the pooled score mean
anything, and cutting it buys speed by removing the gate's only claim.
At a median full game of **76.5 s** (measured, max 248 s) and eight
workers:

    150 games x 76.5 s / 8 workers = 1434 s = 24 minutes

So **24 minutes is the floor at today's game cost**, before step 1's
tables, step 2's checkpoint, or the baseline snapshot. Ten minutes needs
roughly a **2.5x faster game**, or about nineteen cores. Seed count
cannot get there; it is already near the floor the acceptance rule sets.

Where the 2.5x would have to come from, per the profiles above:
`event_value` is ~70 % of an ordinary mid-war decision and
`action_risk` into `defcon.risk` ~67 % of a hazardous late one --
two different paths, each about half the workload, so **optimising
either alone wins about half**. A 2.5x therefore means both, or a native
kernel (docs/RUST_PORT_PLAN.md Option C), which is what that plan is for.

What is worth doing before any of that, in order of value per hour spent:

1. **Keep measuring the gate's wall time and put it in the log.** It is
   not recorded today; this entry had to recover it from file mtimes.
2. **Stop running anything else while a gate runs.** 46 minutes included
   my own contention, and "never time anything while a gate runs" is
   already shape 7 in this file. The same applies to the gate itself.
3. The early stop (`--decide`) already saves ~15 % and no historical
   verdict changed. It is the only free speed taken so far.

The honest summary for the maintainer: **under an hour is met and worth
defending; ten minutes is a port-scale project, not a tuning exercise.**
