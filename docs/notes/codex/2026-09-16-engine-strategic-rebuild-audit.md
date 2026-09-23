# Engine, strategic bot, rebuild progress, and small improvements — 2026-09-16

Follow-up: [branch-aware overall sequencing](2026-09-16-overall-rebuild-sequencing.md) reviews `rebuild/value-function` at `02c6e16`. The prototype and schedule scaffold already exist there, unwired. The main-only status below is historical; do not restart that prototype.

## Revision and scope

- Reviewed `main` at `18abdba2cd8725cdd8988ba6dabcb23ad5d2e07a`, fetched and confirmed against the remote default branch.
- Repeat-audit comparison: `bfaa229e91e36fe69b5b3fd32f266cca52789352` (September 15 audit).
- Historical baseline: `v0.1.0`, resolved to `3c3125431f2979171101cbda07e95f69b65b5ddd`.
- Isolated worktree. Read AGENTS.md, CLAUDE.md, architecture, limitations, strategic documentation, testing guidance, rebuild plan, and recent experiment/landing notes.
- Scope: recent engine and strategic changes, reply timing/outcomes, scoring schedule and common-value integration, existing regression coverage, static checks, and a small ranking profile. This is not an exhaustive card audit. MCTS remains outside the requested development queue; no tournaments or paid model calls were run.
- No implementation or test expectations changed. Documentation publication follows AGENTS.md's standing instruction to commit and push notes; no implementation branch or PR is created.

## Assessment

Two new P2 strategic-policy defects are reproduced, both in the expanded coup-reply path. No new engine implementation defect was verified in the reviewed changes. The engine provides the correct turn-effect expiry and Yuri-and-Samantha terminal outcome; the bot's approximation fails to carry them through.

The expected-VP rebuild has useful scaffolding on main but its core is still unimplemented. Stop treating additional old-model weight experiments as progress on the central deliverable. Build the one-region expected-payout component next.

## F1 — P2: next-turn coup replies retain expired turn modifiers

**Locations:** `policy.py::_after_reply` (around 1450), `_may_coup` (1488–1518), `_coup_reply` (1520–1541); `rules_math.py::coup_roll_modifier_estimate`; `engine/core.py::_end_of_turn`.

The placement evaluator correctly computes whether the opponent next acts this turn or next turn. `_may_coup` raises the forecast DEFCON and expires Cuban Missile Crisis/Nuclear Subs when `when == 1`. However, `_coup_reply` receives no timing argument and reads SALT and Latin American Death Squads from the original observation. Both effects expire at the engine's turn boundary.

**Reachable trigger:** US's last action of turn 5, DEFCON 2, placing three points into Lebanon. USSR's next move is on turn 6, at DEFCON 3; a coup is legal and cannot retain turn 5's SALT penalty. Using default strategic weights:

| Current turn SALT | Raw placement delta | Reply-adjusted value |
| --- | ---: | ---: |
| Absent | 11.05984858939394 | -2.0908951938202307 |
| Present, but expires before reply | 11.05984858939394 | 1.2031332656954312 |

Only an expired modifier differs, yet it changes the sign of the candidate's value. These are heuristic units, not VP. This establishes a valuation error, not a measured tournament impact or proof of a changed top action.

**Smallest correction:** carry the reply horizon into outcome arithmetic and use the same effective turn effects for legality and dice modifiers. Keep raw board-delta context fixed; changing the observation used for every valuation would introduce a separate accounting change. A small typed reply context containing horizon, forecast DEFCON, and applicable effects would make the contract explicit.

**Acceptance:** same-turn SALT/Death Squads still affect rolls; next-turn versions do not. Cover both Death Squads owners, applicable/inapplicable regions, and both seats. Existing Chernobyl, CMC, Nuclear Subs, DEFCON-recovery, final-turn, and board-restoration checks must remain green.

## F2 — P2: the reply model threatens a coup that immediately loses under Yuri and Samantha

**Locations:** `policy.py::_may_coup`, `_coup_reply`, and `coup`; engine reference `core.py::_handle_coup_roll` around 2705 and `_change_vp_by` around 2320.

The reply checker excludes DEFCON/CMC suicide but omits Yuri and Samantha. With USSR at 19 VP, any otherwise safe US coup awards the USSR its twentieth point and ends the game. The model nevertheless subtracts that coup's board damage from the USSR placement's value. `_coup_reply` also omits the ordinary one-VP transfer below the terminal threshold, whereas `coup()` already subtracts its heuristic price for our own US coups.

**Reproduction:** turn 8, USSR AR7 (`ars_played=13`), DEFCON 3, `vp=-19`, empty board except one USSR point in Angola. USSR considers placing one point in Zaire. US has no placement reach, so a coup is the modeled answer. Default weights return the same values with Yuri off or on:

- Raw placement: `28.571943642307684`.
- After reply: `-41.830297208933516`.

