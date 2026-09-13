# Handoff, 2026-09-13 midday — supersedes the morning handoff

## 0. Stopping point (written as the session hit its usage limit)

Nothing is lost if every process below died; each piece is committed or on
disk, and each has a resume step.

- **CI:** the three reply/coup layer gates (section 1) were still
  `in_progress`. Their collectors (`scripts/collect_ci.sh
  reply-lookahead-layers-ab` and `reply-lookahead-layer-c`) commit a note
  to the LOCAL main when the runs finish and **never push**. If they died,
  re-run them with the run ids in section 1; `collect_ci.sh` downloads
  artifacts, which CI keeps for 30 days.
- **Codex M1** is committed: `8879a79` "delta prices the access other
  countries lose or gain", on both `fix/board-potential-m2a` and
  `fix/board-potential-m2b` (local branches, not pushed). Verify it before
  trusting it: `tests/test_board_potential.py` plus test_strategic plain
  and under `STRUGGLER_CHECK_SNAPSHOT=1`, and Codex's M1 numbers.
- **M2a / M2b** were in progress in `wt-m2a` / `wt-m2b` (evaluator, policy,
  stakes.py, docs, tests/test_board_potential.py, test_strategic.py). The
  agent was told to commit whatever it had as `wip:` with what is done and
  verified in the body. Check with `git log fix/board-potential-m2a
  fix/board-potential-m2b` and `git -C $WT status`; if uncommitted, the
  diff in the worktree is the work.
