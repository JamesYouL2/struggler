# Astra scratchpad

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
