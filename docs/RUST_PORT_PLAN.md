# Rust port plan (revised after Astra's review)

Status: revision 3, Sept 2026. Astra agreed to **Option C** as a bounded
measurement stage, with the order revised as below (`docs/CODEX_NOTES.md`,
"Revision 2 / Option C decision"). Nothing ported. Toolchain (rustup,
maturin) installed. Author: Claude (Fable). Reviewer: Astra. The Option C
section is the current scope; the later sections describe the Rust stage
that C may or may not lead to, and are consistent with it.

## The decision this revision asks for: Option C

The first draft promised that a native evaluator would turn 24 MCTS
simulations into thousands. Astra's Amdahl budget shows it cannot: the
evaluator's placement loop is ~72 % of search time, so a 20-50x kernel
gives 3.2-3.4x on search, and an infinitely fast one 3.6x. On full games
the evaluator is ~25 %, a ceiling of 1.33x. Thousands of simulations would
need most of the rollout path native, whether that is the whole engine
(B), a narrower native rollout implementation, or parallel search; which
of those, if any, is C step 4's decision, not a premise.

Three options were put to the user:

- **A.** Evaluator-only port as planned: ~3x on search, ~2 weeks.
- **B.** Full engine + policy port for deep MCTS: a month or more, with A
  as its first stage.
- **C.** No Rust yet. Do the Python prerequisites that A and B both need
  (semantics freeze and parity corpus, evaluator indexing, DEFCON
  memoisation), measure what they alone deliver on the two workloads,
  then choose A or B with real numbers.

**Proposed: C.** Reasons: two of its three steps are required by A and B
anyway; the enum-and-dict overhead (12 % of a full game) and the DEFCON
planner's repeated per-card predicates (3.5-4 M calls a game) are
possible savings that indexing and memoisation may recover without a
toolchain, to be measured, not assumed (the planner already caches its
solve);
the measurement it produces is exactly what the A-versus-B decision
lacks; and it defers writing the evaluator three times (dict Python,
array Python, Rust) until the array Python version has proven itself.

What C does *not* claim: it will not make deep MCTS possible. If after C
the search is still bound by the evaluator, A follows; if the user wants
deep MCTS, B follows and C's corpus and indexing are its first stage.

Astra's decision: yes, as a bounded measurement stage, not a commitment
to finish an array-Python rewrite before Rust is considered. No predicted
speedup is approved. Deep MCTS does not logically require the whole
engine native; that stays an option to justify with measurements and a
latency target.

## Option C, step by step (Astra's order)

Each step is its own commit, gated by `scripts/gate.sh` for strength
(these are meant to be behaviour no-ops) and by the parity corpus for
exactness. Each optimisation is measured on its own, so attribution is
not lost.

1. **Parity corpus and fresh baseline timings, from the current code.**
   The generator records positions and the current outputs: for the
   evaluator, `delta` per candidate and point count, `influence` and
   `_investment`, `ops_value` for 1-4 Ops, `country_value` for every
   country, `region_score` and `region_margin` per region, and the full
   `rank_actions` ordering with safety keys; for the planner, the DEFCON
   risk per card and per play mode with its inputs (hand, DEFCON, turn
   effects, Space Race state, China, traps, pending headline, learned
   prior in use, truncation reached or not). Positions: gate seeds at
   several turns, both seats; MCTS rollout and event-sandbox positions
   from the corrected policy; generated boundary cases (enemy-control cost
   transitions, tier thresholds, Europe control, zero and near-tied gains,
   bonus Ops, turn effects, influence extremes, planner truncation).
   Baseline profiles on the same snapshot: a strategic full game, and
   MCTS at 24 simulations on frozen opening, scoring and hazardous
   late-game positions. Stored under `tests/corpus/`; regenerated only by
   an explicit, reviewed commit. Captured after the MCTS fixes (98cdc1f,
   95deb39), which were intentional behaviour changes, and before
   anything else.
