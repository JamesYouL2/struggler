# Handoff, 2026-09-13 morning — where everything is, and how to finish it

Written at 06:45 with a lot in flight. Sections 1 and 2 are what to check
first; section 6 is how to finish each piece if the session that started it
is gone. Earlier state: `2026-09-13-handoff-for-codex.md`.

`main` is `b4ab3e1`, pushed. The working tree has **three uncommitted files
that belong to two different pieces of work** — see section 2.

## 1. Live right now

| what | where | state at 06:42 |
| --- | --- | --- |
| Gate, reply model 4 | CI 34758550918, `experiment/reply-model-4` vs `0cb9e16` | running |
| Gate, reply model 5 | CI 34758554168, `experiment/reply-model-5` vs `0cb9e16` | running |
| Experiment, `reply_model` 4.0, 256 seeds | CI 34758467181 | running |
| Experiment, `reply_model` 5.0, 256 seeds | CI 34758468757 | running |
| Collector for those four | `scripts/collect_ci.sh reply-budget-models` | waiting; commits one note |
| Control-odds measurement + fits | `scripts/queue_control_odds.sh`, `logs/control-odds/20260913-055843` | 62/192 games; commits a generated note |
| Legacy drift, anchor `372609e` | `scripts/queue_legacy_drift.sh`, `logs/legacy-drift/20260913-021444` | running; commits per anchor |
| Suite, stall follow-up | main tree, `logs/stall-followup/suite.txt` | ~62% |
| Suite, merged first_mover tree | `wt-merge-fm`, `logs/merge-first-mover/suite.txt` | ~71% |
| Agent: ruff families | `wt-ruff`, branch `chore/ruff-families` | working |
| Agent: audit F6 | `wt-f6`, branch `fix/f6-our-man-in-tehran` | code done, uncommitted, targeted tests running |
| Agent: audit F8 | `wt-f8`, branch `fix/f8-harvest-validation` | code done, uncommitted, full suite ~71% |
| Agent: reply/coup look-ahead | `wt-reply-coups`, branches A/B/C | building |

Worktrees are under
`/tmp/claude-1000/-home-jjy-struggler-struggler/28a9a4ff-f490-45c3-9385-c3cc193f3daf/scratchpad/`.
None has its own venv: run
`PYTHONPATH=$WT/src /home/jjy/struggler/struggler/.venv/bin/python -m pytest ...`
or the shared editable install silently tests the main tree instead.

## 2. The uncommitted files in the main tree

- `src/struggler/bots/benchmark.py` + `tests/test_benchmark_stall.py` — **the
  stall follow-up.** My F4 fix stamped a run's `stalled` on *every* report it
  wrote, so on CI run 34753464219 the held-out samples read "stalled after 128
  of 128 games; unfinished []" and failed completeness because the *other*
  arm hung on seed 4006. Writer: a report is stalled only if its own games
  are unfinished. Reader: a stamped report with nothing unfinished is
  complete, which also rescues reports already written. Two new tests fail
  on the old code. Commit when the suite in section 1 passes.
- `pyproject.toml` — **the ruff families** (C4, PERF, RET, PIE, FURB; ARG in
  the evaluator only; UP and TRY deliberately not selected, counted first).
  The ruff agent has a copy in `wt-ruff` and commits it there. Do not commit
  it from the main tree; discard it here once `chore/ruff-families` merges.

## 3. What landed today (since the Codex handoff)

| commit | what |
| --- | --- |
| `9068a19` | audit F3: acceptance and early stopping count complete seat pairs only |
| `734a7cb` | audit F7: observation context frozen, `\|=` refused, CHANCE options private |
| `c0d9983` | note: the China phantom's five points live in `_reply_budgets` (9/9 top changes, 80/80 orderings) |
| `438e76c`, `7083521` | control-odds measurement, fitter and queue |
| `6051060`, `9ee6aa9`, `b4ab3e1`, `a5865aa` | generated notes: drift and ladder, first_mover gate, coup variants, legacy anchor |

Earlier this session, before the Codex handoff was superseded: Blockade
recursion fix, F1 and F4, wipe/wipe_backed/progress_curve/ops deleted
(`d120c63`), legacy anchor harness (`a213b67`).

## 4. Results, and what the maintainer decided

Every score is the candidate's against its base; 0.500 is a dead heat.
"Pooled" combines a gate with the 256-seed weight experiment by inverse
variance.

