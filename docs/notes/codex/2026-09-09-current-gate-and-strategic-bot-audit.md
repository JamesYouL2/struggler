# 2026-09-09 — Current gate and strategic-bot audit

This review was run against clean `HEAD` at `df29bf8`, after the risk and
sentinel fixes. The earlier high-priority event-risk defect is fixed. The
targeted regressions for Summit, Missile Envy, Five Year Plan, and the
simulated Summit ending pass. `event_value` now lets a sandboxed terminal
outcome own its probability, and `safety_key` charges only residual risk.

Verification at `df29bf8`: four targeted risk regressions passed. The earlier
581 passed, 3 skipped, and one parity-corpus failure result came from the
working tree before `df29bf8`, not from this revision. The full suite was not
rerun during this review. Review the intended corpus differences separately
before regeneration; a stale corpus alone does not establish a regression.

### Gate speed

The gate already has the two useful broad controls: it runs the tuning and
held-out samples in one worker pool, and `GATE_DECIDE=1` stops when the
remaining games cannot plausibly change the verdict. The early-stopping
validation recorded about 10.2% fewer games, with the known near-boundary
false-accept tradeoff. That is a useful saving, so the acceptance rule should
not be made more aggressive without new evidence.

The next cheap speedup is to remove duplicate opening work. `gate.sh` runs a
separate turn-3 checkpoint and then plays the same seeds as full games. The
full-game worker should record the turn-3 diagnostic while it is already
playing, allowing the separate checkpoint run to disappear. This must preserve
the checkpoint report for games stopped early and should remain a diagnostic,
not an acceptance criterion.

A current cProfile run of one strategic-versus-strategic full game (seed
4000) took 107.8 seconds under profiling. The cumulative hot paths were
`action_risk`/the DEFCON planner (about 49 seconds), `delta` (about 37
seconds), and `ops_value` (about 31 seconds); these timings overlap and are
profiling measurements, not additive wall-clock costs. The next performance
investigation should measure repeated `discard_risk`, coup-target planning,
and `delta` calls across several hazardous and ordinary positions. Any cache
must include every state input it reads. A native port is premature until
that repeated work is measured and a Python reference is frozen.

### Strategic-bot simplification

The most valuable structural simplification is to separate terminal outcomes
from numeric values. `LOSS` is an ordering sentinel, while event values,
hand values, Ops values, and game values are numeric prices. The current code
now protects that boundary with clamps and flags, and the tests cover the
known leaks, but an explicit result type or terminal-outcome field would
remove much of the sentinel plumbing and make composition safer.

The next low-risk simplification is to separate active policy parameters from
compatibility fields and experimental terms. `StrategicWeights` currently has
26 fields. `ops` is retained for old checkpoints but no longer affects the
main estimate; `wipe` and `wipe_backed` are disabled; and `progress_curve` is
intended to remain at its default linear shape. Keep old model files loadable,
but exclude retired or opt-in terms from ordinary mutation and report the
active tuning set explicitly.

Test `coup_discount=1` as an isolated ablation. Coup dice and their board
consequences are already evaluated explicitly, so the extra 0.9 factor is a
policy preference for placement rather than a rule-derived quantity. Keep
the experiment separate from leaf changes so its effect can be measured.

For MCTS, keep leaf evaluation parameters separate from rollout and move-
proposal parameters before broad tuning. The root still searches a narrow
card and target shortlist and delegates most continuations to the strategic
policy; changing leaf weights and rollout behavior together would make a
result hard to interpret. Keep access, progress, region margin, and reserve
terms until that separation is tested: they currently bridge the one-action
search horizon and are not obviously redundant.

Recommended order: fold the turn-3 diagnostic into full-game workers; finish
the corpus review; profile and cache repeated risk/evaluation work with full
state keys; then test the isolated coup-discount ablation and a separated
MCTS leaf. Do not start a broad MCTS weight search before those measurements.
