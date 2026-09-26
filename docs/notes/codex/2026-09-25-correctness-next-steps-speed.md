# Correctness, next steps, and speed audit — 2026-09-25

Reviewed main: `90247b2e7222e64493a21a17e3cd234f8f777e89`.
Previous audit baseline: `cec39ca958cd774ead806690e84b4c83e5cc1064`
(September 22). Historical baseline: `v0.1.0` =
`50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9`.
Main was rechecked remotely during the audit and remained at the reviewed SHA.

## Assessment

No new live engine/default-policy correctness defect was confirmed in this
bounded review. The main risks found are in experiment accounting and
measurement, which can misdirect the next policy work despite green tests.
The rules engine has no source diff since the previous audited revision.
This was a recent-change audit with targeted boundary checks, not an exhaustive
card-by-card rules certification or a new strength tournament.

The country-value rebuild is shipped. The optional stochastic potential was
measured and left off; its development plan is closed in the current handoff.
The assignment solver and policy wiring exist, but `hand_assignment=0.0`.
The alphabetic sequencing defect remains in main's opt-in path, with a repair
already on `fix/hand-planner-lead`. Do not rebuild the allocator or enable it
before resolving that existing candidate. Current defaults include region 2.6
and military 2.0. Repository experiment records describe measured gains;
this audit did not independently replay those experiments.

## Verified findings

### F1 — P2, main: an incomplete reserve run writes a complete-looking report

Location: `src/struggler/bots/benchmark.py:main`, report construction around
lines 1409–1431; `counted_pairs` around line 514.

With `--reserve-seeds`, `mine` is overwritten with the pairs that actually
finished. `planned_games` then counts that reduced set, `unfinished` is empty
by construction, and `report_stop` becomes `None` even if the reserve failed
to deliver the requested number of pairs. The process correctly returns 6;
the saved report contradicts it. Pooling consumes the saved games and loses
the failure evidence further downstream (F2).

Reproduced through the real `benchmark.main` using the existing fake-pool
fixture: core seeds `4000-4001`, reserve `5000-5001`, only both seats of seed
4000 finish, then the pool times out. Result:

```
exit status: 6
stop_reason: None
planned_games: 2
finished_games: 2
unfinished: []
counted_pairs: 1
```

The requested sample was TWO pairs/four seat-games. Preserve the requested
pair target independently of completed membership; keep incomplete status
when counted pairs fall short. Add an integration regression for exhausted
reserves, not just successful backfill and the no-reserve path.

A related design limitation: independently backfilling each arm does not
restore paired sample size. If A counts {4000, 5000} and B counts {4000, 4001},
the paired estimator correctly retains only 4000. Moreover, replacing games
because they run slowly does not establish unbiased sampling: runtime can
depend on policy and outcome. Backfill can be an operational convenience,
but it must not erase censoring, original seed identities, or paired attrition.

### F2 — P2, main: pooling still loses missing/partial-run evidence

Locations: `scripts/pool_reports.py:load`, `pooled`; consumers
`scripts/wave_verdict.py:decide` and `.github/workflows/experiments.yml`.
This is September 22 F2, rechecked and still open.

`load` retains `games` but drops report completion metadata. It discovers
shards by existing directories rather than an expected manifest, so a wholly
absent artifact is not listed as missing. The workflow still passes this
output straight to the interim rule.

Reproduction: one directory, metadata `of=2`, 40 complete seeds, report
`stop_reason='stalled'`, `planned_games=82`, two unfinished seat-games, and
no second directory. The pool reports `shards=1`, `missing=[]`, score 0.75,
SE 0.04. The interim returns `proceed=False`, z=6.25, despite incomplete
required evidence. This is a fabricated report fixture, not strength evidence.

Fix with an expected wave-specific shard/seed manifest and explicit complete,
partial, missing, and deliberately skipped states. Descriptive estimates can
remain visible; stopping/promotion eligibility must retain the missingness.

### F3 — P2, main: the tie instrument counts simulations as live decisions

Location: `scripts/measure_ties.py:_rank_actions`, `_record`, `play`.

The script monkeypatches the StrategicPlayer class globally. Event helpers
are StrategicPlayers too (`policy._event_helper` / `_resolve_sandbox`), so
ranking one live card also records the event decisions simulated while
pricing its alternatives. The script cannot interpret the resulting counts
as choices actually made in a game.

Minimal reproduction: a US headline observation holding Marshall Plan and
Fidel; call `rank_actions` once. The instrument records one HEADLINE_PLAY
ranking AND seven EVENT_INFLUENCE rankings, although no engine action has
been applied. Therefore the September 24 note's per-game blind-choice count
and per-kind rates need remeasurement. This does not establish that every
reported unpriced event is harmless or that every rate is inflated equally.

Other confirmed instrument defects:

- Global `STAT` is not reset at the start of `play`. For more games than
  workers, later worker results include earlier games again.
- `no_pref = [(k[0],) + k[1:] ...]` does not remove the preference component;
  it must skip index 1. This is inert at the shipped zero planner weight.
- A tie is not proof of an unimplemented scorer. Independent Reds and the
  shape-based free Coup/Realignment choices already have pricing branches.
  A one-option decision is not evidence of an arbitrary choice either.

Instrument only the actual player decision in the game loop, reuse the
ranking already computed, and distinguish unhandled from equal-valued and
single-option decisions. Test one live decision with nested event simulation,
multiple games per worker, and nonzero planner preference.

### F4 — P2, active branch only: event measurement crashes non-strategic benchmarks

Branch `report/event-measurement` at
`cf0bf60f9909a3a769c93115c0d792404f0094f8`,
`src/struggler/bots/benchmark.py:377`.

The new measurement calls `player.safety_key(...)` on every EVENT_CHOICE.
That method is not part of the Player protocol. Reproduced on the exact branch:

```python
from struggler.bots.benchmark import play
play(('greedy', 'greedy', 42000, 'US', 24, 0, None, None, False))
# AttributeError: 'GreedyPlayer' object has no attribute 'safety_key'
```

Main does not contain this change. Before integrating the branch, make
measurement optional/capability-aware, record unavailable telemetry explicitly,
and reuse live rank results rather than re-evaluating every option after the
choice. Test greedy/strategic and supported historical opponents end to end.

### F5 — P3, main: the final sequential boundary remains unused

September 22 F3 remains open. `wave_verdict.FINAL_BOUNDARY` computes
1.6779527108592447, but the final pooling path uses
`ACCEPTANCE['confidence']=1.645` and advertises that fixed-sample interval.
A z=1.66 result clears the latter, not the declared two-look final boundary.
Carry actual stage/design metadata into final reporting; distinguish
fixed-sample descriptive intervals from sequential decisions. Also handle
information fractions that differ from one half.

### F6 — P2, main: an unreadable comparison can lose its fail-open propagation

Location: `scripts/wave_verdict.py:decide`, comparison graph construction.

Edges are appended only for readable comparisons. With B and C both compared
to A, B's unreadable comparison first sets A/B to continue. A later decisive
C/A comparison overwrites A to stop. Because the B/A edge was never added,
propagation cannot restore A. Reproduced: absent B paired statistic, C/A
`diff_exact=.25, se=.04` returns B continue, A/C stop. This contradicts the
function's connected-comparisons contract.

Construct the graph from declarations independently of statistical
readability; combine decisions conservatively and propagate any continue
through the full connected component. Test shared-base groups with one
unreadable edge, plus ordering/permutation invariance.

## Prior findings and false alarms

- September 22 F1 (`paired` producer versus `pairs` consumer) is fixed in
  `499badc`; the producer-to-consumer regression passes.
- September 22 F2/F3 remain open as F2/F5 above.
- The September 22 assignment design note's claim that the double Space Race
  attempt has no writer is false. `Engine._update_space_race_ability` writes
  the key provided by `rules.json.space_race_ability_keys`. Advancing the US
  twice from box 0 produces `space_race_double_attempt_holder='US'` and
  `_space_attempts_allowed(Side.US)==2`. Correct that note/comment, not the
  engine. This is exactly why a literal-name search is not a call-path audit.
- The note's inventory of unpriced free Coup choices is stale: the scorer
  recognizes the option/context shape for Junta, Ortega, and Tear Down This
  Wall. Independent Reds also has a direct country-delta scorer. Current
  absence of a preference must be observed, not inferred from event names.

## Next tasks, in order

1. Repair experiment completeness and stopping contracts (F1/F2/F5/F6).
   Acceptance: actual benchmark JSON through pooling/interim/final reporting,
   including missing directories, exhausted reserves, shared-base comparisons,
   and intentional early stops. No tournament is needed to validate this.
2. Repair the live-only event instrumentation and branch compatibility
   (F3/F4). Produce per-event exposure and eligible-option counts before
   ranking which event scorers deserve work. For consequence estimates,
   distinguish immediate board delta from future flag value; a board-only
   sandbox cannot validate Chernobyl or other flags the evaluator omits.
3. Finish evaluating the existing strict-preference hand-planner repair.
   Keep default 0 meanwhile; retain the survival DP. Its previously recorded
   -0.240 loss was confounded by alphabetic ordering, and the repair's
   headline-only reading did not establish a gain. This is an optional
   strength experiment, not a live engine blocker.
4. Target a small number of consequential event decisions using corrected
   exposure plus counterfactual evidence. Compare against the same corrected
   baseline on paired seeds and both seats. Do not infer cost from tie rate
   alone, and do not keep tuning weights around an unreliable instrument.
