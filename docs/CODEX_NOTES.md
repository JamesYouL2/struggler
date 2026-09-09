# Codex scratchpad

## 2026-09-08 — MCTS audit and Rust port assessment

Scope: quick review of `bots/mcts.py`, `bots/rollout.py`,
`bots/defcon.py`, and the strategic evaluation helpers. No implementation
changes made during this audit. HEAD was `cc7bfb0` and the working tree was
initially clean. `src/struggler/bots/strategic.py` changed externally while
the audit ran; the findings and profile concern the code loaded before
those edits, not a review of the subsequent changes.

At the time of this initial audit, the detailed Fable Rust plan was not
available. The recommendation below assessed the user's description:
port DEFCON helpers and evaluation. The subsequent review of
`docs/RUST_PORT_PLAN.md` is recorded below.

### Recommendation

Prioritize correcting reward semantics and targeted continuations, then
accelerate repeated candidate evaluation. A small board does not make Rust
pointless: the same small calculations run many thousands of times.

- Port the hot `delta()` / country / regional evaluation loops together,
  ideally including batches of candidate changes or investment evaluation.
- Use compact influence arrays and precomputed static country/adjacency
  data. Avoid converting Python dictionaries or calling back into Python
  for each tiny inner-loop operation.
- Porting only `StrategicPlayer.value()` at MCTS leaves will miss almost
  all the measured evaluation cost.
- DEFCON-first is not supported by the opening profile. Profile hazardous
  late-game hands before deciding its priority; the recursive planner can
  have a very different workload there.
- After correctness fixes establish a baseline, compare Python/Rust
  rankings and numerical results on frozen positions. Measure whole-search
  wall time including conversion, then playing strength at equal wall time.
  Keep algorithm changes separate from acceleration measurements.

### Reproduced findings

1. **High — leaf evaluation inherits previous ranking context.**
   `MCTSPlayer.leaf_return()` calls `self.policy.value(engine.board, side)`.
   The same policy ranks tree moves and retains `_obs`, `_scoring_weights`,
   and evaluation caches. Therefore the leaf is evaluated using context
   from a preceding tree-node ranking, rather than explicit leaf context.
   Using `tests/test_mcts.py::scoring_position`, an identical leaf returned
   `-0.2012164391` with a fresh bot, `-0.2831167675` after ranking that
   position, and `-0.0927994271` after ranking a separate position with
   Central America Scoring moved from hand to discard. The evaluated leaf
   itself did not change. Tree traversal/depth can change the reward basis.
   Fix direction: separate leaf evaluation from proposal policy state and
   explicitly choose leaf-observation or observation-independent semantics.

2. **High — served placement plans suppress MCTS targets.**
   `RolloutPolicy._served()` returns only its planned placement, while
   `MCTSPlayer.continuation()` searches that returned ranking for the macro
   target. If the plan selects another country, the target cannot be found.
   Reproduction: a bare action-round engine, US influence 1 in Italy, US
   spending 4 Ops; rank Ops, choose influence, then request France as the
   continuation target. France is legal and uncontrolled, but the action
   places in Italy. Japan, Mexico, and Cuba also reproduced this mismatch.
   Distinct target macros can therefore execute the same placements.
   Fix direction: make placement planning target-aware or bypass served
   plans for targeted moves while preserving legal-action and safety checks.

3. **Medium — rollout ranking cache does not synchronize the board.**
   `RolloutPolicy.rank_actions()` restores rankings, `_plan`, and
   `_placements` on a hit, but does not synchronize `self.board` to `obs`.
   Reproduction: rank an Ops-type observation A, rank B with France changed
   to 10 US influence, then rank cached A again. The policy board retains
   10 in France while A contains 0. `MCTSPlayer.continuation()` reads that
   board to decide whether its target is controlled. Served decisions can
   also bypass board synchronization.
   Fix direction: use the current observation for the control check or
   guarantee board synchronization on every relevant ranking path.

These are missing regression cases, not fixes already implemented.

### Profile evidence

Workload: `Engine.new_game(3003)`, strategic decisions through the first US
action-round card boundary, then `MCTSPlayer(simulations=24)` with default
settings. One local cProfile run, not a representative multi-position suite.

| Measurement | Result |
| --- | ---: |
| Simulations / tree nodes / truncated simulations | 24 / 14 / 0 |
| Root macros | 11 |
| Visits per root macro | 2–3 |
| Total profiled search time | 48.89 s |
| Rollout ranking cumulative time | 45.52 s (~93%) |
| `delta()` calls / cumulative time | 156,879 / 35.13 s (~72%) |
| Leaf evaluation calls / cumulative time | 24 / 0.391 s (~0.8%) |
| DEFCON module exclusive time | 0.352 s (~0.7%) |
| `DefconPlanner.risk()` cumulative time | 0.420 s |
| Hidden-state reconstruction cumulative time | 0.057 s |
| Information-key cumulative time | 0.452 s |

