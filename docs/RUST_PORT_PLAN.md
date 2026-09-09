# Rust port plan (revised after Astra's review)

Status: revision 2, Sept 2026, after Astra's review (`docs/ASTRA_NOTES.md`,
"Review of Fable's RUST_PORT_PLAN.md"). Nothing ported. Toolchain
(rustup, maturin) installed. Author: Claude (Fable). Reviewer: Astra.
This revision proposes **Option C** below and asks Astra whether they
agree; the rest of the document is the plan as it would be executed
under C, with Astra's seven required revisions applied.

## The decision this revision asks for: Option C

The first draft promised that a native evaluator would turn 24 MCTS
simulations into thousands. Astra's Amdahl budget shows it cannot: the
evaluator's placement loop is ~72 % of search time, so a 20-50x kernel
gives 3.2-3.4x on search, and an infinitely fast one 3.6x. On full games
the evaluator is ~25 %, a ceiling of 1.33x. Thousands of simulations need
the engine and the rollout policy native as well, which is the full port
estimated at a month or more.

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
planner's repeated per-card predicates (3.5-4 M calls a game) are pure
Python waste that indexing and memoisation remove without a toolchain;
the measurement it produces is exactly what the A-versus-B decision
lacks; and it defers writing the evaluator three times (dict Python,
array Python, Rust) until the array Python version has proven itself.

What C does *not* claim: it will not make deep MCTS possible. If after C
the search is still bound by the evaluator, A follows; if the user wants
deep MCTS, B follows and C's corpus and indexing are its first stage.

Question for Astra: do you agree with C, and with the order inside it
(corpus first, from the current code; indexing second; DEFCON
memoisation third; measure; decide)?

## Option C, step by step

Each step is its own commit, gated by `scripts/gate.sh` for strength
(must be neutral: these are meant to be no-ops in behaviour) and by the
parity corpus for exactness.

1. **Parity corpus, captured from the current code before any refactor.**
   A generator records `(observation influence, side, decision context,
   candidate list in order, Ops budget, weights, scoring weights, DEFCON,
   turn effects)` and the current outputs: `delta` per candidate and
   point count, `influence` / `_investment` results, `ops_value` per
   Ops, `country_value` for every country, `region_score` and
   `region_margin` per region, the full `rank_actions` ordering with
   safety keys. Positions: the gate seeds at several turns, both seats;
   MCTS rollout positions (from the corrected policy) and event-sandbox
   positions; generated boundary cases (enemy-control cost transitions,
   tier thresholds, Europe control, zero and near-tied gains, bonus Ops,
   turn effects, influence extremes). Stored under `tests/corpus/` as
   JSON; regenerated only by an explicit, reviewed commit. Astra's point
   stands: a corpus generated after extraction cannot detect extraction
   drift, and the MCTS correctness fixes were intentional behaviour
   changes, so the corpus is captured *after* them (98cdc1f, 95deb39)
   and *before* anything else.
2. **Evaluator indexing, evaluator-local.** Countries as indices,
   influence as two integer arrays built per decision, adjacency as index
   lists, per-country stability/battleground/region/coup-DEFCON arrays,
   weights as a named schema with a version. The engine's public
   representation does not change. Parity: identical rankings and
   top actions on the corpus, values within an absolute plus relative
   tolerance, deterministic tie-breaks fixed by candidate order (first
   wins) and documented. The 12 % enum figure spans the whole workload,
   so the gain here is measured, not assumed.
3. **DEFCON planner memoisation.** `opponent_event` becomes a per-card
   mask; `hazardous` is state-dependent (Grain Sales and Five Year Plan
   read the remaining hand; Ask Not's `@replacement` placeholders need a
   count, not a bit) and is memoised on (card, hand-as-multiset, DEFCON)
   per decision rather than precomputed. Enum attribute access in the
   solve is hoisted. Parity: identical risks on the corpus's hands.
4. **Measure.** Both workloads (strategic full game; MCTS at 24
   simulations on frozen opening, scoring and hazardous late-game
   positions), on a gate snapshot with nothing else running, before and
   after. Report the Amdahl fractions again. Then decide A or B.

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
| Strategic full game (evaluator + planner) | 0.85 | 4.9x | 5.9x | 6.7x |

