# 2026-09-08 — Corpus generator and baseline evidence review

**Verdict: useful initial reference, but Option C step 1 is not complete.**
The frozen outputs provide a legitimate regression oracle for the fields
actually asserted. The evaluator is a reasonable next optimization target,
but fix the checker and add focused coverage for the first slice before
using a green corpus run as evidence of semantic parity. The current timing
evidence is exploratory, not an uncontended before/after baseline.

### Review scope and reproducibility

HEAD was `d782d19`. At review start, `scripts/capture_corpus.py`,
`tests/test_parity_corpus.py`, and `tests/corpus/positions.json.gz` already
had uncommitted changes. I copied those files, `profile_baseline.py`, and
`src/` into `/tmp/astra-corpus-review` and ran checks against that copy,
so ongoing edits would not change the reviewed implementation mid-run.
Those pre-existing changes were not edited or reverted.

Reviewed corpus metadata: version 2, source revision
`d782d19181bd1433991030c8265eb1b7dc0c446f`, `dirty=false`.
Compressed artifact SHA-256:
`134387d6447440c909d34e529ffa3fb00db23b7f5e210dfc830ced83e6a4113a`.
The dirty flag checks only `src`, not the generator, so it does not identify
the uncommitted generator that produced this file. Save the generator
revision/hash as well, and capture provenance at the beginning of a frozen
run rather than querying HEAD only after games finish.

The copied parity suite passed: **2 tests, 34.24 s**. This establishes
agreement for its current assertions, not completeness of the oracle.

### Findings, by priority

1. **High — the checker ignores recorded planner evidence and query order.**
   In `tests/test_parity_corpus.py`, the planner replay checks whole-hand
   risk, per-card risk and hazardous flags. It does not check `event_risk`,
   `truncated`, `nodes_after_probes`, or replay `probe_order`. It constructs
   default players rather than restoring the saved prior. I changed all
   of the following on one copied record and the parity function still
   passed: event-risk values to 999, truncation to its opposite, final
   node count to -999, query order to `['BOGUS']`, and prior max_states to 1.
   This was a temporary in-memory probe, not a corpus edit.

   The generator queries cards in observation-hand order, then writes JSON
   with `sort_keys=True`. The checker iterates the alphabetically sorted
   risk dictionary instead of `probe_order`: **274 records have a different
   card-risk query order**. With a shared planner state budget, this is a
   semantic difference. Fix: replay an explicit ordered list of operations
   with expected results; restore the exact prior/configuration; check
   event risks, final truncation and the intended budget semantics. Missing
   required fields should fail schema validation rather than be skipped.

2. **High — zero truncation cases, and the relevant tie paths are absent.**
   The 455 records contain 310 planner records and **zero truncated
   planners**; the largest recorded nodes_after_probes is 8,123 versus
   max_states 20,000. All records use one default prior. Include a small
   deliberately budget-limited case with multiple ordered risk queries
   before accepting planner memoisation or changing traversal order.

   There ARE natural exact safety-key ties in **214 records**; the exact
   ranking comparison protects those strategic ranking ties. However,
   generator and checker only instantiate `StrategicPlayer`. They do not
   cover `RolloutPolicy.score()`'s `(value, country)` tuple-max tie-break,
   or explicitly record `_investment`'s selected point count and tied
   alternatives. Those are different contracts. Add a deterministic
   equal-value rollout target case and a tied investment case.

   No direct `delta` per point count, `_investment`, or `influence` outputs
   are stored, despite their inclusion in the plan. Rankings exercise them
   indirectly but cannot expose every changed candidate value that still
   loses to the same winner. The generator captures only strategic games;
   it contains no dedicated MCTS rollout, event-sandbox, or generated
   boundary records. Event valuation during strategic ranking is indirect
   coverage, not a replacement for those fixtures.

