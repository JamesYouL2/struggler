# Rust port plan (draft for audit)

Status: proposal, Sept 2026. Nothing ported yet. Toolchain (rustup,
maturin) is installed on the development machine. Author: Claude (Fable).
Reviewer: Astra (see `docs/ASTRA_NOTES.md` for the MCTS audit this plan
answers).

## Goal

Make search affordable without changing what the bot decides. The
strategic policy plays a full game in about 13 s; a trivial bot plays one
in 1.1 s, so the engine is under 5 % of the cost and the two hot paths are
the evaluator's placement search and the DEFCON survival planner. A
compiled evaluator that owns whole loops should give 20-50x on those
paths, which turns 24 MCTS simulations into thousands at the same wall
time. Python keeps the engine, the rules, the events, the card sandbox,
the opponent model and every decision that runs once per action.

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

Conclusions the plan rests on:

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
  differ. The target is identical *rankings* and values within 1e-9
  relative on the corpus, and identical actions over full games on the
  gate seeds (`benchmark --bot strategic --opponent strategic@<python
  snapshot>` must score exactly 0.5 with identical VP per game).
- The suite runs twice in CI: `STRUGGLER_NATIVE=0` and `1`.
- Speed is measured only on a frozen checkout with nothing else running:
  the gate script's snapshot worktree. Whole-decision wall time including
  conversion, then playing strength at equal wall time (Astra).
- Algorithm changes and acceleration never share a commit.

## Effort and order

| Step | Size | Depends on |
| --- | --- | --- |
| MCTS fixes and regressions | done | none |
| Indexing refactor | 1-2 days | none |
| Pure-function evaluator + corpus | 1-2 days | indexing |
| `evaluate_placements` + `board_value` in Rust, parity | 3-5 days | corpus |
| coup/realign values | 1 day | above |
| DEFCON solve (if profiling warrants) | 2-3 days | hazardous-hand profile |

About two weeks of focused work, with the first three steps useful on
their own. Rust knowledge on the user's side is not required: the module
is a few hundred lines with the Python path kept as the oracle.

## Data layout (the contract both sides compile against)

- Country order: the key order of `data/countries.json`, fixed; `N` = 86.
  `struggler_native.COUNTRY_ORDER` is exported and checked at import
  against the Python board so a data change cannot silently skew indices.
- Influence: two `uint8[N]` arrays, US then USSR. Never negative; the
  engine caps well under 255.
- Static per-country: `stability: u8[N]`, `battleground: bool[N]`,
  `region: u8[N]` (index into the region table, in `Region` enum order),
  `coup_min_defcon: u8[N]`, `adjacency: Vec<Vec<u16>>`, `home_us` and
  `home_ussr: Vec<u16>`.
- Region table: `members: Vec<Vec<u16>>`, `presence/domination/control
  VP: i16` (control `-1` for Europe's non-numeric tier).
- Card table (for the DEFCON solve only): `side: u8` (0 US, 1 USSR, 2
  neutral), `ops: u8`, `scoring: bool`, `war: bool`, indexed by the card
  order of `cards.json`.
- Context per decision: `weights: f64[K]` in the field order of
  `StrategicWeights` (K is asserted equal on both sides), `scoring_weight:
  f64[N]`, `defcon: u8`, `side: u8`, `ops_scale: f64[5]` (the concave Ops
  scale the evaluator already computes).
- Returns: `Vec<f64>` or `Vec<(f64, u8)>`; errors are Python exceptions
  raised by PyO3 for shape mismatches, never silent defaults.

## Build, packaging and CI

- `rust/Cargo.toml` (crate `struggler_native`, `cdylib`, PyO3 with the
  `extension-module` feature, `abi3-py312`); `rust/pyproject.toml` for
  maturin. Development: `uv run maturin develop --release -m
  rust/pyproject.toml` installs into the project venv. Release: `maturin
  build --release` produces a wheel; the wheel is committed nowhere, the
  build is reproducible from source.
- The Python package imports the module inside `try`; absence or
  `STRUGGLER_NATIVE=0` selects the Python path and logs once at INFO. No
  test depends on the native module being present.
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

## Acceptance criteria

1. Parity: identical action rankings on every corpus position; values
   within 1e-9 relative; identical per-game VP on the gate seeds between
   `NATIVE=0` and `NATIVE=1` (`benchmark` score exactly 0.5).
2. Speed: at least 10x on `evaluate_placements` in isolation and at
   least 3x on a full strategic game, measured on the gate snapshot with
   nothing else running. Below that, the boundary is wrong and the plan
   returns to the granularity question.
3. Strength: MCTS at the wall-time budget of today's 24 simulations,
   with the corrected semantics, beats the plain strategic policy by more
   than two standard errors at 64 seeds. This is the point of the port;
   speed without it is not a result.

## Ownership

Claude writes the Rust, the Python refactors and the corpus; Astra
audits the boundary, the parity evidence and the profiles; the user
decides the acceptance calls and runs nothing but the gate script.

## Open questions for the reviewer

1. Is the `evaluate_placements` boundary the right granularity, or should
   the whole `rank_actions` for an Ops spend (candidates included) cross?
2. Should the corpus include MCTS rollout positions, which reach boards
   the strategic policy never does?
3. Enum overhead is 12 % on its own; is the indexing refactor worth
   landing even if the port stalls? (Claude: yes.)