2. **DEFCON planner: predicate hoisting and memoisation, measured alone.**
   `DefconPlanner` already caches `solve` and `_event_risk` with
   `lru_cache`; the millions of `opponent_event` / `hazardous` calls are
   inside those, so another cache is not assumed to help. Measure hits,
   misses and key-construction cost first; hoist the enum attribute
   lookups; make `opponent_event` a per-card lookup; memoise `hazardous`
   on (card, hand multiset, DEFCON) only if the measurement says so.
   Hazard-at-DEFCON-2 semantics and `@replacement` multiplicity intact.
   Parity: identical risks on the corpus.
3. **Evaluator indexing, incrementally.** Slices (static per-country
   arrays; influence arrays per decision; adjacency index lists; the
   weights schema), each with parity and whole-workload timing. If
   conversion or Python indexing overhead erases the gain, stop; a Rust
   kernel can take arrays while the dict-based Python evaluator stays the
   reference. The engine's representation does not change.
4. **Decide**, with the fresh Amdahl fractions: keep the Python gains
   only, a batched Rust kernel (`evaluate_placements`), parallel search,
   or a broader native rollout implementation.

## What the profiles say

Two workloads, two different hot paths. Cumulative times overlap and must
not be added.

| Workload | Dominant path | Share | Source |
| --- | --- | ---: | --- |
| Strategic vs strategic, full game (25.6 s profiled, 13.4 s plain) | `bots/defcon.py` whole-hand survival search (`_solve`, `_after_hand_attack`, `hazardous`, `opponent_event`: 3.5-4 M calls of per-card predicates) | ~60 % | Claude, seed 4000 |
| same | evaluator: `country_value` 347 k, `_access` 338 k, `delta` 184 k, `influence`/`_investment` | ~25 % | Claude |
| same | enum attribute access (`Side.value`, `.opponent`): 11 M lookups | ~12 % | Claude |
| MCTS, 24 simulations, one opening decision (48.9 s profiled, 22.2 s plain) | rollout ranking: `delta()` 157 k calls, 72 % of search | ~93 % | Astra |
| same | DEFCON module exclusive | 0.7 % | Astra |
| same | leaf `value()` | 0.8 % | Astra |

Amdahl budget (Astra): whole-workload speedup is 1 / ((1 - p) + p / s)
for an accelerated fraction p at kernel speedup s.

| Workload | p covered by an evaluator port | s = 20 | s = 50 | s -> inf |
| --- | ---: | ---: | ---: | ---: |
| MCTS search (delta share) | 0.72 | 3.2x | 3.4x | 3.6x |
| MCTS search (all rollout ranking) | 0.93 | 8.6x | 11.3x | 14.3x |
| Strategic full game (evaluator share) | 0.25 | 1.3x | 1.3x | 1.33x |
| Strategic full game (evaluator + planner; hypothetical, the planner is not in the proposed scope) | 0.85 | 5.2x | 6.0x | 6.7x |

The trivial-bot game time (1.1 s of 13.4 s, 8.2 %) bounds the engine's
share from above only loosely; it was not profiled separately.

**Re-measured 2026-09-09, after the pure-function extraction** (Claude), on
a whole benchmark game -- the workload `scripts/gate.sh` actually runs --
rather than on saved positions:

| Module (exclusive time) | Share |
| --- | ---: |
| `evaluator.py` (the proposed port) | 45.8 % |
| `strategic.py` (policy, caches, sandbox driving) | 19.8 % |
| built-ins (`max`/`min`/`any`/`dict.get`), mostly from evaluator loops | 15.3 % |
| `board.py` + `core.py` (the engine, explicitly not ported) | 9.5 % |
| `defcon.py` (the planner, explicitly not ported) | 3.3 % |

So p = 0.458 for a strategic full game, not the 0.25 recorded above: the
extraction moved terms into `evaluator.py` that were spread across
`strategic.py`, and the `Board.serialize` deepcopy that was inflating the
non-evaluator share is gone. The ceiling is **1.84x at s -> infinity**, and
about 2.2x if the port also absorbs the built-ins those loops call. Two
cautions on both numbers: `cProfile` charges per-call overhead and so
flatters exactly this kind of code, and MCTS is not in this workload at all.