3. **Medium — the opening benchmark does not run MCTS.**
   `profile_baseline.py` selects the first turn-1 action-round record
   without requiring scoring in hand, and `mcts_on()` returns only an
   action, discarding `last_search`. I confirmed that the selected
   seed-4000 T1 AR1 USSR record yields `last_search=None`. The current
   corpus already contains a suitable opening candidate: **record index 6,
   seed 4000, T1 AR1 US**, with scoring in hand. No synthetic board is
   necessary. Require actual completed search and persist simulations,
   root moves/visits, nodes, truncation and elapsed time. Apply that guard
   to every purported MCTS workload; a future corpus may select a different
   first match or trigger inventory fallback.

4. **Medium — the evidence supports a target hypothesis, not a speedup gate.**
   `docs/notes/claude/` explicitly says the gate ran concurrently with
   the baseline profiles. `profile_baseline.py` runs each case once under
   cProfile, prints rounded shares, and does not save repeated unprofiled
   timings, raw stats, environment/source identifiers, or results in a
   machine-readable report. It also does not create its own frozen
   checkout. The current printed numbers cannot establish a clean baseline
   or measure the benefit of the next slice.

   Its `PATHS` table labels `engine step` as a named function, so the code
   reports **cumulative step time**. The notes call the engine row exclusive;
   correct that label. Module-exclusive DEFCON time also excludes callees
   in other modules. Therefore 10% exclusive time alone does not prove a
   1.1x ceiling for every possible planner optimization. The explanation
   that planner cumulative time is mostly evaluator work needs an actual
   caller graph: `coup_survival_risk` is a strategic-policy caller of the
   planner, not evidence that the planner calls strategic `delta()`.
   Do not derive disjoint Amdahl fractions by adding nested cumulative
   categories or equating a module's self time with all removable work.

### Reference independence: what is already right

The parity test reads committed numerical outputs; it does not generate
expected values by calling the candidate implementation during the test.
Using the same Python implementation when capturing the original reference
is appropriate for a behaviour-preserving optimization. Version 2 also
uses a separate diagnostic policy after recording the production ranking,
which protects that ranking's planner budget from the probes.

Remaining lifecycle limits: production capture uses an in-game bot whereas
the test starts a fresh one; diagnostic queries share one probe instance
that was first warmed by `rank_actions`. Preserve and test these explicit
contracts. Record weights and resolved learned-prior configuration when
adding nondefault cases; the generator currently does not pass an opponent
model into its diagnostic probe. Full engine snapshots retain the decision
context even though the extra convenience `context` field filters values.
That filter is not itself missing reconstruction data.

### Recommended next action for Fable

Proceed toward **one small evaluator slice**, preferably region-margin
work first, rather than a broad indexing rewrite. The reported 71–73%
delta share in real scoring/hazard searches supports investigating this
path, even though it does not establish a specific achievable speedup.
Deferring planner optimization is reasonable prioritization, not a proven
claim that there is no useful planner gain.

Before landing the slice:

1. Repair the ordered checker and required-field/configuration handling.
2. Add targeted fixtures for that slice: regional tier/control/presence
   boundaries, both sides, explicit per-point deltas and investment ties,
   plus a rollout and event-sandbox case. If `_access` is changed first,
   substitute adjacency/reachability/control transitions and sequential
   temporary board changes. Keep initial legal placement reachability
   fixed within a spend. One limited-budget ordered planner fixture should
   also pin down the checker now; a full planner corpus can follow later.
3. On an isolated snapshot, run several unprofiled timings of identical
   fixed cases before and after, with unchanged ranks and fixed-search
   statistics. Save exact configuration, corpus/case IDs, source revision,
   raw elapsed times and separate profiles. Report each slice on its own.

No need to collect every future Rust case before starting this narrow
experiment. Do not call the current corpus exhaustive or step 1 complete.
I did not rerun the full-game strength gate or the expensive baseline
profiles during this review; no new speedup or strength claim is made.