Executing that US coup through the engine with Yuri on ends at `vp=-20`, winner USSR. Without Yuri it remains at -19 and nonterminal. The deterministic seeded roll in the probe is 2; the Yuri VP award does not depend on the roll succeeding.

**Smallest correction:** exclude an immediately losing reply before selecting the opponent's best answer. Include Yuri's signed VP consequence in nonterminal coup-reply valuation with the same fixed VP context as other action consequences. Preserve the separation between legal actions and sensible replies: the engine correctly offers this legal but losing coup. Audit the direct `coup()` terminal handling too; it currently applies a finite VP deduction rather than an explicit terminal loss.

**Acceptance:** US coup replies at USSR 19 VP cannot be treated as threats; at 18 VP the one-point transfer is counted once. Verify Yuri absent, both perspectives, unchanged board restoration, and coexistence with existing DEFCON/CMC terminal handling.

## Minimal reproductions

Run from this revision using `uv run python`:

```python
import sys
sys.path.insert(0, 'tests')
from test_reply_lookahead import _overprotected_lebanon
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.rules_math import next_move
from struggler.engine import Engine, Side

for salt in (False, True):
    e = _overprotected_lebanon(2)
    e.turn, e.phase, e.action_round, e._ars_played = 5, 'action_rounds', 7, 14
    e.turn_effects['salt'] = salt
    e.begin_influence_operations(Side.US, 3)
    obs = e.observe(Side.US)
    bot = StrategicPlayer()
    bot.prepare(obs)
    raw = bot.delta(obs, 'Lebanon', own=3)
    print('SALT', salt, next_move(obs, Side.USSR), raw,
          bot._after_reply(obs, 'Lebanon', 3, raw))

for yuri in (False, True):
    e = Engine(seed=1)
    e.turn, e.phase, e.action_round, e._ars_played = 8, 'action_rounds', 7, 13
    e.defcon, e.vp = 3, -19
    for inf in e.board.influence.values():
        inf.update(US=0, USSR=0)
    e.board.influence['Angola']['USSR'] = 1
    e.game_effects['yuri_samantha'] = yuri
    e.begin_influence_operations(Side.USSR, 1)
    obs = e.observe(Side.USSR)
    bot = StrategicPlayer()
    bot.prepare(obs)
    raw = bot.delta(obs, 'Zaire', own=1)
    print('Yuri', yuri, next_move(obs, Side.US), raw,
          bot._after_reply(obs, 'Zaire', 1, raw))
    # Isolate the modeled reply from the fixture's remaining turn-loop work.
    e.phase = 'idle'
    e._decision_stack.clear()
    e.board.influence['Zaire']['USSR'] = 1
    e.begin_coup(Side.US, 4)
    e.step(next(a for a in e.legal_actions() if a.payload.get('country') == 'Zaire'))
    e.step(e.legal_actions()[0])
    print('Engine reply outcome', e.vp, e.winner, e.is_terminal)
```

## Value rebuild: actual progress

The controlling design is [value-function-rebuild/README.md](value-function-rebuild/README.md). Its accounting and acceptance criteria remain appropriate. Its description of the schedule is now stale in one respect: named buckets have landed.

| Component | Main at this revision | Next work |
| --- | --- | --- |
| Schedule representation | `scoring_buckets` wraps the old schedule; buckets 1/2 split its zero-turn term equally, bucket 3 maps later terms, bucket 4 is never emitted, final scoring is separate | Explicit occurrence mass and timing, including card held now and removed/one-shot scorings |
| Control forecast | Stability-keyed pooled retention and access conversion tables; no coherent US/USSR/uncontrolled forecast per horizon | Separate three-outcome forecast from rules payout; document conditioning and dependence |
| Expected regional payout | Current country weights, regional score, and margin terms remain | One regional payout per scoring, without summing duplicate tier bonuses |
| Common VP units | `importance` still uses guessed country weights; `vp_value` still prices VP as `vp_base * ops_value(1)` | Native VP potential, then coherent Ops/event/risk integration |
| Calibration/adoption | Several old-model changes gated and merged | Freeze current bot; evaluate the integrated rebuild, keeping correctness and strength evidence separate |

Recent delivered work includes retention compounding, rival-held-card urgency, five-bucket scaffolding, removal of the holding multiplier and contested-access weight, coup replies, Italy opening, and evaluator optimization. These are real changes, but they do not implement the expected-VP architecture. Gate acceptance is not evidence that a guessed factor is calibrated, nor necessarily evidence of a strength improvement.

**Recommended order:**

1. Fix F1/F2 separately from the modeling changes.
2. Freeze `18abdba` as the current comparison baseline, and build the candidate on a rebuild branch.
3. Implement the Africa payout interface first: deterministic immediate payouts exactly match the engine; supplied future control probabilities produce country bonuses plus one expected regional tier. Start with an explicit independence approximation if necessary. Compute expectation over outcomes, not a tier evaluated at average country counts.
4. Test probability normalization, seat signs, deterministic reduction, non-BG requirements, terminal precedence, and full-potential/telescoping deltas before introducing schedule fitting.
5. Add the control forecast and occurrence/timing distribution, then other regions and special modifiers. Avoid charging retention twice when the forecast already models loss of control.
6. Convert Ops, direct VP, events, and risk comparisons together. Run held-out calibration and paired-seat strength/runtime comparisons before adoption. Residual discount tuning comes last.

