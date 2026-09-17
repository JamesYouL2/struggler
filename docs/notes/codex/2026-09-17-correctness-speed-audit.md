# Correctness, rebuild sequencing, and speed — 2026-09-17

## Revision and scope

- Reviewed main and rebuild/value-function: `d541db2d811ce47e8be1deaba069fd278674fe9c`; both remote heads resolved to that SHA twice during review. The rebuild is merged, not an outstanding branch.
- Previous audit: `18abdba2cd8725cdd8988ba6dabcb23ad5d2e07a`, recovered from docs/audit-20260916-engine-strategic-rebuild (`30b2b88`). Historical baseline v0.1.0: `3c3125431f2979171101cbda07e95f69b65b5ddd`.
- The existing checkout was preserved; review and notes use a separate worktree. Publication base is the reviewed SHA, fetched again before creating the notes branch.
- Focused repeat audit of engine/event integration, current strategic policy, schedule, forecast/DP and diagnostic integration, previous findings, benchmark acceptance, tests and hot paths. Read AGENTS.md, CLAUDE.md, architecture, limitations, testing guidance, rebuild plan and recent handoffs. Not an exhaustive 110-card audit, physical-mode review, native-port audit, or live LLM API check.
- No implementation changes, corpus regeneration, paid calls, or strength gates. Notes publication follows AGENTS.md's standing docs commit/push instruction; no PR or merge.

## Assessment

Fix the live rules and schedule defects before treating the shipped scoring masses as a reliable comparison baseline. Forecast and independence-DP components exist, but whole expected-VP ranking remains descoped. Its surviving diagnostic has integration defects too. A native kernel is an option, not yet the only demonstrated route to viability.

## F1 — P1: Yuri and Samantha's actual event never awards coup VP

Locations: `engine/events.py::_yuri_and_samantha` (795), `engine/core.py::_handle_coup_roll` (2704–2711), `bots/strategic/policy.py::coup` (1892).

The event writes `turn_effects['yuri_samantha']`; engine coup resolution and the strategic bot still read `game_effects`. Thus normal event play awards no VP for US coups. At USSR 19 VP it misses a game-ending point.

Reproduction on reviewed SHA, using existing test helpers:

```python
import sys
sys.path.insert(0, 'tests')
from conftest import bare_engine
from test_events import _resolve_coup_roll
from struggler.engine import Side
for vp in (0, -19):
    e = bare_engine(seed=1)
    e.defcon, e.vp = 5, vp
    e._fire_event(Side.USSR, 'Yuri_and_Samantha')
    e.board.influence['Cuba'] = {'US': 0, 'USSR': 1}
    _resolve_coup_roll(e, Side.US, 'Cuba', ops=3, value=1)
    print(e.vp, e.is_terminal)
```

Actual: `(0, False)` and `(-19, False)`. Expected: -1 VP, and -20 VP with USSR victory respectively. The failed coup still owes the point.

Why tests miss it: `test_yuri_and_samantha_lapses_at_the_end_of_the_turn` verifies the new field in isolation; `test_yuri_and_samantha_scores_ussr_on_us_coups` manually sets the obsolete game field. Both pass while the real producer and consumer disagree.

Small fix: use the turn-scoped effect consistently in engine and bot, including the reply model's effective-turn context. Test event → US coup → VP, USSR coup exclusion, expiry, and the terminal point through the real event entry point. Do not preserve an obsolete-field test as the only payout coverage.

Correction to yesterday's audit: its Yuri reply reproduction manually installed the old game flag. That demonstrates the reply omission in that constructed state, but missed this upstream break in ordinary play. Repair the real event pipeline first; then ensure same-turn US replies account for the VP and reject immediately losing replies. Next-turn replies must expire Yuri.

## F2 — P2: Southeast Asia's one-shot scoring is counted again

Locations: `strategic/schedule.py::opportunities` (state hand/unseen/discard → bucket 3); `policy.py::_scoring_weight_uncached`.

`once` guards discarded cards and final scoring but does not guard the generic recycling block. A held SEA card gets mass 1 this turn plus another post-reshuffle opportunity. An unseen card similarly gets combined lifetime mass greater than one. This is live: the urgency consumer sums these masses for SEA countries.

Reproduced: turn 4, held SEA, pile 10, no removed/discarded cards gives masses `1.0 + 0.9576155318567131`. More significantly, **99/385 existing corpus records** assign SEA lifetime mass above one. Record 56 (turn 5, unseen SEA) assigns buckets 1/2/3 masses `0.2195121951 / 0.7804878049 / 0.3561643836`.

Fix: model SEA's remaining first draw/play, never recycling after it fires. Held SEA has no later opportunity. For unseen SEA, include remaining pile draws without resurrecting an already played card. Acceptance: sum of unshaped occurrence masses across SEA opportunities <= 1; held, unseen, exhausted-pile, future-era, and removed cases; preserve its distinct payout from Asia and absence at final scoring.