Cumulative timings overlap and must not be added together. DEFCON's
exclusive time excludes helpers called in other modules. cProfile adds
substantial overhead; a separate unprofiled run took 22.22 s locally.
Neither timing is a portable latency claim or a before/after speedup.
Concurrent workspace activity also makes timing comparisons unsuitable for
an optimization acceptance gate. Use a frozen checkout for that gate.

The root's 11 macros over 24 simulations also deserve attention: only 2–3
observations inform each mean. Correct target execution and reducing
redundant candidates may improve useful search before a native port.

### Validation and follow-up

Existing targeted suite passed: **40 tests in 2.56 s**.

```sh
.venv/bin/python -m pytest tests/test_mcts.py tests/test_rollout.py tests/test_defcon_planner.py -q
```

Temporary evidence from this session: `/tmp/mcts_audit.py` and
`/tmp/mcts_audit.prof`. The script contains the leaf-context probe, a
placement-target probe, and the opening profile workload. The additional
battleground-target and cache-synchronization probes were run separately
through stdin. Temporary files are not durable repository artifacts.

Next work, in order:

1. Add focused regressions and resolve the three findings above.
2. Review Fable's concrete Rust API and port scope (completed below).
3. Profile frozen opening, scoring, and hazardous late-game positions.
4. Choose a native boundary covering repeated evaluation work and measure
   end-to-end benefit without changing the corrected policy semantics.

Audit limits: no full rules-engine review, no exhaustive DEFCON semantic
audit, no Rust implementation benchmark, and no playing-strength comparison.

## 2026-09-08 — Review of Fable's RUST_PORT_PLAN.md

Verdict: support the staged, batched evaluator approach, with the revisions
below before implementation. The draft incorporates the important audit
recommendations: correctness first, whole evaluation loops rather than tiny
helpers, explicit context, a Python reference, and end-to-end measurement.
Its throughput promises, data contract, and parity gate need correction.
This is a plan review, not approval of an implementation or confirmation
that the earlier MCTS defects have been fixed.

### Required revisions

1. **Replace the throughput forecast with an Amdahl budget.**
   Whole-workload speedup is `1 / ((1 - p) + p / s)`, where `p` is the
   accelerated fraction and `s` its speedup. At the measured 72% `delta`
   fraction, a 20–50x kernel gives only about 3.2–3.4x overall, even if
   the port covers that entire fraction. At an optimistic 93% coverage,
   it gives about 8.6–11.3x; even eliminating that fraction entirely caps
   speedup at 14.3x. These figures do not justify "24 simulations into
   thousands." They are illustrative ceilings from a profiled opening,
   not forecasts for larger searches, which can change the work mix.
   On Fable's stated full-game evaluator share of 25%, evaluator-only
   acceleration cannot reach the required 3x full-game speedup: its
   theoretical ceiling is 1.33x. Set stage-specific targets; failure to
   reach 3x does not by itself prove the boundary is wrong. Also, a trivial
   bot's game time does not isolate engine cost; 1.1 / 13.4 is about 8.2%,
   not evidence that the engine is under 5%. Fable's full-game profile was
   reported in the plan and has not been independently reproduced here.

2. **Freeze the exact evaluation semantics before extracting them.**
   The plan describes access evaluation "for the country and its
   neighbours (everything delta touches)." Current `delta()` evaluates
   the changed country's value plus regional terms; it does not sum
   changed values for neighbouring countries. Its access helper reads
   neighbours, which is different. Replacing this with a full-board
   before/after delta would change the policy. Cache removal can also
   expose previously frozen dependencies and change results. Capture
   outputs from the corrected, pre-refactor Python implementation before
   making it pure, then compare after every extraction step. A corpus
   generated only after extraction cannot detect extraction drift.
   Correctness fixes themselves are intentional behaviour changes, not
   the "gated no-op" the prerequisite heading calls them.

3. **Correct the array contract and validate its assumptions.**
   `len(Board().countries)` is **85**, not the draft's 86. Derive size
   from the shared tables and validate country ordering. I found no
   enforced engine-wide influence cap supporting the uint8 claim; use
   checked conversion with an explicit supported range/fallback, or a
   wider representation. Never wrap or saturate values silently. Signed
   intermediates are necessary for influence differences and removals.
   Validate weight names/order and a schema version, not just K: equal
   lengths do not detect reordered or renamed fields. Clarify how tables
   supplied dynamically by Python relate to the exported COUNTRY_ORDER.

4. **Specify the missing combat and DEFCON context.**
   The proposed evaluator context is enough only for the dependencies
   actually extracted. `coup()` additionally uses phasing responsibility,
   event effects, roll modifiers, military Ops and Yuri/Samantha; realign
   also has modifiers. Either pass precomputed modifiers/adjustments and
   legal candidates, or enumerate these context fields explicitly.
   `defcon_risks` needs a complete state contract: rounds remaining, Space
   Race position and attempts/eligibility, China availability, trap state,
   pending headline, discard-dependent event chains, learned priors, and
   max_states/truncation behaviour, in addition to its listed arguments.
   Static opponent affiliation can be a mask; `hazardous()` is not in
   general a fixed per-card mask. Grain Sales and Five Year Plan depend
   on the remaining hand. Preserve those state-dependent risks. A bitset
   over card identities must also preserve multiple `@replacement`
   placeholders produced by Ask Not, for example using a separate count.