**Standing recommendation (Claude, 2026-09-09): not yet.** Three reasons,
in order of weight.

1. *The semantics are not frozen, and the plan's own first condition is
   that they are.* `region_vp`, `country_value` and `board_value` all
   changed signature in a single day (scoring overrides, then Coup
   prohibitions). A port has to be bitwise-identical to whatever it copies,
   so every semantic change during a port is paid for twice.
2. *It cannot reach 5x on the workload that measures strength today.* The
   gate plays strategic against strategic, where the ceiling is under 2x.
   The 3.2-3.6x row is MCTS search, and the 8.6-14.3x row is a port of all
   of rollout ranking -- a bigger scope than the kernel list in this plan.
   Anyone quoting a large number should say which row it comes from.
3. *Evaluation consistency is still the binding constraint, not speed.* Four
   correctness defects landed on 2026-09-09, two of them live engine rules
   bugs (the missing Containment/Brezhnev Ops ceiling, and the unmodelled
   China Card + Vietnam Revolts bonus stack). Searching deeper with wrong
   values finds worse moves more confidently.

What to do instead, while those settle: profile the workload the gate runs
and fix what it names. An afternoon of that bought 1.1x
(`docs/STRATEGIC_AI.md`), and it found the two largest costs outside the
evaluator entirely, which no amount of evaluator microbenchmarking would
have surfaced. `access` is now the single largest term at 283 k calls and
about 11 % of a game, and is the obvious next target.

Revisit the port when the evaluator's signatures have been stable for a
stretch, and when there is evidence that search depth rather than
evaluation quality is what limits playing strength.

Conclusions the plan rests on:

- The exact semantics are frozen first. `delta()` values the changed
  country plus the region terms (score and margin); it does not
  re-evaluate neighbours whose access changed, so it is *not* the change
  in the board value. The port reproduces `delta` as it is; a full-board
  before/after delta is a separate, gated algorithm change. Cache removal
  can expose frozen dependencies (`_base_regions`, the per-decision
  caches) and change results, which is why the corpus precedes it.
- The evaluator's *placement search* (`delta` and the loops that call it)
  is the shared hot path. Porting `value()` alone at MCTS leaves would miss
  almost all of it (Astra). Porting `country_value` alone would drown in
  boundary crossings: 350 k calls of a few microseconds each.
- The DEFCON planner matters for plain play and for rollouts that use the
  full policy, not for the search tree itself. It is second, and its
  priority should be re-checked on hazardous late-game hands, where the
  recursive planner's workload differs from the opening (Astra).
- Before any acceleration is measured, the three MCTS correctness findings
  in Astra's audit (leaf context inherited from the last ranking, served
  plans suppressing targets, the ranking cache not syncing the board) had
  to be fixed and pinned by regressions, or speed and semantics changes
  would be confounded. Done, Sept 2026 (98cdc1f and the commit after).

## Boundary

One extension module, `struggler_native`, built with PyO3 and maturin
from `rust/` beside `src/`. Python owns all state; Rust receives plain
arrays and returns plain arrays or floats. No Python object is touched
inside a Rust loop.

### Static tables, built once per process

Country index 0..N-1 in a fixed order (the order of `countries.json`).
Per country: stability, battleground flag, region index, coup minimum
DEFCON, adjacency as index lists, superpower adjacency per side. Card
table: side, Ops, scoring flag. Region table: member index lists, the
presence/domination/control VP. Built in Python from the existing data
and passed to Rust once (`Tables::new`), held in a `PyCell`.

### Per-decision context

