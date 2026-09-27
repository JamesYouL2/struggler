# Correctness and Rust-port readiness — 2026-09-27

Reviewed main: `5ab9eab4417080d167359f06a381eab8865891f0` (source/test audit baseline).
Previous audit: `90247b2e7222e64493a21a17e3cd234f8f777e89`, September 25.
Historical baseline: `v0.1.0` = `50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9` (resolved in the previous audit; not the comparison baseline for this review).

Publication update: main advanced to `9a8f6c5d476b76b137f97f30199bcdd12df26e3f`, merging PR #79 (placement memo). The intervening comparison contains the audited memo implementation and notes changes; **F5 now affects main**, and F1–F4 remain applicable. The test counts below belong to the original audit baseline, not a new full-suite run on this merge. This notes branch is based on that latest main.

## Assessment

Two live rules defects and two policy/cache defects were reproduced on main. A fifth defect was reproduced on the placement-memo branch and now affects main following its merge. Fix these before treating Python outputs as the semantic oracle for an accelerated implementation.

The repo already has indexed Terrain/Position data, a captured ranking corpus, deterministic engine replays, and tests for cache invalidation. Repeating that foundational work is unnecessary. The immediate porting work is to update the obsolete Rust contract, define a coarse batch boundary around the *current* evaluator/placement code, and add persistent-player differential traces. A full engine rewrite is a much larger undertaking and is not justified by the old speedup figures in the plan.

No implementation was changed. No tournaments, paid calls, or PRs were initiated. The user subsequently authorized publishing this audit and pre-Rust recommendations as notes on a separate branch. This is a bounded source audit, not an exhaustive certification of every card.

## Confirmed findings

### F1 — P1: three wars incorrectly subtract for control of the target

Locations: `src/struggler/engine/events.py:669–698`, `engine/core.py:2161–2184,2226–2258`.

Indo-Pakistani War, Iran-Iraq War, and Brush War all call `push_war_target_choice` without specifying `count_target_control`. Its default is True, and `_handle_war_roll` subtracts an additional point when the defender controls the target. These cards penalize defender-controlled **adjacent** countries; the target-control penalty belongs to Arab-Israeli War, not these three.

Reproductions use an otherwise empty board, US attacker, a USSR-controlled target, no USSR-controlled neighboring countries, and an explicitly chosen die face through the normal war decision handlers:

| Card | Target | Die | Expected | Actual |
|---|---|---:|---|---|
| Brush War | Angola, USSR 1 | 3 | Win: +1 US VP, seize influence | Loss: 0 VP, USSR influence remains |
| Indo-Pakistani War | India, USSR 3 | 4 | Win: +2 US VP, seize influence | Loss: 0 VP, USSR influence remains |
| Iran-Iraq War | Iraq, USSR 3 | 4 | Win: +2 US VP, seize influence | Loss: 0 VP, USSR influence remains |

For a controlled target with no other penalties, Brush War wins on 3–6, not 4–6; the other two win on 4–6, not 5–6. This changes actual outcomes and the event sandbox's estimates.

Smallest correction: pass `count_target_control=False` explicitly from these three events. Prefer making this rule choice required rather than leaving an easy-to-misuse default. Add parameterized tests at the exact threshold, alongside positive controls retaining Arab-Israeli War's target penalty and the superpower-adjacency penalty. Do not just change a test expectation generated from the current implementation.

Source: GMT-hosted [Deluxe card sheet](https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/nnts/TS_Cards_Deluxe.pdf), printed pages 4, 7 and 15 (Turkish translation of the card text). The adjacent-country wording was checked for all three; Arab-Israeli War explicitly includes Israel on printed page 3.

### F2 — P2: the China Card's end-of-turn-10 VP is absent

Locations: `src/struggler/engine/core.py:_end_of_turn`, `_advance_past_turn_boundary`, `_finish_game` (824–858).

The terminal path scores regions and immediately picks the winner without awarding the China Card holder's one VP. There is no compensating award elsewhere on the turn-end path.

Reproduction: an empty board at turn 10, VP 0, both military tracks at 5, and either side holding China. Call `_end_of_turn()`. Both versions terminate at VP 0 with `winner=None`. The China holder should receive one VP and win this otherwise tied position. Face-down ownership should not erase ownership for this award.

Smallest correction: implement the one-time end-of-turn-10 China award in the terminal sequence and test both holders, both availability states, tie-to-win and one-point-loss-to-tie cases. Pin the timing against automatic victory and Europe control explicitly when implementing; do not casually place a normal immediate-win VP award inside a loop intended to suppress intermediate final-scoring victory checks.