## F3 — P2: exhausting deals lose the first draw of cards already in the pile

Locations: `public_cards.py::cycle_deal_masses`, `post_reshuffle_deal_masses`; `schedule.py::opportunities`.

The current-cycle walk excludes the entire deal that exhausts the pile. The next-cycle walk prices only draws from recycled discards. But the old pile's remaining cards are drawn first, before reshuffling; they do not vanish or become eligible for that same reshuffle while held.

Minimal input, built with `dataclasses.replace` on a real observation: turn 9, draw pile 5, opponent hand count 0, own hand empty, no discarded/removed cards. Asia Scoring is therefore in the old pile under the model. The modeled turn-10 deal requests 16 cards, necessarily drawing it. Output instead has no bucket 2 and only `0.1208791208791209` bucket-3 card-play mass, plus the separate 0.75 final-scoring prior. Conditional on reaching that deal, the first card-play mass should be 1, not 0.121.

This is not the documented uncertainty about early game endings or precise reshuffled pile size: it is omission of a guaranteed draw within the model's own 16-card deal.

Fix: split an exhausting deal into the old-pile portion and recycled portion, and condition a card's eligibility for the latter on its location. Cover cards already discarded versus cards still in the pile, a last-turn exhaustion, exact exhaustion, future-era additions, and SEA's single lifetime play. Do not merely add 1 to bucket 2 while continuing to count that same held card in recycled draws.

## F4 — P2, still open: next-turn coup replies retain expired roll modifiers

Locations: `policy.py::_after_reply`, `_may_coup`, `_coup_reply`; `rules_math.py::coup_roll_modifier_estimate`.

Yesterday's defect remains: legality advances DEFCON/expires turn effects for `when == 1`; roll arithmetic gets the original observation without the reply horizon. Using the previous audit's `_overprotected_lebanon` fixture at US turn-5 AR7, `_ars_played=14`, DEFCON 2, and a three-point Lebanon placement:

| SALT this turn, expiring before reply | Raw delta | Reply-adjusted value |
| --- | ---: | ---: |
| Absent | 11.4147845440 | -2.4799629292 |
| Present | 11.4147845440 | 1.0049628109 |

The stale modifier still flips the candidate's sign. Carry one effective reply context through legality, modifiers and VP consequences; leave raw valuation context fixed. Cover same/next-turn SALT, Death Squads, and Yuri alongside existing DEFCON/CMC/Nuclear Subs cases. These values establish an implementation defect, not tournament strength impact.

## F5 — P2 integration blocker, diagnostic only: scoring_potential's public contract is broken

Locations: `policy.py::scoring_potential` (1154), `_potential_total` (847), `prepare` (698), `_overrides_for`.

Three independently visible seams:

1. `scoring_potential` passes `_overrides_map(pos)` to a parameter expecting the two scoring flags. With Formosan active, it unpacks a six-region dict into two values and raises `ValueError: too many values to unpack (expected 2)`. Shuttle takes the same path.
2. Its `side` argument is ignored. A bot prepared for US returns `4.468027280228045` for both requested US and USSR on the fresh seed-4000 board. It actually uses the prepared observation's seat. Either honor the public argument with explicit fixed-context sign semantics or narrow the API.
3. `_potential_total` iterates `_region_cards`, which contains only the six regional cards. Its `card == SEA_SCORING` arm is unreachable, so it omits `_sea_term` entirely. A turn-5 held-SEA/US-Thailand probe produces a nonzero `_sea_term` of 4.539622878989191 that is absent from the sum.

These do not affect current default rankings because the potential is descoped. They do block trusting it as the rebuild oracle. Add direct wrapper-level tests for modifiers, both requested seats, and total = six regional terms + SEA; component DP tests cannot catch this wiring.

## Rebuild status and next tasks

| Component | Current status |
| --- | --- |
| Schedule masses | Live on main; F2/F3 need correction |
| Control forecast | Implemented; normalized US/USSR/open triples; old-policy calibration assumptions remain |
| Stochastic regional tiers | Independence DP implemented; explicitly a joint-distribution approximation |
| Incremental DP | Per-member-removed state and reconvolution implemented, not integrated into ranking |
| Expected-VP diagnostic | Present, but F5 breaks its advertised contract |
| Default ranking | Old country/region/margin structure with new schedule urgency |
| Common VP units | Still outstanding; direct VP continues through heuristic Ops conversion |

Order:

1. Repair F1–F4 and their missing integration regressions. Carry the same fixes into the frozen comparison baseline and candidate; record exact SHAs.
2. Repair F5 so the diagnostic is a usable oracle. Update the rebuild README's stale “implementation has not started” status.
3. Implement/measure exact conditional-payout reuse below, with invalidation tests and representative ranking call counts. Set a measured per-game/gate runtime budget.
4. If still too expensive, port only the measured DP kernel behind the existing pure snapshot boundary, preserving exactness. No full-engine rewrite is implied.
5. Integrate whole-potential deltas and coherent direct-VP/Ops/event/risk units. Preserve modifier and scoring-time terminal semantics: merely controlling Europe between scorings is not immediate victory.
6. Then run paired-seat strength validation and calibration. Keep deeper search deferred; component tests do not require repeated tournaments between identical policies.