Weights (the `StrategicWeights` fields as an f64 array in a fixed order),
the per-country scoring weight array, DEFCON, side, and the two scoring-
override flags (Formosan Resolution, Shuttle Diplomacy) plus the region
index the second is spent on. Passed once per `rank_actions`, not per call.
The flags rather than the resulting country sets: the sets are a function
of control, which every trial placement can move, so they are derived
inside the kernel exactly as `evaluator.scoring_overrides` derives them.

### Calls, in port order

1. `evaluate_placements(us: &[i16], su: &[i16], side, ops, candidates: &[u16], ctx) -> Vec<(f64, u8)>`
   The influence search: for each candidate country, the best value per
   Op of investing 1..ops points there (`_investment` / `influence`), with
   the doubled cost past enemy control, reproducing `delta()` exactly: the
   changed country's value (whose access term reads its neighbours'
   influence without rescoring them) plus the region score and margin.
   This is the call that covers the `delta` share of both workloads
   (53-73 % measured); actual coverage is measured, not assumed.
2. `board_value(us, su, side, ctx) -> f64` The leaf: sum of country terms,
   region score, region margin. Cheap, needed for MCTS leaves and for
   parity tests.
3. `coup_values(us, su, side, ops, candidates, ctx) -> Vec<f64>` and
   `realign_values(...)`: same board delta with the dice enumerated.
4. There is no native DEFCON solve. Its state contract is too large to
   freeze cheaply and its predicates are state-dependent (see Option C
   step 2); the planner stays in Python, memoised.

Not ported: the engine, events, the event sandbox, the DEFCON planner,
`ops_value`'s card logic (its investment loop is part of the workload and
is a candidate for the second batched call), the opponent model, MCTS
tree management, hidden-state sampling, logging.

### Python side

`bots/evaluator.py` grows the table builders and a `Native` wrapper with
the same three functions in pure Python. `STRUGGLER_NATIVE=0` forces the
Python path. The strategic player calls the wrapper; nothing else changes.
Weights keep their names; the array order is defined in one place.

## Prerequisites in Python

Option C above is the prerequisite list, in Codex's order: corpus and
baselines, planner memoisation, incremental indexing, decide.

The pure-function evaluator is **done** and landed ahead of that order,
because it turned out to be the fix for a correctness defect rather than
only a porting convenience: two memos in `StrategicPlayer` were keyed on
less state than the terms read, and the same position scored differently
depending on what had been evaluated first. `bots/evaluator.py` now holds
the country, access, wipe, region and margin terms as functions of
`(Terrain, Position, weights, urgency, defcon)` -- no reads of `self._obs`,
`board`, `RULES` or any memo. That module is the data layout below, in
Python: `Terrain` is the static tables a kernel would receive once,
`Position` the influence plus derived control and reachability vectors, and
countries are already indices into `data/countries.json` order. The
remaining Python-side prerequisite is the indexing measurement, not the
extraction.

## Verification

Oracle discipline (Astra, revision-3 check): the corpus records, per
case, the production ranking from the in-game bot with the planner node
budget it consumed, then probes on an independent instance in a recorded
order, so a diagnostic query can never push the production planner past
`max_states`; the prior (including `max_states`), decision options and
context, and the source revision are stored. Hand iteration order is
preserved where it affects traversal or summation.

- Bit-for-bit is not the target; floating-point summation order will
  differ. The target is identical rankings and top actions on the
  corpus, values within an absolute plus relative tolerance (near-zero
  values need the absolute term), and deterministic tie-breaks fixed by
  candidate order in both implementations, not by rounding in tests.
- Full-game parity is trace parity, not a head-to-head score: run
  Python/Python and native/native games separately on identical seeds
  and compare action and chance traces and final states. Compare
  fixed-simulation MCTS root statistics too. A 0.5 score with equal VP
  proves nothing about identical actions.
- The suite runs twice in CI: `STRUGGLER_NATIVE=0` and `1`.
- Speed is measured only on a frozen checkout with nothing else running:
  the gate script's snapshot worktree. Whole-decision wall time including
  conversion, then playing strength at equal wall time (Astra).
- Algorithm changes and acceleration never share a commit.