5. **Make the reference and native parity tests independent.**
   A head-to-head score of 0.5 and matching final VP do not establish
   identical actions. Identical policies can have seat/seed bias; different
   actions can end at the same VP. Run Python/Python and native/native
   games separately with identical seeds and compare action/chance traces
   and final states. Compare fixed-simulation MCTS root statistics too.
   Use absolute plus relative value tolerances near zero, and require
   actual deterministic ranking/top-action parity. Rounding rankings to
   1e-9 only in tests can hide a tie-break difference in production.
   Fix candidate order and first/last-tie behaviour explicitly.

6. **Forced-native testing must not silently fall back.**
   Auto mode may fall back when the module is absent; `STRUGGLER_NATIVE=1`
   should fail loudly if it cannot load the expected extension. At least
   one required CI job must build it and assert native execution.
   Otherwise both supposedly different test runs can exercise Python.
   The existing gate snapshots Python source but uses the shared venv;
   that does not freeze a native extension installed there. Build/isolate
   the extension from the same snapshot and record its source revision,
   artifact hash, loaded path, build mode and backend. Likewise, loading
   only an old `strategic.py` via `strategic@...` is no longer an isolated
   baseline once it imports a shared evaluator/native wrapper.

7. **Fix the development command.**
   The installed `maturin develop --help` says `-m/--manifest-path` takes
   `Cargo.toml`, not `pyproject.toml`. The proposed command must point to
   `rust/Cargo.toml`; verify configuration discovery and a clean install
   with the final packaging layout. No build was attempted in this review.

### Answers to Fable's three questions

1. **Boundary:** start with batched `evaluate_placements`, keeping legal
   candidate generation and survival ordering in Python. Do not port all
   of `rank_actions` just to reduce crossings: it includes event and
   safety logic outside the numerical kernel. Consider a second batched
   greedy-spend operation for `ops_value()` / `_placement_plan()` after
   measuring the first boundary. Their repeated investment loops still
   change the board between batches. Preserve the initial legal candidate
   set so an investment cannot open new reachability in the same Ops spend.
   `ops_value` is not merely card logic; its investment loop is part of
   the measured workload, so document precisely which part stays Python.

2. **Corpus:** yes, include MCTS rollout and event-sandbox positions, both
   seats, multiple turns, and generated boundary cases. Include candidate
   order, Ops budget, context and expected point counts, not just board
   arrays. Cover enemy-control cost transitions, regional tier thresholds,
   Europe control, zero/near-tied gains, bonus Ops, effects, safety ordering,
   and influence range limits. Extend the corpus for each later API.

3. **Indexing:** useful as an evaluator-local step if parity and timing
   demonstrate benefit. Do not change the engine's public representation.
   The profile's enum cost spans the whole workload, so indexing only the
   evaluator cannot be assumed to remove all 12%. Keep the refactor small
   enough to avoid writing and maintaining the evaluator three times.

### Acceptance recommendation

Separate three decisions: semantic parity, measured acceleration, and
promotion of the resulting MCTS policy. A faster implementation need not
beat strategic at 64 seeds to be a valid port; search quality is a separate
question. Measure paired-seat results with uncertainty clustered by seed
and compare against corrected Python MCTS at equal wall time as well as
strategic. Treat 64 seeds as a planned sample size, not a guarantee of
detecting an improvement. The two-week and ~600-line estimates are planning
assumptions, not validated constraints.

Review validation: read the draft and relevant current Python callers;
confirmed 85 countries at runtime and checked the local maturin CLI help.
No code changes, new performance runs, or test-suite reruns were needed
for this documentation-only review. Fable's plan is unchanged; these notes
are the requested reviewer feedback.

## 2026-09-08 — Revision 2 / Option C decision

**Yes to Option C as a bounded measurement stage.** Defer Rust while
establishing a corrected reference and measuring inexpensive Python
improvements. This is not a commitment to complete a large array-Python
rewrite before Rust can be considered.

Suggested order:

1. Capture the corrected parity corpus AND fresh baseline timings/profiles.
   Include explicit DEFCON risk outputs and planner inputs: the listed
   evaluator outputs and rank safety keys alone do not cover the planner's
   public operations. Include truncation cases and learned-prior context.
2. Try the smaller predicate-hoisting/memoisation change first, then measure
   it independently. Current `DefconPlanner` already caches `solve` and
   `_event_risk` with `lru_cache`; do not assume another cache eliminates
   millions of expensive computations. Measure cache hits, misses and
   wrapper/key-construction cost. Keep hazard-at-DEFCON-2 semantics and
   replacement multiplicity intact.
3. Index the evaluator incrementally, with parity and whole-workload timing
   after each meaningful slice. If conversion or Python indexing overhead
   erases the gain, stop rather than completing a rewrite solely because
   it was called a prerequisite. A Rust kernel can receive arrays while
   the original dict-based Python evaluator remains the reference.