| question | reading | decision |
| --- | --- | --- |
| delete `coup_discount` | pooled 0.473 [0.442, 0.505] | **keep it; do not merge `delete/coup-discount`** |
| `coup_discount` on battleground coups only | 0.514 ±0.025 (128 seeds) | open |
| `coup_discount` on coups, not realignments | 0.498 ±0.023 | open |
| delete `first_mover` | gate 0.484 ±0.028, pooled 0.504 [0.473, 0.535] | **merge** (approved; waiting on the suites) |
| China phantom restored | 0.557 rotated, 0.555 iran/austria | superseded by reply models 4/5 |
| HEAD vs `c0ccd95`, iran/austria | 0.467 ±0.029 | the regression survives fixed books |
| HEAD vs pre-split legacy anchors | 0.756, 0.727, 0.650, 0.660, 0.596 (`b375ae5`) | no regression to chase before the split |
| Voice of America | withdrawn, misread log | — |

The `first_mover` branch's re-captured corpus grew from 401 to 473 records,
turn 9 from 32 to 85: games last longer without it. Legitimate, but the
suite is slower, since turn-9 records are the expensive ones.

## 5. The maintainer's current ideas, and what is built for each

**Reply budget** (`experiment/reply-budget-models`, `0cb9e16`): always add
the China Card when the opponent holds it face up (**model 5**), and try the
budget as max(known cards, best of an `opponent_hand_size` draw from the
unseen pool) (**model 4**, exact via `max_budget_weights`). Never our own
China Card. Gated and experimented in section 1.

**The look-ahead should consider coups**, which the maintainer thinks is
what `coup_discount` stands in for. The code agrees: `coup()` and `realign()`
never call `_after_reply`; they multiply by 0.9. Three stacked branches,
each to be gated against its parent:

- A `experiment/reply-fixes` (from `7e3d911`): audit Q1 (reach), Q2 (retake
  cost via one shared `rules_math.ops_to_control`), F5 (no reply once the
  opponent has no move before the payout).
- B `experiment/reply-coups`: the opponent may answer a placement with a
  legal coup (DEFCON region, NATO/pact/Reformer, not suicidal at DEFCON 2).
- C `experiment/coup-lookahead`: our coups and realignments get the reply
  per roll outcome; `coup_discount` 1.0. If the hypothesis holds, C is not
  worse than B.

**Battleground value formula**: value of scoring × flip ability^turns ×
P(scoring) × (a/Ops for you + b/Ops for them). Division probably does not
survive; overprotection must count. Built: `measure_control_odds.py` records
exact Ops-to-control for both sides, both overprotections, reach and who
controls at the next two scorings; `fit_control_odds.py` fits a table,
reciprocal, contest share, exponential and linear, each with and without
overprotection, on even seeds and scores on odd. Nothing is wired into the
bot; the fits choose a shape, a gate would decide strength.

## 6. How to finish each piece

- **Stall follow-up**: suite passes → `git commit -- src/struggler/bots/benchmark.py tests/test_benchmark_stall.py`.
- **first_mover merge**: both suites pass → commit the stall follow-up, then
  `git merge --no-edit delete/first-mover`, check `git rev-parse HEAD^{tree}`
  equals the tree recorded on the first line of
  `logs/merge-first-mover/suite.txt` modulo the stall-fix commit, push.
- **F6 / F8**: if their agents are gone, the code is uncommitted in `wt-f6` /
  `wt-f8`. Read `git diff`, run the full suite there with the PYTHONPATH
  above, commit on the branch, then merge. F6 changes engine observation
  and the bot; check `tests/test_history_privacy.py` and the parity corpus.
- **Ruff**: `chore/ruff-families`; it includes removing the evaluator's dead
  `defcon`/`bans` parameters, whose proof is the parity corpus passing
  unchanged. It will need a small rebase after the first_mover merge (both
  touch `country_value`).
- **Reply/coup A, B, C**: push the three branches, dispatch
  `gate.yml` for each with `bases` = its parent SHA, `decide=0`, `vary=0`,
  then one `collect_ci.sh`. They change decisions, so the parity corpus is
  re-captured only on whichever merges.
- **Collectors and queues** commit their own notes by explicit path and
  never push. Push after reading them.

## 7. Still open, not started

- Audit F2: the capped access formula `[1-(1-p)**k]/p`, gated.
- `benchmark.stable_verdict`: `threshold` is unused; fix the docstring.
- A 256-seed run of `coup_discount` on battleground coups only, if B/C do not
  settle it.
- GitHub dispatch still fails intermittently while the status page is green
  (`2026-09-13-github-dispatch-degradation.md`); every dispatch here retries.

## 8. What this does not say

Nothing in section 5 has a result yet. ACCEPTED means not measurably worse,
never better, and a 128-seed gate cannot separate 0.514 from 0.473.
