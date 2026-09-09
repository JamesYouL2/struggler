# Astra scratchpad

## 2026-09-08 — MCTS audit and Rust port assessment

Scope: quick review of `bots/mcts.py`, `bots/rollout.py`,
`bots/defcon.py`, and the strategic evaluation helpers. No implementation
changes made during this audit. HEAD was `cc7bfb0` and the working tree was
initially clean. `src/struggler/bots/strategic.py` changed externally while
the audit ran; the findings and profile concern the code loaded before
those edits, not a review of the subsequent changes.

The detailed Fable Rust plan was not found. `docs/CLAUDE_NOTES.md` mentions a Rust
speedup, but does not specify its implementation. The recommendation below
assesses the user's description: port DEFCON helpers and evaluation.

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
2. Obtain/review Fable's concrete Rust API and port scope.
3. Profile frozen opening, scoring, and hazardous late-game positions.
4. Choose a native boundary covering repeated evaluation work and measure
   end-to-end benefit without changing the corrected policy semantics.

Audit limits: no full rules-engine review, no exhaustive DEFCON semantic
audit, no Rust implementation benchmark, and no playing-strength comparison.