Do not spend the next iteration tuning another guessed old-model weight. An independently testable expected regional payout is the missing substantive milestone.

## Small speed and engineering improvements

### Best measured hotspot candidate: fixed card allegiance in the DEFCON planner

`defcon.py::opponent_event` only depends on card metadata and the planner's fixed seat. A profile of nine corpus positions (first action-round-play, Ops-type, and placement record for each of turns 1, 5, 9), ranked with current defaults, called it **717,549 times**. It accounted for about 0.99 seconds cumulative out of 5.02 profiler seconds. Precompute opposing-card IDs per seat or planner and replace repeated enum/property traversal with membership.

This is a hotspot diagnosis, not a promised 20% wall-clock saving: cProfile exaggerates frequent-call overhead, the sample is small, and suite work was concurrent. Require unchanged rankings, survival risks, truncation flags, and node counts, then measure an idle representative workload. Avoid caching `hazardous(cid)` on the card alone: it also depends on the hypothetical hand.

### Smaller optional caches

- `_reply_budgets`: the unseen Ops pool is already cached, but its sorted median or frequency table is rebuilt on each call. Cache the final immutable distribution per prepared observation, respecting context restoration. The profile had 1,368 calls and only ~0.032 seconds cumulative: worthwhile only as a tiny cleanup, not a major speed initiative.
- `coup_outcomes`: pure immutable result, 5,216 calls and ~0.043 seconds cumulative in the sample. A bounded cache keyed by all four inputs is plausible. Avoid caching board deltas across hypothetical positions. This is lower priority than allegiance lookup.

### Correctness and typing

- Introduce typed payout and control-probability records for the new evaluator and an explicit reply horizon/effects contract. These prevent the errors being introduced now; a whole-codebase annotation rewrite does not.
- Add only missing cross-boundary invariants: same-turn versus expired effects, direct-VP consequences and terminal replies, alongside the existing board-potential, snapshot, reachability, and scoring regressions.
- General `ty check` reports 103 diagnostics; source-only Ruff reports 26. These are advisory totals, not 129 proven defects. Much of the type output is `Decision | None` narrowing and mixed report payloads. Bind and check a decision once at an entry point, or give a heterogeneous report a real schema; do not scatter assertions solely to silence warnings.
- `tests/test_types.py` already gates five selected type rules and plants a negative-control enum bug. Keep that protection. Its prose and pyproject commentary conflict about which rule caught the enum bug; fix that documentation cheaply, without disabling `redundant-condition-strict` or removing mutable-state terminal guards.
- Preserve the existing parity corpus for behavior-neutral optimizations. Do not recapture it just to make an optimization pass.

## Previous findings and coverage

The reviewed diff retains the prior fixes for neighboring-access accounting, regional urgency accounting, legal retake reach/cost, final-turn reply timing, and private Tehran observations. Do not requeue these as new defects. The existing MCTS leaf-context issue is outside this task and has not been re-audited here. Existing expected failures/documented limitations are not new findings.

## Validation and publication

- Full run: `uv run --extra test pytest -q` — **861 passed, 4 skipped, 1 xfailed, 1 failed**, 285.67 seconds reported by pytest. This is not a wholly green local run.
- The failure is `tests/test_process_checks.py::test_a_monitoring_loop_is_not_a_gate`, reading nonexistent `/proc/224/cmdline`. This matches the previous audit's workspace PID-namespace limitation; an independent current probe confirms `os.getpid()` has no corresponding `/proc/<pid>/cmdline` entry while `/proc/self/status` reports the outer and inner namespace PIDs. It is not a new engine or bot test failure. No result is silently excluded.
- The full run exercises the parity corpus, engine/replay tests, board-potential and reply regressions, and selected strict type rules. The new F1/F2 edge cases are absent from the existing reply tests and were independently reproduced by the exact code block above.
- `uv run ty check --output-format concise`: 103 advisory diagnostics, nonzero exit. `uv run ruff check src/struggler --output-format concise`: 26 findings, nonzero exit. No automatic fixes applied. These use different scopes and should not be compared to old total counts as a change delta.
- Nine-position cProfile sample described above; no standalone speedup benchmark or strength experiment. Existing speedup/gate claims in landing notes were read as historical evidence, not independently rerun or certified.
- Profile and static-check/full-suite logs are under `logs/audit-20260916/` (ignored, local evidence).
- Main advanced to `02c6e1692f4861f69f134ec968c38a890e9abe3f` before publication, incorporating the rebuild prototype. Publication uses that newer base and preserves its notes; the reviewed main SHA above remains `18abdba`. Documentation-only changes relative to the publication base. No PR or merge requested.