4. Choose among keeping the Python improvements, a batched Rust kernel,
   parallel search, or a broader native rollout implementation. Deep MCTS
   does not logically require porting the entire engine; that remains an
   option to justify with measurements and a concrete latency target.

The draft's corpus -> indexing -> memoisation order is workable, but
measuring only after both optimizations loses attribution. Prefer the
cheaper memoisation experiment first unless the fresh profiles favor an
equally small indexing change. No predicted speedup is approved here.

Revision 2 still contains stale, contradictory sections: its later
prerequisite list puts the corpus last; its signatures still say u8 despite
the int16 layout; its call list still describes static hazard masks and a
DEFCON native solve despite the newer scope exclusion; and its risk table
still rounds rankings despite trace/ranking parity without rounding above.
Treat the Option C section as the proposed current scope, and consolidate
these leftovers before treating the whole document as an implementation
contract. The evaluator-plus-planner Amdahl row also computes to about
5.2x at s=20 and 6.0x at s=50 for p=.85, rather than 4.9x/5.9x.

Validation: read revision 2 at HEAD `371d592` and confirmed the existing
DEFCON caches in source. The cited MCTS fix commits are present in history;
this decision does not constitute a fresh implementation audit of them.

## 2026-09-08 — Revision 3 double-check

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

## 2026-09-08 — Corpus generator and baseline evidence review

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
   `docs/CLAUDE_NOTES.md` explicitly says the gate ran concurrently with
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

## 2026-09-09 — Overnight handoff: region slice gated, hash-order bug fixed

Scope so far: finish the four next steps in `docs/CLAUDE_NOTES.md`, run the
full 32-seed gate, make atomic conventional commits, then continue with one
more evaluator/MCTS improvement. The tree was clean at this handoff. The
remaining optimization work should start from `a84593a`.

### Commits made

- `c24c531 perf(bots): cache regional margin aggregates`
- `b0db60d test(corpus): preserve investment tie context`
- `ee66cce docs(notes): rename Astra audit to Codex`
- `696294c fix(profiling): select hazards from ordered probes`
- `7d820de fix(profiling): force hazardous MCTS searches`
- `a84593a fix(bots): stabilize access ranking across hash seeds`

The two profiler fixes were necessary because corpus v3 replaced the old
`planner.hazardous` mapping with ordered `planner.probes`, and none of the
natural hazardous action-round records contains a scoring card. The
hazardous profile now selects from the ordered probes and deliberately uses
`MCTSPlayer(search_all=True)`. A direct smoke run on seed 4000, turn 5,
action round 1 completed 24 simulations over 18 nodes.

### The reported cross-test leak was hash-order nondeterminism

The current full suite initially passed unchanged (`490 passed, 3 skipped`,
134.16 s), which contradicted a persistent leak. No test writes the shared
adjacency dictionary, `RULES`, or the module card tables, and the adjacency
values are immutable `frozenset`s. Fresh-process probes then reproduced the
six affected corpus records under some `PYTHONHASHSEED` values without
running any earlier tests.

Root cause: `_access()` accumulated floats while iterating a first-hop
`set` and second-hop adjacency `frozenset`s. Hash-dependent addition order
moved values by one ulp; strict ranking then reordered candidates around
2.4668. This looked like test pollution because the isolated and full-suite
pytest processes happened to receive different hash seeds.

`a84593a` walks both additive neighbor loops in sorted order and adds a
three-process regression covering hash seeds 0, 1 and 2. Manual probes of
all six reported records (121, 122, 130, 131, 135, 136) matched the corpus
under seeds 0 through 5. The full suite under `PYTHONHASHSEED=5` passed:
`491 passed, 3 skipped in 151.91s`. The corpus did not need regeneration;
the canonical order reproduces its captured values and rankings.

### Region-margin gate: passed over 32 seeds

Ran the isolated snapshot gate at `ee66cce` against the pre-slice revision
`1291064`, seeds 4000-4031, both seats, 8 workers:

| Check | Result |
| --- | --- |
| Turn-3 checkpoint | score 0.500, mean signed VP 0.00, mean total 0.00, 0 nuclear losses |
| Full games | score 0.500, mean signed VP +0.27, mean total +0.55, 0 nuclear losses |
| Existing expert check | 24 misses; two ordering and placement warnings remain, not introduced by this slice |

Raw gate artifacts are in `logs/game-check/gate-ee66cce/` (gitignored).
The gate exited successfully. Because `a84593a` is a later behavioral
determinism fix, the final overnight candidate still needs its own 32-seed
gate after the next slice is selected and landed.

### Isolated region-slice timing and fixed-search evidence

Compared detached, clean snapshots `1291064` (before) and `7d820de` (after;
the only `strategic.py` change is `c24c531`) on Linux/WSL2, Python 3.12.13,
8 logical CPUs. The same current corpus supplied serialized positions to
both. No other benchmark or repository process was running.

For the first 40 `place_influence` corpus positions, five unprofiled passes
took:

- Before: 0.150938, 0.178106, 0.168382, 0.206434, 0.176398 s
- After: 0.125992, 0.141635, 0.137464, 0.125678, 0.147990 s
- Median: 0.176398 -> 0.137464 s, **22.1% faster**

Ten process-isolated strategic-vs-strategic seed-4000 games were run in
alternating order to reduce time-of-run bias. Every game ended identically:
USSR, -20 VP, turn 10, VP victory.

- Before: 8.390106, 7.833148, 8.760186, 8.837293, 8.647347,
  7.565142, 8.768050, 8.582119, 8.775470, 8.642374 s
- After: 6.947339, 7.728132, 7.639097, 7.689720, 7.675124,
  6.927435, 7.384989, 7.716984, 7.634510, 7.627454 s
- Median: 8.644861 -> 7.636804 s, **11.7% faster**

Three repeated 24-simulation MCTS searches on fixed corpus records retained
identical action/root-stat digests before and after (including move order,
visits and values): opening record 6 chose East European Unrest with 11
nodes; scoring record 35 chose Formosan Resolution with 15 nodes; hazardous
record 58, forced with `search_all`, chose the China Card with 18 nodes.
Wall-time medians were noisy and mixed:

| Fixed MCTS case | Before median | After median | Change |
| --- | ---: | ---: | ---: |
| Opening | 6.320 s | 6.559 s | 3.8% slower |
| Scoring | 9.395 s | 8.948 s | 4.8% faster |
| Hazardous | 28.259 s | 29.771 s | 5.4% slower |

Do not claim a general MCTS speedup from three repetitions. The direct
placement workload and ten alternating full games support the region slice;
the fixed-search digests support unchanged behavior on these MCTS cases.
Temporary full JSON reports are `/tmp/region-before-1291064.json` and
`/tmp/region-after-7d820de.json`; the raw durable values are copied above.

### Next action

Take `_access` as the next evaluator slice before attempting the broader
pure-function extraction. It is 10-16% of the measured path and the
determinism fix now sorts adjacency on every call. Precompute canonical
first/second-hop adjacency tuples once and reuse them in `_access`, while
preserving its current duplicate counting, reachability, contested and
chain semantics. Measure this slice independently against `a84593a`; require
the parity corpus, the hash-seed regression, the full suite, fixed MCTS root
statistics, and a fresh 32-seed gate before landing it. If precomputation
does not beat the new sorted implementation end to end, revert that slice
and proceed to pure-function extraction instead.

## 2026-09-09 — Architecture, technical and strategic audit

Read-only audit anchored to committed `7cb9fbe` (which removed the stale
country/access memos). An untracked `src/struggler/bots/evaluator.py` and
changes to `strategic.py` were being edited concurrently. Observations about
that extraction are provisional integration risks, not findings against a
finished implementation. No implementation files were changed for this
audit. Numerical event findings below were reproduced with focused runtime
probes; the broader assessment is based on code inspection, not a new full
suite or strength tournament.

Overall assessment: the architecture has a solid foundation, but evaluation
consistency is currently a bigger constraint than search speed. Increasing
MCTS depth before resolving that consistency risks searching more deeply
with misleading values.

### Architecture

**The observation boundary is sound in the inspected paths.** StrategicPlayer
selects from supplied legal actions and reconstructs simulations from public
observations. No direct access to the live opponent's hand or RNG was found.
Keeping legality in the engine and DEFCON survival in a separate planner are
good boundaries. This was not an exhaustive hidden-information audit.

**High priority — explicit evaluation context and state contract.** The
committed player mixes observation preparation, board mutation, evaluation,
event simulation and policy selection. `value(board, side)` also depends on
the player's previously prepared observation. Consequently a local-looking
change can alter distant callers. Numerical kernels should receive explicit
position, weights and context, with cache ownership and lifetime defined at
the boundary.

The pure evaluator extraction is promising, but the inspected wrapper keeps
both `board.influence` and an indexed position. Every mutation must update
both. At inspection time, `RolloutPolicy._placement_plan()` still wrote
influence directly; cached-ranking synchronization paths also deserve an
audit. These callers must be checked before accepting the new snapshot
representation. A pure kernel does not by itself make its stateful wrapper
correct.

**High priority — benchmark isolation after extraction.** `scripts/gate.sh`
extracts only the baseline's `strategic.py` and imports it inside the
candidate's package environment. Once both versions import `evaluator.py`,
the baseline can silently use the candidate evaluator. Compare complete
revision-specific implementations, including evaluator dependencies, rather
than a single historical source file.

### Technical correctness

**High — event valuation omits indirect board changes.**
`StrategicPlayer._resolve_sandbox()` refreshes only countries whose influence
changed, although `country_value()` reads neighboring influence and, when
wipe weights are enabled, global coup-target counts. Removing the old memos
does not repair this separate reuse of the event basis.

Reproduction on `7cb9fbe`: an engine with US influence 2 in Egypt, 1 in
Israel and 1 in Mexico, with a US placement observation, values Nasser at
**-67.8296875** through `_public_event_value()`. Full before/after board
recomputation gives **-65.8890625**. Israel's **+1.940625** change is omitted
because its own influence did not change. This can misrank events against
Ops. Recompute the full affected dependency set, or use full board
recomputation as a correctness reference before optimizing it.

