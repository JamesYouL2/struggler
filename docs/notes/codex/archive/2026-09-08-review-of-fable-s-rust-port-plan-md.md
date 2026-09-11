# 2026-09-08 — Review of Fable's RUST_PORT_PLAN.md

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