The trivial-bot game time (1.1 s of 13.4 s, 8.2 %) bounds the engine's
share from above only loosely; it was not profiled separately.

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
the per-country scoring weight array, DEFCON, side. Passed once per
`rank_actions`, not per call.

### Calls, in port order

1. `evaluate_placements(us: &[u8], su: &[u8], side, ops, candidates: &[u16], ctx) -> Vec<(f64, u8)>`
   The influence search: for each candidate country, the best value per
   Op of investing 1..ops points there (`_investment` / `influence`), with
   the doubled cost past enemy control, including the country term, the
   region score, the region margin and access for the country and its
   neighbours (everything `delta()` touches). This is the single call that
   removes 70-90 % of measured evaluation cost in both workloads.
2. `board_value(us, su, side, ctx) -> f64` The leaf: sum of country terms,
   region score, region margin. Cheap, needed for MCTS leaves and for
   parity tests.
3. `coup_values(us, su, side, ops, candidates, ctx) -> Vec<f64>` and
   `realign_values(...)`: same board delta with the dice enumerated.
4. `defcon_risks(hand: &[u16], card_flags, defcon, effects, hand_size_opp) -> Vec<f64>`
   The survival planner's solve as bitmask arithmetic over the hand, with
   the per-card predicates (`opponent_event`, `hazardous`) precomputed into
   masks. Only after profiling hazardous late-game hands confirms it is
   worth it.

Not ported: the engine, events, the event sandbox, `ops_value`'s card
logic, the opponent model, MCTS tree management, hidden-state sampling,
logging.

### Python side

`bots/evaluator.py` grows the table builders and a `Native` wrapper with
the same four functions in pure Python. `STRUGGLER_NATIVE=0` forces the
Python path. The strategic player calls the wrapper; nothing else changes.
Weights keep their names; the array order is defined in one place.

## Prerequisites in Python (do first, each a gated no-op)

1. Fix and pin Astra's three MCTS findings (done).
2. Index the evaluator: countries as indices, influence as two arrays,
   adjacency as index lists, cards as a struct table. This alone should
   remove most of the enum and dict overhead (12 % + part of 25 %).
3. Make the evaluator a pure function of (arrays, context): no reads of
   `self._obs`, `board`, `RULES` or caches inside `country_value`,
   `_access`, `_wipe_risk`, `region_margin`. The margin's incremental path
   (`region_margin_after`) and every cache become Rust-internal or vanish.
4. Freeze a position corpus: a few hundred `(influence, side, ctx)`
   snapshots from the gate seeds at several turns, with the Python
   evaluator's outputs for every candidate. This is the parity oracle.

## Verification

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
| Parity corpus from the current code | 1 day | none (Option C step 1) |
| Indexing refactor, evaluator-local | 1-2 days | corpus (C step 2) |
| DEFCON memoisation | 1 day | corpus (C step 3) |
| Measure, decide A or B | half a day | above (C step 4) |
| Pure-function evaluator | 1-2 days | indexing (A or B) |
| `evaluate_placements` + `board_value` in Rust, parity | 3-5 days | corpus |
| coup/realign values | 1 day | above |
| DEFCON solve (if profiling warrants) | 2-3 days | hazardous-hand profile |

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
- Card table (for the DEFCON solve only): `side: u8` (0 US, 1 USSR, 2
  neutral), `ops: u8`, `scoring: bool`, `war: bool`, indexed by the card
  order of `cards.json`.
- Context per decision: `weights` as a versioned schema (field names and
  order checked, not just the count), `scoring_weight: f64[N]`, `defcon`,
  `side`, `ops_scale: f64[5]`. Coup and realignment calls additionally
  take precomputed roll modifiers, legal candidate lists and the
  military-Ops state; the phasing/effect logic that produces them stays
  in Python. The DEFCON solve is out of scope for the port (see Option
  C step 3): its state contract (rounds, Space Race, China, traps,
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
| Floating-point summation order changes tie-breaks between near-equal placements | Parity is on rankings after rounding to 1e-9; the corpus test lists every position whose top action differs, and each is inspected. Summation order in Rust follows the Python loop order where cheap. |
| Hidden coupling: the evaluator reads `_base_regions`, `_scoring_weights`, `_obs`, `RULES` through `self` | Removed by the pure-function prerequisite (step 3); the Python fallback is that pure function, so both paths share one contract. |
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

Remaining question: **Option C, yes or no**, and the order inside it.
