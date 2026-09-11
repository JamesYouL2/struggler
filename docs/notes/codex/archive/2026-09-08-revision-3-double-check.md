# 2026-09-08 — Revision 3 double-check

Reviewed `docs/RUST_PORT_PLAN.md` at HEAD `3c762f9`, plus the relevant
planner and rollout callers. **Option C remains agreed and is ready to
start with the corpus and fresh baseline.** No further broad planning
round is needed. Address the two oracle details below while writing the
corpus, before using it to accept an optimization.

### Two correctness details to pin down

1. **Preserve existing tie-breaks per operation, not a universal first-wins
   rule.** `RolloutPolicy.score()` selects `(value, country)` with
   `max(candidates)`. Equal values there are resolved by country-string
   order, not candidate order. `_investment` uses a strict `>` update and
   therefore retains the first best point count; stable action sorting
   likewise has its own ordering contract. The draft's blanket "first
   wins in both implementations" would change some current decisions.
   Record these distinct rules and include tied target values in the
   corpus. Any intentional standardization belongs in a separate semantic
   change, not an indexing or Rust commit.

2. **Record query order and cache lifecycle in the oracle.** The planner's
   `nodes` counter and `max_states` budget are shared across calls on a
   planner instance; exceeding the budget switches to conservative
   results. Asking every card/mode for diagnostic output can itself consume
   that budget before the production ranking is captured. Use independent
   reference instances for isolated probes, and also capture the real
   ranking's ordered query sequence on a shared instance, especially for
   truncation cases. Similarly, evaluator probes must not accidentally
   prime or mutate the policy used for the recorded production ranking.
   Store enough reconstruction information to reproduce each case:
   complete observation, weights/priors (including max_states), decision
   options and context, and the relevant initialization/query sequence.
   Preserve hand iteration order where it affects traversal or summation;
   using a multiset cache key does not authorize reordering the solver.

### Remaining draft inconsistencies

These do not block C's baseline work, but the plan should stop making
contradictory commitments:

- The introduction still says thousands of simulations require the whole
  engine native and that deep MCTS implies B. Its later Astra decision
  and C step 4 correctly leave parallel search and narrower native rollout
  implementations open. Keep that conditional language throughout.
- The introduction still calls the costs Python waste that indexing and
  memoisation "remove." Step 2 correctly acknowledges existing caches
  and requires measurement. Describe possible savings, not guaranteed ones.
- The `evaluate_placements` description still says it evaluates access
  "for the country and its neighbours" and removes 70–90% of cost. It
  must preserve the changed-country delta and measure actual coverage;
  reading neighbours inside `_access` is not rescoring their values.
- The effort table still budgets a native DEFCON solve and the data layout
  includes a card table "for the DEFCON solve only," although the call
  list excludes that solve. Remove or explicitly label these as a separate
  future option. The context's reference to C step 3 should be step 2 for
  planner work; pure-function extraction is no longer C step 3 either.
- The hypothetical evaluator-plus-planner Amdahl row is not a forecast for
  the currently proposed Rust scope, which leaves the planner in Python.
  The two-week and speed targets remain provisional, subject to C's fresh
  workload mix and timing measurements.

### Next concrete deliverable

A small reproducible corpus plus a baseline report: exact source revision,
case IDs/seeds, reference outputs, ordered ties and truncation cases,
unprofiled wall timings over repeated runs, separate profiling results,
and environment details. Then measure predicate hoisting as its own change.
Expand the corpus as needed; do not turn collecting it into a broad rewrite.

Validation for this review: source inspection and `git diff --check` on
the notes. No runtime code was changed and no benchmark or test-suite
results are claimed for revision 3. Fable's plan was left unchanged.