Evidence correction: the factor-2 note calls a 0.543 score “STRONGER.” Its printed standard error is 0.036, and the actual gate accepts when the **upper** one-sided bound reaches 0.5. The corresponding fixed-sample lower bound is about 0.484; early stopping adds another reason not to promote this to superiority evidence. It passed the project's regression screen with a favorable point estimate. That neither proves improvement nor validates the schedule's probability accounting.

## Speed suggestions, ranked

### A. Exact conditional-payout coefficients before a native rewrite

For fixed other-member probabilities and scoring rules, expected tier payout is linear in the changed member's triple:

`E = p_US * V_US + p_USSR * V_USSR + p_open * V_open`.

Compute the three conditional payouts from the per-member-removed DP once. Cache those three numbers, rather than rescanning thousands of count states in `tier_e_from_minus` for every new own-member probability. A Europe probe compressed **2,856 states to three coefficients**; 50 seeded random probability triples agreed with existing reconvolution to maximum absolute error **2.665e-15**.

This is an exact algebraic simplification, not a measured end-to-end speedup. Setup remains expensive; reach changes at neighbours, promoted/ignored scoring members, horizon and other-member feature changes invalidate reuse. Use a signature of all other rows and scoring rules, or compute bounded variants for actual changed-neighbour sets. Never assume other rows stay fixed just because only one country's influence was edited. Measure reuse across `_investment` point counts and reply outcomes before concluding it solves the runtime problem.

### B. Reduce repeated preparation work in the shipped bot

`_urgency_for` still keys by stability although the new `_scoring_weight_uncached` no longer reads stability. Cache the seven card weights per prepared observation, then combine by region/SEA membership. Also prepare diagnostic-only masses lazily if profiling justifies it; `prepare` currently constructs them on ordinary rankings although live values do not consume them. Both are bounded behavior-preserving candidates; protect exact rankings and do not recapture a failing corpus to conceal drift.

### C. Optimize the measured search hot path, not generic typing cleanup

Five corpus rankings (indices 0, 56, 120, 200, 300; current default weights) under cProfile: 14,914 `delta` calls, 4,109 `_after_reply`, 4,204 `_coup_reply`; ~62% cumulative time under `delta`, ~45% under `_after_reply` (nested percentages, not additive). This is a small hotspot sample, not a game benchmark; it ran while the suite was active, so its wall time is not an idle-machine speed claim.

The existing route-weight/access optimization is already merged (`a904c7e` is an ancestor). Do not queue it again. Preserve the corpus as an exactness gate for further behavior-neutral work. Type annotations are useful at the producer/consumer boundaries above, not an established runtime optimization.

The design note's 15–100-hour gate estimate is not a benchmark: its stated 40–120 extra seconds/game over a ~21-second baseline implies a different multiplier than its 50-minute-to-15–100-hour projection. Runtime may indeed be unacceptable given call fan-out, but measure it after the cheaper exact representation instead of treating that arithmetic as proof Python cannot work.

## Earlier findings and coverage limits

- Expired coup modifiers: reproduced, open (F4).
- Yuri reply omission: superseded by the upstream real-event break; repair both in sequence (F1).
- MCTS banked-VP context: still reproduced as optional-path debt; identical nonzero-VP leaf returns -0.1484547588 fresh versus -0.1123635012 after ranking its own position. Keep outside the current development queue unless MCTS is resumed.
- Previously repaired neighboring-access, raw-potential, legal placement reach, final-turn reply, and private Tehran observation paths remain in the source/regression coverage. No new privacy leak was verified.
- Forecast correlation, non-battleground extrapolation, survival/early-ending odds, and exact opportunity-to-scoring-horizon mapping remain modeling limitations, not newly proved implementation bugs.

## Validation

**Full suite: 897 passed, 4 skipped, 1 xfailed**, reported runtime 211.47 seconds (`uv run pytest -q`). This is a complete passing run, not evidence that the independently reproduced gaps are covered. Full suite, profile, and advisory checker logs are under `logs/audit-20260917/` (local, ignored).

- Initial `uv run pytest -q` could not start because this fresh worktree lacked test extras. Ran `uv sync --frozen --extra test`, then the full suite.
- `uv run ruff check src/struggler --output-format concise`: 26 advisory findings; no fixes applied.
- `uv run ty check --output-format concise`: 114 advisory diagnostics; not 114 confirmed defects. The incorrect `tier_e_minus` return annotation (declares dict, returns tuple) is a small boundary cleanup worth doing with its caller work.
- Independent reproductions above ran at the reviewed SHA, without changing implementation or existing tests. No speed multiplier or new strength result is claimed.