## Effort and order

| Step | Size | Depends on |
| --- | --- | --- |
| MCTS fixes and regressions | done | none |
| Parity corpus and baseline timings | 1 day | none (C step 1) |
| DEFCON memoisation, measured alone | 1 day | corpus (C step 2) |
| Indexing, incremental slices | 1-2 days | corpus (C step 3) |
| Decide | half a day | above (C step 4) |
| Pure-function evaluator | done | none |
| `evaluate_placements` + `board_value` in Rust, parity | 3-5 days | corpus |
| coup/realign values | 1 day | above |

About two weeks of focused work, with the first three steps useful on
their own. Rust knowledge on the user's side is not required: the module
is a few hundred lines with the Python path kept as the oracle.

## Data layout (the contract both sides compile against)

- Country order: the key order of `data/countries.json`, fixed; `N` is
  derived from the shared tables (85 today), never hard-coded. Python
  builds the tables and passes them once; the module exports the order
  it was built with and every later call is validated against it.
- Influence: two `int16[N]` arrays, US then USSR (no engine-wide cap is
  enforced, so no byte type; conversion is checked and a value outside
  the supported range raises, never wraps or saturates). Differences and
  removals use signed intermediates.
- Static per-country: `stability: u8[N]`, `battleground: bool[N]`,
  `region: u8[N]` (index into the region table, in `Region` enum order),
  `coup_min_defcon: u8[N]`, `adjacency: Vec<Vec<u16>>`, `home_us` and
  `home_ussr: Vec<u16>`.