**Medium — event helpers retain old weights.** `_event_helper()` constructs
its policy once using the parent's weights. Replacing `bot.weights` leaves
the helper on the previous weights, so simulated choices and their
evaluation can use different weights. This was reproduced by creating the
helper, replacing the parent's weights, and checking the helper's weights.
The existing weight-change regression does not exercise that helper. This
affects reused players whose weights change, rather than every normal game.

**Medium — unexpected simulation failures are hidden by generic estimates.**
`event_value()` catches every `Exception`, logs at debug level and substitutes
an allegiance/Ops estimate. A programming error can therefore produce a
plausible number instead of a visible failure. Distinguish expected
unsupported simulations from implementation errors, and make fallback use
observable in diagnostics and validation.

**High — gate completion is not gate acceptance.** `gate.sh` reports scores
but does not enforce strength or nuclear-loss acceptance thresholds. A zero
exit status establishes successful execution, not strategic acceptance.
The earlier handoff's statement that the region-margin gate "passed" was
too strong: the 32-seed run completed with the recorded neutral results,
which still require interpretation. Define explicit acceptance criteria and
compare expert-check changes before describing a candidate as passing.

### Strategic quality

**High — persistent effects are systematically undervalued.** Flag-only
events commonly receive zero. This is an acknowledged limitation in
`docs/STRATEGIC_AI.md`, not a newly introduced regression, but it matters
strategically. In a probe with US-controlled Taiwan and USSR-controlled
Thailand, Formosan Resolution and Shuttle Diplomacy both received event
value **0**, while improving immediate Asia scoring by **1 VP** and **4 VP**
respectively. Prioritize high-impact effects whose benefits can be evaluated
from public state.

**High — scoring urgency has an incomplete horizon model.**
`public_cards.scoring_schedule()` treats unseen scoring cards as scoring now
and again after an estimated reshuffle. It does not cap those predictions
at game end or explicitly include final scoring. Late-game investments can
therefore be priced against opportunities that never occur. Use a bounded
remaining-game horizon and distinguish current-cycle uncertainty from
mandatory final scoring.

**Medium — card and operations selection use different placement models.**
`ops_value()` uses a greedy multi-country spend; the influence branch of
`score(OPS_TYPE)` extrapolates the best single-country investment across all
Ops. A card can be selected based on one allocation estimate, followed by an
operations-mode choice based on another. Align the spend evaluator used by
these decisions while keeping the engine's legal actions authoritative.

**Medium — local gains miss sequencing and counterplay.** Average gain per
Op cannot fully capture combinations, defensive timing or the opponent's
next response. This is intentional tactical scope, not an implementation
defect. Weight tuning alone cannot solve it. Targeted continuation search
for consequential decisions is more promising than a blanket increase in
simulation count.

**Medium — repeated benchmark reuse encourages overfitting.** Selecting
successive changes on the same seeds against recent predecessors can favor
narrow improvements. Keep paired seeds for debugging and attribution, but
reserve untouched seeds and multiple opponent styles for promotion. This is
a methodological risk, not proof that any particular improvement overfit.

### Recommended order

1. Finish the evaluator state contract and audit every rollout/sandbox
   mutation and synchronization path.
2. Correct event recomputation and expose unexpected simulation failures;
   update event-helper weights when the parent changes.
3. Repair full-revision benchmark isolation and define explicit gate
   acceptance criteria.
4. Correct scoring horizons and price the highest-impact persistent
   effects.
5. Evaluate targeted MCTS improvements on held-out seeds at equal wall time.

This audit supersedes the prior handoff's recommendation to immediately
optimize `_access`: the subsequent memo-removal commit and concurrent
evaluator extraction change the baseline, and correctness/integration now
take priority. Earlier timing numbers describe their named revisions only.

## 2026-09-09 — Preferred architecture for an 8-core personal laptop

The user endorsed this practical direction:

> Exact engine -> lightweight hand sampling -> selective tactical search
> -> fast handcrafted or small learned value.

Keep the engine authoritative for legality and chance. Sample hidden hands
consistently with public information, and give each simulated player only
information available to that seat. Spend search on consequential card
choices, scoring timing and a few competing investment plans; use cheap
continuations for routine atomic placements.

The recommended progression is:

1. Finish the deterministic evaluator: correct event values, scoring
   horizons and state synchronization before optimizing measured hot paths.
2. Improve search candidates and remove redundant branches before simply
   increasing simulation count.
3. Parallelize independent games first. Start around 4-6 workers and measure
   throughput and thermal throttling; eight busy workers need not be fastest
   on a laptop. Run timing benchmarks separately from training workloads.
4. Test a small CPU-friendly learned value model before learning a policy.
   Collect outcome-labeled self-play positions, with varied opponents, and
   compare prediction quality against the handcrafted evaluator on held-out
   games. Split data by whole game and seed, not individual positions.
