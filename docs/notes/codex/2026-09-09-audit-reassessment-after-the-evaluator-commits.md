# 2026-09-09 — Audit reassessment after the evaluator commits

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