- Region table: `members: Vec<Vec<u16>>`, `presence/domination/control
  VP: i16` (control `-1` for Europe's non-numeric tier).
- Context per decision: `weights` as a versioned schema (field names and
  order checked, not just the count), `scoring_weight: f64[N]`, `defcon`,
  `side`, `ops_scale: f64[5]`. Coup and realignment calls additionally
  take precomputed roll modifiers, legal candidate lists and the
  military-Ops state; the phasing/effect logic that produces them stays
  in Python. The DEFCON solve is out of scope for the port (see Option
  C step 2): its state contract (rounds, Space Race, China, traps,
  pending headline, discard chains, learned priors, truncation) is too
  large to freeze cheaply.
- Returns: `Vec<f64>` or `Vec<(f64, u8)>`; errors are Python exceptions
  raised by PyO3 for shape mismatches, never silent defaults.

## Build, packaging and CI

- `rust/Cargo.toml` (crate `struggler_native`, `cdylib`, PyO3 with the
  `extension-module` feature, `abi3-py312`); `rust/pyproject.toml` for
  maturin. Development: `uv run maturin develop --release -m
  rust/Cargo.toml` (the `-m` flag takes the Cargo manifest) installs
  into the project venv; discovery and a clean install are verified with
  the final layout before the command is documented as working. Release: `maturin
  build --release` produces a wheel; the wheel is committed nowhere, the
  build is reproducible from source.
- `STRUGGLER_NATIVE` unset: use the module if it loads, else Python,
  logged once. `=0`: Python. `=1`: the module must load or the process
  fails loudly; at least one CI job builds it and asserts native
  execution, so the two test runs cannot both silently be Python.
- The gate snapshot freezes Python source but not an extension installed
  in the shared venv: the gate builds the extension from the snapshot
  and records its source revision, artifact hash, loaded path and build
  mode. A `strategic@<old file>` baseline is not isolated once it imports
  a shared evaluator wrapper; baselines pin the wrapper too.
- CI matrix: the suite with `STRUGGLER_NATIVE=0` (always) and `=1` (when
  the toolchain is available), plus `tests/test_native_parity.py`, which
  loads the frozen corpus and asserts rankings equal and values within
  tolerance for every snapshot.
- The gate script gains a `NATIVE=0|1` knob so both paths can be gated on
  the same snapshot.

## Risks and how each is handled

| Risk | Handling |
| --- | --- |
| Floating-point summation order changes tie-breaks between near-equal placements | Each operation keeps its *existing* tie rule and the port reproduces it: `RolloutPolicy.score` resolves equal values by country-string order (`max` over `(value, country)`), `_investment` keeps the first best point count (strict `>`), action sorting is stable on its own key. The corpus includes tied cases; any standardisation is a separate semantic commit. Parity is exact rankings and top actions, values within absolute plus relative tolerance. |
| Hidden coupling: the evaluator reads `_base_regions`, `_scoring_weights`, `_obs`, `RULES` through `self` | Removed: the terms live in `bots/evaluator.py` and take `(Terrain, Position, weights, urgency, defcon)`. `_scoring_weights` is gone, replaced by an urgency vector computed once per decision; the margin basis is passed as an argument rather than read from `self`. The Python fallback is that pure function, so both paths share one contract. |
| A baseline loaded by `strategic@<file>` silently uses the *candidate's* evaluator | `benchmark.load_module` binds an `evaluator.py` sitting beside the baseline file in place of the candidate's while the baseline executes, and `gate.sh` snapshots both files per revision. Without it, a gate spanning an evaluator change reports the candidate playing itself. |
| Boundary cost dominating if the granularity is wrong | `evaluate_placements` takes all candidates at once; measured whole-decision wall time including conversion is the acceptance metric. |
| Behaviour drift from an "accidental" fix while porting | Algorithm changes and acceleration never share a commit; the corpus is regenerated only by an explicit, reviewed commit. |
| Maintenance with no Rust on the user's side | Module under ~600 lines, one file per call, Python oracle kept indefinitely, `STRUGGLER_NATIVE=0` restores the old behaviour in one environment variable. |
| Engine hot path emerging once the evaluator is fast | Profile again after step 4 before deciding; the engine stays in Python until it is the measured bottleneck. |

## Acceptance: three separate decisions

1. **Semantic parity** (the port is correct): corpus rankings, top
   actions and values as above; full-game trace parity on the gate seeds.
2. **Measured acceleration** (the port is worth keeping): per-stage
   targets set from the Amdahl table, not a blanket 3x. For the
   evaluator port: at least 15x on `evaluate_placements` in isolation and
   at least 2.5x on MCTS search wall time at fixed simulations, on a
   gate snapshot with nothing else running. Missing a target says the
   boundary or the kernel needs work, not by itself that the boundary is
   wrong.
3. **Promotion** (the resulting MCTS is the bot): paired-seat results
   with uncertainty clustered by seed, against the corrected Python MCTS
   at equal wall time and against strategic; 64 seeds is a planned
   sample size, not a detection guarantee. This is the reason to do the
   port at all, but it is a search-quality question, and a correct fast
   port that loses it is still a valid port.

The two-week and ~600-line figures are planning assumptions.

## Ownership

Claude writes the Rust, the Python refactors and the corpus; Astra
audits the boundary, the parity evidence and the profiles; the user
decides the acceptance calls and runs nothing but the gate script.

## Reviewer answers (Astra) and remaining question

- Boundary: batched `evaluate_placements`, with legal candidate
  generation and survival ordering staying in Python; a second batched
  greedy-spend operation for `ops_value` / `_placement_plan` only after
  measuring the first. The initial legal candidate set is preserved
  across a spend (rule 6.1.1). `ops_value`'s investment loop is part of
  the workload and is documented as such.
- Corpus: yes to rollout and event-sandbox positions, both seats,
  several turns, generated boundary cases, with candidate order, Ops
  budget, context and expected point counts. Extended for each later API.
- Indexing: evaluator-local, engine representation unchanged, gain
  measured not assumed, kept small enough not to maintain the evaluator
  three times.

Option C: agreed by Astra with the order above. Revision 3 consolidates
the leftovers Astra listed (prerequisite order, `u8` in signatures, the
native DEFCON solve and hazard masks, rounding in the risk table, the
evaluator-plus-planner Amdahl row).