5. Integrate the learned value only if it improves search at equal wall
   time. Compare heuristic search and learned-value search directly; retain
   the handcrafted evaluator as a baseline and diagnostic tool.

Defer full belief-state CFR, large neural networks, learning from scratch,
and sophisticated learned hand beliefs. Student of Games and ReBeL are
architectural references, not proposed laptop training recipes. Strategic
can supply initial competence and training opponents without defining every
future rollout and leaf value.

This is a preferred experimental direction, not a demonstrated strength
gain or a hardware performance guarantee. Game-generation throughput,
held-out results and equal-time playing strength decide whether learning
earns a place. The eight-core constraint changes the scale and order of
experiments; it does not require abandoning selective search.

## 2026-09-09 — Audit reassessment after the evaluator commits

Reviewed through `9d9890f`, including `ec99a5f` (pure evaluator extraction)
and `9d9890f` (event-value dependencies). The only working-tree change was
this notes file. This section updates the earlier architecture/technical/
strategic audit; the earlier text is retained as a historical assessment,
not a list of defects all still present. No implementation changes were
made during this reassessment.

### What is fixed or materially improved

- **Indirect event-value recomputation: resolved for the reported defect.**
  `StrategicPlayer._value_dependents` now includes the evaluator's dependency
  radius, rather than only countries whose influence changed. With the
  global `wipe` term enabled it conservatively includes the entire board.
  This addresses the Nasser/Israel omission. Tests check dependency coverage
  and compare reused event values with full country recomputation across
  the public events supported by a fixture. This is not proof of complete
  event valuation: both paths still use the same limited evaluation context,
  and that test skips events the fixture cannot simulate.
- **Evaluator architecture: substantially improved, not fully closed.**
  `evaluator.py` now provides pure terms with explicit terrain, position,
  weights, urgency and DEFCON inputs. Strategic is a policy/context wrapper
  around those terms. Rollout trial placements use synchronized mutation
  helpers; even cached rankings refresh the position snapshot. Snapshot
  consistency tests cover strategic and rollout mutations. The earlier
  warning about those direct rollout writes is obsolete. However, the
  public `StrategicPlayer.value(board, side)` wrapper still takes urgency
  and DEFCON from previously prepared state. Document/enforce that wrapper
  contract or use explicit core inputs for independent evaluation. Two
  representations remain a maintenance obligation, not a demonstrated
  current synchronization failure.
- **Baseline evaluator contamination: resolved for the extracted pair.**
  The gate snapshots both `strategic.py` and its revision's `evaluator.py`;
  the benchmark loader binds that sibling evaluator and restores the
  candidate's module afterward. Regression tests cover the binding and
  restoration. The original concrete contamination finding should no
  longer be treated as an outstanding blocker. This is still not complete
  revision isolation: other imported modules come from the candidate
  environment. Comparisons spanning changes in those dependencies need
  broader isolation or an explicit shared-dependency qualification.

### What still applies

- **Event helper weights (medium):** `_event_helper` creates its cached
  policy once and does not update it when the parent's weights object is
  replaced. The finding remains conditional on such replacement.
- **Silent simulation fallback (medium):** `event_value` still catches all
  exceptions, logs only at debug level and substitutes a generic estimate.
  Unexpected defects can therefore look like supported approximations.
- **Gate acceptance criteria (high):** `scripts/gate.sh` prints benchmark
  summaries but does not enforce strength or regression thresholds. Its
  anchor run remains opt-in. Successful execution is not a strength pass.
- **Persistent effects (high):** the event sandbox's final value still
  measures influence-derived terms and immediate VP, not the future value
  of flag-only effects. The earlier Formosan Resolution/Shuttle Diplomacy
  concern remains; fixing influence dependencies does not price those
  effects. The earlier numerical probes were not rerun in this reassessment.
- **Scoring horizon (high):** `public_cards.scoring_schedule` still uses
  current-cycle/reshuffle estimates without final scoring or a turn-10
  horizon cap. The extraction preserves this approximation.
- **Operations consistency (medium):** card-level `ops_value` uses a greedy
  multi-country spend, while the influence branch of `OPS_TYPE` still uses
  the best single-country average gain multiplied by the operation count.
- **Sequencing and counterplay (medium):** local investment values remain
  approximations, not a replacement for selective tactical search.
- **Benchmark reuse (medium):** held-out seeds and varied opponents remain
  necessary for promotion; the loader fix does not address selection bias.
  This remains a methodological risk, not demonstrated overfitting.

The positive observation-boundary assessment is unchanged in the inspected
paths; this was not a fresh exhaustive hidden-information audit.

### Revised next steps and verification

Do not redo the evaluator extraction or the Nasser fix. First synchronize
helper weights and make unexpected sandbox failures visible; clarify the
prepared-state wrapper contract. Add explicit benchmark acceptance rules
and isolate any shared dependencies that changed between compared versions.
Then address scoring horizons and high-impact persistent effects, and align
the two operations estimates. Broaden regression fixtures across late-game
states, nondefault weights and event contexts as those areas change.

