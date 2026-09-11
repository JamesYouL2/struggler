# 2026-09-09 — Review of Claude's night plan

Reviewed the uncommitted final section of `CLAUDE_NOTES.md` with repository
HEAD at `c15a603`. Broad agreement: restore the parity baseline, profile on
a quiet machine, and optimize the bot. Claude's reported checkpoint share
of about 4% changes the priority above: folding that diagnostic into full
games is a small cleanup, not the main speed project. The following
qualifications should accompany the plan.

### Measurement and experiment qualifications

1. **Worker elapsed time is not CPU time.** `benchmark.play` measures game
   duration using `time.time()`. Summing those durations and dividing by eight
   measures worker occupancy, not 96% CPU efficiency under contention. Full
   games still dominate the reported gate duration, but historical elapsed
   times do not establish a 2–3x code slowdown without controlled comparisons.
   The 107.8-second profile above identifies candidate hot paths; it is not
   a quiet-machine runtime baseline or evidence of a regression by itself.
2. **Wipe risk is a hypothesis to test.** Empty-country access, vulnerability
   to events, and vulnerability to coups overlap but are not interchangeable.
   The implemented wipe term models a particular coup threat and its target
   count introduces whole-board dependencies. Use annotated positions that
   distinguish those mechanisms and measure runtime before enabling it
   broadly. A group of expert-table misses does not yet prove one cause.
3. **The claim of 16 untested cards overstates the evidence.** There are
   explicit behavior tests for Nuclear Subs, Flower Power, and Shuttle
   Diplomacy, including Shuttle expiration and final-scoring exclusion.
   Some tests set effect flags directly, so activation may still lack
   coverage. Audit activation, resolution, interactions, and expiration
   separately; searching for literal card IDs cannot establish coverage.
4. **Batch gates selectively.** Larger samples can buy more information than
   many small gates. Batch behavior-preserving work after parity is green,
   but keep distinct strategic hypotheses independently measurable. A failed
   batch may contain interacting changes, so bisecting need not identify a
   single culprit. The power table is a useful approximation; low power for
   a three-point change is not complete blindness to that change. Its pooled
   historical variance is not guaranteed for every future comparison.
5. **Run the 32-seed MCTS experiment soon.** The 0.75 score over eight games
   needs confirmation. Compare fixed simulation counts and equal wall-time
   budgets, recording root visits and truncation. This measures search
   promise; profiling determines the opportunity for acceleration. One
   strength experiment should not be the sole criterion for a native port.

The strongest addition is an annotated tactics suite beyond the opening
board. Use expert valuations for fitting and games for validation, with
some annotated positions held out from fitting and model selection. The
opening table alone can be overfit just as readily as a fixed seed range.

### Concrete profiling scope and revised order

Make "several revisions and representative positions" a bounded first pass:
compare `df29bf8` with the parent and result of each suspected transition
(`6ec71d4`, `4e67bf0`, and `7cb9fbe`). Deduplicate overlapping revisions and
verify engine/API compatibility before interpreting comparisons. Use fixed
observations to distinguish implementation cost from changes in game
trajectories; also measure complete games for end-to-end cost. Do not force
an incompatible historical bot onto a newer engine and call that a baseline.

Start with frozen observations covering opening placement, a scoring-card
decision, an ordinary mid-war hand, and a hazardous late-game hand. Run
three unprofiled repetitions per case under the same environment on a quiet
machine, then profile to attribute cost. Record revision, position identity,
elapsed time, CPU time, chosen action, and planner truncation. Expand the
sample if results vary enough to change the optimization priority. This is
a proposed experiment, not a measurement already completed.

Revised sequence:

1. Review intended corpus changes and restore a green baseline.
2. Run the controlled profiling comparisons above.
3. Run the paired 32-seed MCTS baseline with search diagnostics.
4. Expand the tactics suite and audit actual card-coverage gaps.
5. Optimize measured hot paths; test wipe and coup-discount changes
   independently, preserving complete cache dependencies.
6. Use larger validation batches where attribution remains clear.

The separate terminal-outcome representation, explicit active tuning set,
and independent MCTS leaf/rollout configuration remain worthwhile
simplifications from the preceding audit. This review changed documentation
only; it did not run these proposed experiments or modify Claude's notes.