Source: the China Card text, visible in GMT's [2015 rulebook](https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/nnts/TS_Rules-2015.pdf), printed page 9, and the card sheet's printed page 2: the holder receives 1 VP at the end of turn 10.

### F3 — P2: disabling snapshot checking silently invalidates the delta cache

Locations: `src/struggler/bots/strategic/evaluator.py:172`, `policy.py:797,1389–1398`.

`STRUGGLER_CHECK_SNAPSHOT=0` makes `ev.DIGEST=False`, leaving every position digest at zero. `rank_actions` still creates `_delta_cache`, keyed on `(digest, country, own, opp)`. During placement/reply search, different boards therefore share a cache key. `_invalidate_base` correctly clears the separate base caches but does not clear this supposedly content-addressed cache.

Reproduced in an actual USSR four-Op placement ranking on a board with US 2 in Italy and USSR 1 in Greece. Under the zero setting, the cached Italy value is **3.3606373712737643**; bypassing only the delta memo gives **4.244664669394542**. The full ordering differs. The top action in this particular fixture is unchanged; no claim is made that every such mismatch changes the selected move.

This is conditional: the default environment maintains the digest and does not have this specific defect. The flag is nevertheless documented as a supported way to turn the instrument off and could easily be used in a port benchmark.

Smallest correction: separate optional expensive assertions from required production hashing, or disable the digest-dependent memo whenever hashing is disabled. Add a cross-environment comparison of rankings/values with the memo bypassed as the independent reference.

### F4 — P2: war target scoring omits defender superpower adjacency

Locations: `src/struggler/bots/strategic/policy.py:_score_war_target` (3246–3250), versus `engine/core.py:_handle_war_roll` (2242–2248).

The engine adds a penalty for the defender's adjacent home superpower. The target scorer only calls `board.control` on neighboring nodes; that returns None for the US/USSR nodes. It never adds the explicit home-adjacency check.

Reproduction on an otherwise empty board: USSR Brush War against US-controlled Mexico. Keeping today's target-control flag fixed to isolate this defect, the scorer implies success probability **0.5**, while enumerating all six faces through the engine gives **1/3**. After F1 is fixed, the same omission would still remain, at a different pair of probabilities.

Smallest correction: use a shared war-penalty function for the engine and scorer (or at least add the missing adjacency condition and test agreement across all targets). Preserve the card-specific target-control flag. This is a real estimate mismatch, not an argument about strategic valuation.

Rule source: GMT rulebook §2.1.5, printed page 3; home superpowers count as adjacent controlled countries for events and realignments.

### F5 — P2, now merged into main: cross-decision memo drops phasing context

Originally reviewed branch: `perf/placement-memo` at `796b2112b290c0147da66f5839957908a1ac504d`.
Merge base with reviewed main: main itself, `5ab9eab4417080d167359f06a381eab8865891f0`; the branch was two commits ahead at audit time. Now merged via PR #79 into `9a8f6c5`.
Locations: branch `policy.py:_placement_ops_value`, `_obs_context`; main/shared `bots/rules_math.py:158–184`.

The memo's observation key deliberately removes `pending_decision`, claiming nothing on the path reads it. The actual path is:

`_placement_ops_value -> _investment -> _after_reply -> next_move -> phasing_side -> pending_decision.context['phasing_player']`.

At turn 10 AR7, a USSR placement during the USSR's own card still permits a US reply; a USSR placement borrowed during the US's last card does not. Observations differing only in this context produce identical memo keys but different placement values.

Reproduction uses USSR influence in Angola and US influence in Zaire, DEFCON 2, turn 10 AR7, two Ops. Price the USSR-phasing observation, then the US-phasing observation with the same player, clearing the ordinary per-ranking caches between calls (as a fresh ranking does):

- `next_move(..., US)`: **0** versus **None**.
- First value: **19.22223412525**.
- Reused second value: **19.22223412525**.
- Fresh-player second value: **25.261178461999997**.

The reproduction demonstrates a missing dependency; it is a constructed observation pair, not a measured natural-game failure rate. The branch's six matching games and short-game regression do not cover this turn-10 boundary.

Smallest correction: include semantic phasing context, preferably an explicitly typed evaluation context instead of repr-based exclusion, then add a late-game borrowed-Operations regression and rerun trace parity. The branch's claimed 105.3s -> 84.9s (-19.4%) is its author's six-game measurement, not independently remeasured by this audit. Keep the candidate; repair and validate it before citing it as a behavior-preserving gain.

## Earlier audit status