- **M2 final state (agent's report after wrapping up):** both committed
  `wip:`, not pushed, worktrees clean. `fix/board-potential-m2a` =
  `8879a79` + `8bd2d6c`; `fix/board-potential-m2b` = `8879a79` + `e8bbca5`.
  M1's dependency claim held against `access` (another country reads the
  changed one only through control and each side's presence); Codex's M1
  case now gives 8.4435555556 both ways, and the new exactness/order tests
  fail on `e47f31f`. `tests/test_board_potential.py`: 20 passed, plain and
  under the snapshot checker, both branches. Parity: all 473 records
  change on both; top actions change in 24 (m2a) and 20 (m2b).
  **m2b** targeted suites green (92 passed, 1 xfailed; snapshot 71 passed).
  **m2a** has two failures left for the maintainer, not weakened:
  `test_the_ops_curve_is_convex_where_a_threshold_is_crossed` now PASSES
  (Ops 3-4 worth 34.30 vs 29.80 for 1-2), tripping its strict xfail; and
  `test_the_forward_search_is_what_holds_the_rate_down` no longer separates
  (with the search off, no seat exceeds 3 pokes). Not yet run on either:
  full suite, alternated timing (`scratchpad/timing_rank.py`; an early
  read was ~1.3-1.5x), final commit messages. Probe scripts are in the
  scratchpad (`parity_dump2.py`, `codex_repro.py`, `convex_probe.py`,
  `poke_probe.py`).
- **Next session, in order:** (1) `git log main` — push any collector
  notes; (2) read the layer notes and merge per section 4; (3) finish or
  verify M2a/M2b, push both, gate each against `e47f31f` with
  `gh workflow run gate.yml --ref <branch> -f bases='["e47f31f..."]' -f
  decide=0 -f vary=0` (full SHA; retry on 5xx), collect; (4) section 5.

`main` is `85be653`, pushed, working tree clean (`e47f31f` is the last
code commit). Full suite on it: **815
passed, 3 skipped, 2 xfailed**; ruff clean in every selected family; and
`tests/test_strategic.py` passes with `STRUGGLER_CHECK_SNAPSHOT=1` (71
passed), which it did not this morning.

Worktrees live under
`/tmp/claude-1000/-home-jjy-struggler-struggler/28a9a4ff-f490-45c3-9385-c3cc193f3daf/scratchpad/`
and have no venv: run
`PYTHONPATH=$WT/src /home/jjy/struggler/struggler/.venv/bin/python -m pytest ...`,
or the shared editable install silently tests the main tree.

## 1. Live right now

| what | where | finishes by |
| --- | --- | --- |
| Gate, reply layer A vs `7e3d911` | CI 34770319492, `experiment/reply-fixes` `a5fa264` | collector `reply-lookahead-layers-ab` commits a note |
| Gate, reply layer B vs A | CI 34770321058, `experiment/reply-coups` `4cfa9ba` | same collector |
| Gate, reply layer C vs B | CI 34770564566, `experiment/coup-lookahead` `4610e6d` | collector `reply-lookahead-layer-c` |
| Agent: Codex M1 + M2, two variants | `wt-m2a`, `wt-m2b`, branches `fix/board-potential-m2a` / `-m2b` from `e47f31f` | commits, no push |

`7e3d911` is main plus the first_mover deletion; its bot code equals
`e47f31f`'s except the ruff dead-parameter removal and the snapshot fix,
neither of which moves a decision (parity unchanged), so the layer gates
still describe main.

## 2. Landed on main today

| commit | what | proof |
| --- | --- | --- |
| `9068a19` | audit F3: complete seat pairs only | suite 787 |
| `734a7cb` | audit F7: observation cannot move the engine; CHANCE options private | suite 787 |
| `e4360c1` + `a83ab52` | stall marks only the sample that lost games; **first_mover deleted** | suites 800 and 797 on the merged tree |
| `5c68258` | audit F8: harvester cannot certify USABLE on missing or hidden-wrong evidence | suite 810 |
| `2b78538` | audit F6: Our Man in Tehran shows the US its examined cards (`Observation.examined_cards`, US only); bot keeps/discards by `tehran_discard_gain` | suite 814 |
| `9817aa7` | ruff: C4, PERF, RET, PIE, FURB, ARG (evaluator) selected and fixed; dead `defcon`/`bans` removed from `country_value`/`board_value` | suite 797, parity unchanged |
| `e47f31f` | `_placement_ops_value` calls `_invalidate_base()`; the stale-base guard runs on the placement path again | suite 815 |
| `ea1e468` | Codex's repeat audit, `docs/notes/codex/2026-09-13-strategic-math-followup.md` | docs |
| notes | control-odds fits, reply models 4/5, coup variants, first_mover gate, pre-split drift, the phantom contradiction | generated / written |

## 3. Results and decisions

| question | reading | status |
| --- | --- | --- |
| delete `coup_discount` | pooled 0.473 [0.442, 0.505] | **kept** (maintainer) |
| `coup_discount` on battleground coups only / coups only | 0.514 ±0.025 / 0.498 ±0.023 | open; layer C tests the explanation |
| delete `first_mover` | pooled 0.504 [0.473, 0.535] | **merged** (maintainer) |
| reply model 4 (max of known and drawn) | pooled 0.479 [0.449, 0.509] | not shipped |
| reply model 5 (their face-up China Card) | pooled 0.475 [0.455, 0.494] | not shipped |
| China phantom (China Card in every budget) | 0.557 gate | contradiction: see `2026-09-13-the-phantom-beats-the-correct-china-card.md` |
| HEAD vs `c0ccd95`, iran/austria | 0.467 ±0.029 | regression survives fixed books |
| HEAD vs pre-split anchors | 0.756 … 0.596, 0.502 at `372609e` | nothing earlier to recover |
| control-odds shapes | reciprocal (division) worst at both horizons; linear + categories + overprotection best (−0.015 log-loss vs table) | division does not survive; overprotection matters |

## 4. Open experiments, and how to finish each

**Reply/coup look-ahead** (maintainer: the look-ahead should consider coups,
probably what `coup_discount` stands in for). Stacked, each gated against
its parent:

- A `a5fa264`: audit Q1 (reach, Chernobyl), Q2 (`rules_math.ops_to_control`,
  shared with the control-odds script), F5 (`rules_math.next_move` from the
  engine's own turn-order functions). 349/473 parity records change, 117
  top actions; ~1.05x cost.
- B `4cfa9ba`: the opponent may answer a placement with a legal coup
  (`engine.core.defcon_allows_coup`, `coup_forbidden`, no suicidal
  battleground coup at DEFCON 2). 405/473, 170 top; ~1.48x.
- C `4610e6d`: `_after_change` applied per roll in `coup()` and per margin
  in `realign()`; `coup_discount` 1.0. 453/473, 253 top incl. 24 coup
  targets; 1.18-1.43x.

When the notes land: merge the highest layer that is not measurably worse
than its parent, rebased on `e47f31f` (they predate the snapshot fix and the
ruff removal of `defcon`/`bans`; expect small conflicts in `delta` and
`country_value` calls), re-capture the parity corpus on the merge, full
suite, push. If A is worse, stop: Codex ranks it a correctness fix, so read
why before overriding the gate.

**Codex M1/M2** (reproduced exactly on main). M1: `delta` ignores the access
other countries lose or gain. M2: `delta` weights regional VP by one
country's urgency (Thailand's includes Southeast Asia Scoring), while
`board_value` and the sandbox use none. Two branches, both with M1:
M2a = no urgency on regional VP anywhere; M2b = each region weighted by its
own scoring urgency on every path. The choice is strategic, so both get
gated against `e47f31f`. If the agent is gone: its work is in `wt-m2a` /
`wt-m2b`; the spec is exactness (`delta` == whole-board difference with
reply off) plus Codex's order-invariance reproductions.

## 5. Order of what remains

1. Read the three layer gates; merge per section 4.
2. Gate M2a and M2b; merge one (maintainer's call on the strategy).
3. Audit F2: the access aggregate `[1-(1-p)^k]/p` (Codex: after M1/M2).
4. The phantom contradiction's decisive pair — China Card whenever the
   opponent owns it, face up or down, vs the phantom — on top of the merged
   reply layers.
5. Battleground formula: turn the control-odds fit into a value term only
   after 1-3, and mind Codex's point that the fits are conditional on the
   scoring happening and that conversion and retention are different
   probabilities.
6. `benchmark.stable_verdict`: `threshold` unused; fix the docstring.

## 6. Traps met today

- **An agent waiting on its own background watcher does not wake.** Four
  agents stopped at session limits and two more stopped "waiting for a
  monitor". Give agents foreground waits, or poll their logs and message
  them.
- **`git stash` in a worktree with a suite running in it** swaps files
  under the suite. It happened once today; that suite was discarded and
  the merged tree re-tested.
- **`git commit -- <path>` on an untracked file fails** and stops an `&&`
  chain before anything commits; `git add` first.
- **A copied test that imports a branch-only symbol** breaks main's suite;
  one was deleted from the main tree before committing.