The eight-core architecture direction above still applies, and the pure
evaluator is a useful step toward it. Nothing in these commits establishes
that MCTS, hand sampling or a learned value now improves equal-time strength.
Those remain experiments after the remaining correctness work.

Verification: `.venv/bin/python -m pytest tests/test_evaluator.py
tests/test_rollout.py tests/test_benchmark.py tests/test_strategic.py -q`
completed with **46 passed in 17.12s**. No full strength gate or new playing-
strength claim was made. The review resolves the concrete dependency and
baseline-evaluator bugs, narrows the architecture finding, and leaves most
strategic/modeling findings applicable.

## 2026-09-09 — Human tournament statistics as a calibration reference

Internet research found useful tournament outcome data, but no verified,
ready-to-use tournament dataset of per-card event-versus-operations
frequencies. Use the available data as an advisory diagnostic, not a target
distribution the bot must imitate or a replacement for the strength gate.

### Sources and observed outcomes

The official [WBC 2024 report](https://www.boardgamers.org/yearbook24/tws.html)
and [WBC 2025 report](https://www.boardgamers.org/yearbook25/tws.html) provide
the following counts. Percentages are calculated from all reported games,
including resignations and games with an unreported ending type.

| Ending | WBC 2024: 56 games | WBC 2025: 60 games |
|---|---:|---:|
| Automatic victory before final scoring | 24 (42.9%) | 27 (45.0%) |
| Final scoring | 19 (33.9%) | 6 (10.0%) |
| Wargames | 6 (10.7%) | 6 (10.0%) |
| DEFCON 1 | 3 (5.4%) | 7 (11.7%) |
| Resignation | 4 (7.1%) | 8 (13.3%) |
| Unreported | 0 (0%) | 6 (10.0%) |

Both events used a nonstandard half-point China Card tiebreaker. Preserve
the reports' broad "automatic victory" category rather than silently
equating it with VP-track victories alone. The large year-to-year variation
also argues against treating either small sample as a universal target.

The [BPA 2026 Round 4 results](https://twstourney.wordpress.com/2026-round-4/)
record individual games with side, bid, ending type and turn, including VP,
Wargames, DEFCON, Europe control and final scoring. These round tables are
a promising source for a cleaned multi-round ending-turn dataset. They
were inspected, not yet imported or validated as a complete dataset.

For card usage, ACTS journals are a possible extraction source: card plays
and accompanying action descriptions can support reconstruction, but the
descriptions require interpretation. See the
[Vassal discussion explaining ACTS journals](https://forum.vassalengine.org/t/twilight-struggle/10848).
No consistently covered downloadable tournament action corpus was verified.

### Initial comparison with an existing bot benchmark

Inspected `logs/game-check/gate-9d9890f/full-vs-base.json`, containing 64
games of that revision against its baseline:

- VP-track endings: 45/64 (70.3%).
- Final scoring: 17/64 (26.6%).
- Wargames: 2/64 (3.1%).
- DEFCON: 0/64.
- Ending turns: T4: 4, T5: 6, T6: 8, T7: 2, T8: 3, T9: 6, T10: 35.

Thus 35/64 games ended on turn 10, which is not the same as reaching final
scoring. This is an older bot-versus-predecessor sample, not a measurement
of the current working tree. Opponents, rules and human resignations make
the tournament comparison non-equivalent. The lower Wargames frequency is
a reason to inspect missed opportunities and timing, not evidence that its
weight should simply be increased. Zero bot nuclear losses should not be
"calibrated" upward to match humans.

### Proposed use without MCTS

1. Add behavioral reporting to games already run by the gate: ending
   turn/reason, side, scoring-card timing and each card's chosen use. This
   requires instrumentation, but no additional games or search.
2. Separate headline events, voluntarily chosen action-round events,
   opponent events triggered alongside operations, space attempts,
   discards and held cards. A single "percentage evented" confounds
   preference with forced execution. Compare individual cards by side and
   turn, with explicit denominators and eligibility/availability where
   observable; do not infer unseen hands from aggregate result records.
3. Use human/bot differences to choose investigations and regression
   positions: missed Wargames opportunities, unusual scoring timing, or
   cards consistently valued differently. A mismatch poses a question;
   it does not establish a strategic error.
4. With a sufficiently clean dataset, use ending-turn records as a rough
   prior for reaching future scoring opportunities. Position-level records
   would allow conditioning on current turn, VP and board state. Do not
   apply an unconditional game-length distribution as though every current
   position has the same remaining horizon.
5. Keep cohorts comparable by rules, optional cards, starting bid/bonus,
   player strength and tournament format. Treat resignations, timeouts and
   missing outcomes separately; removing them can itself introduce bias.
   Reserve independent games/tournaments for validation if these data are
   used to select parameters.

Recommendation: build an advisory human-reference diagnostic alongside the
gate, then use it to prioritize targeted evaluator fixes. Matching human
aggregate frequencies is not proof of strength, and human error rates are
not desired bot behavior. No bot code, weights or gate thresholds were
changed as part of this research or its documentation.