September 25 F1/F2/F5/F6 (reserve reporting, manifest completeness, final sequential boundary, comparison propagation) have fixes on main. The focused producer/consumer tests pass. F3/F4 (live measurement and compatibility) are also addressed by the live-ranking telemetry changes. This review did not find a new failure in those covered contracts.

The optional hand-assignment planner is now deleted, not merely disabled. The survival/DEFCON planner remains. Forecast and valuation fitting code moved to `struggler/fitting`; do not bring them back into a native live-policy port by following an old rebuild plan. The AWACS era correction is on main.

Known observation limitation remains: `observe(nonacting_seat)` exposes the acting seat's card options. It is covered by an intentional xfail and described as needed by the current analysis view. Treat a separate private observation/analysis API as prerequisite work for a broader engine/search interface, not as a newly discovered exploit of the current runner or a blocker for a board-evaluator-only kernel.

## Rust prerequisites and low-hanging work, in order

1. **Fix F1–F4 and freeze that corrected Python reference.** Run rules regressions and the suite; refresh affected corpus outputs in an explicit correctness commit. Candidate and comparison baseline must use the same corrected rules before measuring strength. A parity test faithfully reproducing an incorrect rule is not evidence of correct Twilight Struggle.
2. **Repair the now-merged placement memo (F5).** Its current profile and implementation are already useful work. `chore/simplify-before-port` (`8e5d281`) is merged; don't queue its deletions again. Read the branch's fresh profiling note rather than repeating the September 8 prerequisite list.
3. **Rewrite `docs/RUST_PORT_PLAN.md` to match current semantics.** It still says delta ignores neighbors and lists a region-margin term that no longer exists. Current delta includes access dependencies out to two hops. The live evaluator also reads fitted per-side weights from a JSON-backed cached table despite its pure-input introductory claim. Supply those tables explicitly across a native boundary. Remove obsolete signatures, workload fractions and fixed schedule/size promises.
4. **Extract and pin the batch contract in Python.** Terrain and influence indexing already exist. Declare country/region order, fitted side weights, urgency, scoring flags, legal candidate order, Ops budget, reply timing/budget inputs, and outputs including chosen point counts. Keep initial legal reach frozen for a whole spend. Distinguish a raw board-delta batch from the full `_investment` path, which includes reply pricing: calling a raw-delta port an investment port would omit live behavior. Prefer one coarse call over Python-to-Rust calls per country/point.
5. **Add persistent-player differential traces to the port gate.** The existing corpus constructs a fresh bot per record, so it cannot detect cross-decision cache bugs like F5. Compare Python/native action order, chosen point counts, chance/action traces and serialized terminal states on the same frozen cases, including late game, borrowed Ops, scoring overrides and near ties. The current corpus tolerates alternate near-tied investment point counts; an end-to-end trace must still catch any resulting decision drift. Native-required CI must fail if it falls back to Python.
6. **Reprofile after the memo is repaired and validated, then choose the native scope.** The branch's current profile identifies placement search and event sandboxes/DEFCON work as substantial overlapping costs. Do not add cumulative percentages or reuse the old plan's speedup ceilings. Measure whole decisions including conversion and unprofiled full games; keep fixed-work throughput separate from equal-time playing strength. For a broad engine port, additionally pin RNG/chance semantics and pending-decision continuation state; merely giving two languages the same seed will not provide replay equivalence.

The next performance hypothesis after the existing placement memo is repeated event-sandbox work. Its key must include recursion guards and helper context; caching the observation alone is insufficient. This is an investigation, not another confirmed speedup. Deeper search, headline/AR1 planning and new strength features are not prerequisites for a faithful evaluator port.

## Additional recommendations before Rust

Do a short correctness-and-measurement pass, then start the bounded native kernel. Do not make more strength tuning a prerequisite. The cheapest useful work is fixing the five reproduced defects, specifying the current batch interface, and capturing a trustworthy reference. Neither a full engine rewrite nor another broad parameter sweep is necessary first.

### Experiments worth doing, in priority order

| Priority | Experiment | Measurement and decision |
|---|---|---|
| 1 | Cache enabled versus bypassed, using the same persistent player across decisions | Start with F3/F5 fixtures, then full traces through turn 10, borrowed Ops, scoring cards and side changes. Compare values, rankings, point counts and selected actions. A cache must preserve semantics; a good win rate cannot compensate for a missing key dependency. Record hit rate and peak memory as well. |
| 2 | Reprofile corrected main with the repaired memo | Use a small fixed early/mid/late decision set and several fixed full-game seeds. Separate unprofiled wall time from profiler attribution; report median/tail decision time, full-game time and memory. Include context-key construction, hashing and conversion costs. Use the result to choose the first Rust batch boundary. |
| 3 | Measure repeated public-event sandbox work before adding a cache | Instrument calls, repeated semantic inputs, total avoidable time, key cost and retained memory. If material, prototype a bounded cache with every guard/helper dependency explicit and compare against bypassed traces. Stop if saved work does not beat lookup/key overhead. |
| 4, optional | Bounded headline-plus-AR1 valuation | First use 3–5 annotated positions where current headline selection misses a concrete follow-up. Price the *incremental* AR1 benefit, remove the headline card from the remaining hand, and use legal, risk-aware follow-ups. Only if those cases improve, test one candidate on paired seeds/both seats against the same corrected baseline, with an advance stopping rule and a held-out confirmation block. Track latency as well as strength. |