5. Profile the shipped path and optimize a measured hot path with exact
   ranking parity and unprofiled wall-time validation. Do not optimize the
   disabled hand-assignment DP as if it were the live bottleneck, and do not
   promise a language-port multiplier from these findings.

## Measured speed priorities

Two unprofiled full strategic-versus-strategic games, identical seed 42000,
US reporting seat, shipped defaults, events enabled, no game logging:
**47.668 s and 50.153 s**, both ending at turn 10 by final VP. One profiled
repeat took **117.684 s**. These are container/seed-specific baselines,
not evidence of a regression versus another machine or a speedup estimate.
A short audit smoke overlapped the measurement session; no tournament or full
suite ran alongside it. Do not use these two readings to resolve a small
percentage optimization.

The profile identifies work to investigate, not additive percentages:

| path | cumulative time | share of profiled wall |
| --- | ---: | ---: |
| event_value | 87.28 s | 74% |
| _resolve_sandbox | 82.22 s | 70% |
| _hand_attack_value | 48.70 s | 41% |
| DefconPlanner._solve | 48.60 s | 41% |
| delta | 42.75 s | 36% |
| evaluator.country_value | 21.13 s | 18% |

These paths overlap heavily: hand-attack survival evaluation happens inside
event pricing, and board deltas inside simulated decisions. Exclusive module
time was about 25% evaluator, 17% survival planner, 17% policy, and 4% engine
core. Optimizing engine plumbing alone is unlikely to address the dominant
cost in this sample.

Next performance work: collect the same breakdown on a few representative
seeds, including slow tails; instrument event identity, planner nodes/cache
hits, and sandbox fallback counts. Look first for redundant equivalent
hand-attack solves and repeated board-delta work. The planner already has
memoization, and the sandbox helper already has a reduced node budget; do not
propose either as a missing feature. A narrower/equivalent state key needs
proof that it preserves hazards, space eligibility, traps, China, and timing.
A lower budget is a strength/safety tradeoff, not a behavior-preserving speedup.
Require parity plus alternating unprofiled whole-game runs for a claimed win.
The disabled assignment solver is not a shipped-policy bottleneck.

The initial temporary profiling script was named `profile.py`, shadowing
Python's standard-library module. Its two plain games completed, then profiler
construction failed; renaming it and rerunning profiling succeeded. The
reported wall times are completed runs, not the failed profiler attempt.
Artifacts: `logs/audit-2026-09-25/profile.json` and `profile.pstats`.

## Branch status

All remote heads were enumerated with `git ls-remote --heads`; fetch refspec
covers all heads. Relevant tips/merge bases with reviewed main:

| branch | tip | merge base | status |
| --- | --- | --- | --- |
| fix/hand-planner-lead | 935872b2cd5b4f18eb97267dd0a2deeabdaf6413 | b85afa7cc2e34a117eb9c93ebd7a3e081df2630a | strict preference / China exemption; unmerged |
| report/event-measurement | cf0bf60f9909a3a769c93115c0d792404f0094f8 | 90247b2e7222e64493a21a17e3cd234f8f777e89 | instrument candidate; F4 reproduced |
| simplify/space-ability | 5c01d13192c025fcdca6903efe0976e16110f5b2 | 90247b2e7222e64493a21a17e3cd234f8f777e89 | one-knob simplification; unmerged |
| exp/scoring-final-tiebreak | b7bd83bc8eb418290fdc411742399a5419c16364 | ddcefb1c6219dfb97651b19d9199fef23759424a | experiment/record changes; not a default swap |

## Validation and limits

- `uv sync --frozen --extra test` succeeded, Python 3.12.14.
- Local: `uv run pytest -q tests/test_hand_planner.py
  tests/test_hand_planner_wiring.py tests/test_wave_verdict.py
  tests/test_benchmark_stall.py tests/test_shard_plan.py
  tests/test_history_privacy.py tests/test_events.py` — **263 passed, 4.79 s**.
- Matching-SHA full-suite CI: [run 36078725818](https://github.com/JamesYouL2/struggler/actions/runs/36078725818),
  pytest job 107895670190 completed successfully, including `uv run pytest -q`.
  No redundant full local suite or new remote gate was launched.
- F1/F2/F3/F6 and the Space Race disproof were reproduced locally. F4 was
  reproduced in a detached worktree at its exact branch SHA. F5 was verified
  from producer, consumer, workflow, and computed constants.
- Reviewed recent policy, assignment, benchmark and experiment changes;
  sampled observation/privacy, event resolution, replay and MCTS public-state
  reconstruction/terminal evaluation. No new claim of exhaustive MCTS, LLM,
  physical-mode, all-card, or hidden-information correctness is made.
- Scratch reproductions and measurements: `logs/audit-2026-09-25/`.
  No implementation changes were made, no paid LLM calls or tournaments ran.