The fresh [placement-memo profile](../claude/2026-09-27-fresh-profile-and-the-placement-memo.md) reports 105.3s → 84.9s across six matching games. This is useful author evidence for the idea, but F5 prevents treating those six traces as sufficient exactness evidence. Its repeated public-event calls account for roughly 6% of pre-memo game time, not the whole event-sandbox cumulative cost. That makes a small measurement/cache experiment plausible; it does not establish a large additional speedup. Cumulative placement, delta and sandbox percentages overlap and cannot be added.

The [headline/AR1 proposal](../claude/2026-09-27-headline-then-ar1.md) needs one semantic qualification: the USSR headline and USSR AR1 are **not always consecutive**. Resolution order follows headline Ops, with US winning ties (and special-card handling). A higher-Ops USSR headline can be followed by the US headline before USSR AR1. Model that intervening event honestly rather than pricing an uninterrupted two-move sequence or using the opponent's hidden hand. This is an optional strategy experiment, not a port blocker.

### Experiments I would not repeat now

The ledger and latest notes already answer several tempting axes. The [events-still-to-come family](../claude/2026-09-26-events-still-to-come.md) ended with decay 0.2 at paired -0.001 [-0.022, +0.020] versus baseline, and -0.006 [-0.025, +0.014] versus decay 0.4. Do not launch another decay/weight grid without a new, falsifiable mechanism. Likewise, do not resurrect the deleted hand-assignment planner or repeat the already-merged simplification/indexing work as Rust prerequisites.

If the reason for Rust is *stronger search*, rather than cheaper games/tournaments, establish a compute-versus-strength curve separately before committing to a large search rewrite. More nodes are not automatically better decisions. Revisit the existing MCTS replication/horizon evidence first; vary one budget axis on a corrected baseline, measure real latency, and keep this separate from fixed-work native parity. A small faithful evaluator port does not need to wait for that research.

Recommended scope: corrected Python oracle → explicit batch contract and persistent-player parity → fresh profile → one native evaluator/placement batch. Stop prerequisite work there unless the measurements identify a different dominant cost.

## Validation, retrieval and limits

- GitHub default branch and all current branch heads were queried. Source was pinned through the Git tree and materialized using GitHub text blobs because direct Git transport was unavailable. Every source/test/document blob was hash-verified against that tree except `tests/corpus/positions.json.gz`: the connector refuses binary blobs. That local corpus is old and was deliberately NOT used as current parity evidence.
- `uv sync --offline --frozen --extra test` was attempted and failed on an uncached pygments wheel. Tests then ran through `uv run --no-sync python -m pytest`, with current `src` and an existing Python 3.12 test-dependency directory on PYTHONPATH. This is a dependency reuse workaround, not a successful fresh frozen install.
- Focused command covered `test_events`, `test_event_board_choices`, `test_pool_reports`, `test_wave_verdict`, `test_benchmark_stall`, `test_measure_ties`, `test_evaluator`, `test_history_privacy`, `test_replay_and_isolation`, and `test_mcts`: **305 passed, 1 xfailed**. The xfail is the documented nonacting-seat observation leak.
- Matching-SHA full-suite CI [36333140614](https://github.com/JamesYouL2/struggler/actions/runs/36333140614), job `108658810837`: successful frozen dependency sync and `uv run pytest -q`. This is CI evidence for the full suite, including current corpus, not a full local run.
- Reproductions: `logs/audit-2026-09-27/reproduce.py`, `reproduce_war_scorer.py`, `reproduce_branch.py` plus output files. The branch reproduction loads its exact policy source with unchanged main dependencies (policy is the branch's only production-code diff).
- No fresh performance benchmark was run. Branch speed claims are attributed, not independently certified. Recent-change review plus sampled engine scoring/events, observations, replay, evaluator/cache boundaries, MCTS tests, and experiment-accounting paths; no exhaustive LLM, physical-mode, card-by-card, or fitting-model review.
