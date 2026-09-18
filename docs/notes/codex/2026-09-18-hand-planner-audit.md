# Bot audit and hand-planner implementation plan — 2026-09-18

## Revision, scope, and status

Reviewed remote default branch `main` at `43753a5671640ab4cf2c67c8af081d520cbc07e1`. A fresh clone and `git ls-remote --heads origin` agreed. Previous review: `d541db2d811ce47e8be1deaba069fd278674fe9c`; historical baseline `v0.1.0` resolves to commit `3c3125431f2979171101cbda07e95f69b65b5ddd` (the annotated tag object is `50e5af5`, not the source revision).

Remote `rebuild/value-function` is `ce1293dd1fcd871209dcc94e88ce1d8dbda57bb7`, also its merge base with main: already incorporated. No separate hand-planner implementation branch appeared in the remote head inventory. Gross per-mode value helpers exist on main; joint hand assignment does not. The expected-VP potential remains a diagnostic, not default ranking. Do not restart implemented schedule/forecast/DP components or block tactical hand fixes on that larger integration.

This is a focused repeat audit: live strategic card/mode selection, survival search, event/engine integration, space progression, scoring timing, public information boundaries, recent fixes and experiment reporting. Read project instructions, architecture, bot/card/testing/limitations/rules documentation, the existing hand-planner plan, rebuild notes and latest drift report. Not an exhaustive card audit, physical-mode audit, native-port review, or live LLM integration check. No implementation changes or tournaments were made. The user subsequently requested publication of this note and the revised sequencing in a pull request. The changes are documentation only; no merge or implementation work is included.

## Assessment

There are two distinct problems: concrete safety implementation defects, and a survival-only model being asked to perform value allocation and sequencing. Fix the concrete safety defects and add narrow last-safe-exit protection first, then finish the VP rebuild before building the full value-based hand allocator and targeted sequencing. A larger search over the same frozen transitions would confidently repeat several of these mistakes.

The user's desired policy is appropriate: spend a dangerous card while it is safe if waiting can close its last reliable exit. This is not the same as banning every battleground coup while holding CIA, nor blindly spacing the worst event. A valid hold, UN pairing, modified-Ops space attempt, discard route, or immediate win can change the answer.

## Verified findings

### F1 — P1: safe spacing is labeled certain defeat at the card-selection layer

Location: `policy.py::_score_card_play` (around 2967–2993), `safety_key`, `space_card`.

`card_play_value` evaluates Ops/event, returning the LOSS sentinel for an opponent suicide event. `_score_card_play` returns that sentinel before reaching its Space Race alternative. `safety_key` therefore declares the CARD certain defeat even when `action_risk` correctly returns `(0, 0)` because spacing is legal.

Reproduction with existing fixture:

```python
from test_defcon_planner import setup_hand
from struggler.engine import Side
from struggler.bots.strategic import StrategicPlayer

e = setup_hand(['Duck_and_Cover', 'Fidel'], rounds=2, defcon=2)
e._push_action_round_play(Side.USSR)
b = StrategicPlayer()
o = e.observe(Side.USSR)
for key, action in b.rank_actions(o):
    print(action.payload, key, b.action_risk(o, action))
```

Duck and Cover: key `(-1, 0.0, -317.5384615384616)`, risk `(0.0, 0.0)`, despite `space_card == Duck_and_Cover`. Fidel ranks first. This fixture proves misclassification and delay, not that the two-card sequence must lose: the later mode chooser can still space Duck. Existing tests begin at PLAY_MODE and miss this layer.

Small correction: rank legal card+mode pairs with each pair's own value and risk; reduce those pairs to a card score only afterward. Certain defeat means every legal continuation loses. At minimum move legal disposal evaluation ahead of the terminal return; do not suppress genuine terminal outcomes by arithmetic on sentinels. Test ACTION_ROUND_PLAY and PLAY_MODE together, with and without a space attempt, and with UN as an alternative.

### F2 — P1: Cuban Missile Crisis protection is assumed even when the opponent can cancel it

Location: `defcon.py::coup_threat` (around 160), compared with `engine/core.py` CMC cancellation interrupts.

The planner returns no coup threat whenever the opponent has the CMC flag. The engine correctly lets that opponent pay to cancel at an atomic boundary, including during our action. The planner never tests the available cancellation.

Reproduced: USSR, DEFCON 2, final round, hand `[CIA_Created]`, space used, USSR Cuba 2; `turn_effects['cuban_missile_crisis'] = 'US'`; US West Germany 4. The planner gives CIA event risk **0.0**. Following real legal decisions produces:

1. USSR plays CIA for Ops.
2. US accepts the CMC interrupt and removes influence from West Germany.
3. CIA grants US operations; US chooses coup, targeting Cuba.
4. Engine ends at DEFCON 1, winner US, responsible player USSR.

Small correction: include legal cancel-and-coup continuations on a copied public state, applying the payment before enumerating coup targets. Reuse engine eligibility; merely treating CMC as always absent would create the opposite false positive. Cover cancellable/noncancellable CMC, both seats, and payment that removes the last relevant target.

### F3 — P1 behavior gap: the frozen board permits a deterministic self-created CIA trap

Location: `defcon.py` module contract, `hazardous`, `_solve` fast exit, `transition`; policy's card/mode and influence decisions.

This is a documented model limitation with a demonstrated losing policy consequence, not a newly discovered engine-rules defect. Event transitions do not advance the board. A hand with no current hazardous card short-circuits to zero, even if the chosen event creates a future coup target. The special post-coup survival check does not cover event or ordinary influence changes.

Reproduction: `setup_hand(['CIA_Created', 'Fidel'], rounds=2, defcon=2, space_used=1)`; clear USSR influence from Cuba. With no currently legal CIA coup target, both Fidel-event and Fidel-Ops continuations receive zero risk. Real policy decisions are **Fidel → event → CIA → Ops**. Fidel puts USSR 3 in Cuba; CIA is now a forced suicide event. Playing CIA before creating the target was safe.

Small correction: at least simulate candidate board-changing actions through their relevant public-state effects, then recompute survival on the resulting state. Maintain a compact coup-target/eligibility signature if that is sufficient; do not recompute hazard solely from the root board. Carry the same check through event choices and influence placement, not only coup targets. Test the safe reverse order as well as the losing order, so the fix does not just ban Fidel.

### F4 — P2: simulated Space Race advancement misses the newly acquired second attempt

Location: `defcon.py::space_ok`, `transition`; engine `advance_space_race_box`, `_space_attempts_allowed`.

The search updates hypothetical space position and attempts, but `space_ok` obtains the allowance from the unchanged root engine's ability flags. Reaching box 2 first therefore does not enable the second attempt inside the search.

Reproduction: USSR box 1, US box 0, no attempts used, DEFCON 2, two rounds left, hand Duck and Cover / KAL-007 / CIA, USSR Cuba 2. With opponent attack/drop priors off, spacing Duck is reported as loss risk **1.0**. The proper continuation has risk **1/3**: success to box 2 has probability 4/6, enabling spacing KAL and holding CIA; failure leaves only one disposal and loses. The real engine after `advance_space_race_box(USSR)` allows two attempts and accepts KAL.

Small correction: make ability state consistent with simulated positions, preserving first-arrival/cancellation semantics and relevant opponent progress. Test success and failure separately and opponent already at box 2. The live policy can notice a second attempt on its next replan; the defect is the current search's forward estimate, not a claim that the engine never permits it.

The rulebook explicitly makes the ability immediate and permits the second attempt next action round; disposal suppresses the event regardless of the roll. Source: [GMT rules, §§6.4.4–6.4.5](https://www.gmtgames.com/living_rules/TS_Rules_Deluxe.pdf).

### F5 — P2 diagnostic defect: accepted risk is logged as zero

Location: `policy.py::_log_choice` (around 925), `safety_key` (around 960).

For raw-score actions the key's middle field is now always zero: risk was moved into the score. `_log_choice` still reads that field as negative risk. It prints `risk=-0.000` and skips the accepted-risk warning even for a nonzero planner estimate.

Reproduction: USSR hand CIA / Decolonization, two rounds left, DEFCON 3, space used, USSR Cuba 2; set US influence Italy 3, France 3, West Germany 4, Egypt 2. The bot chooses Decolonization with actual whole-turn risk **0.15**, key score **11.03215537853719**, but logs `risk=-0.000`. CIA scores 0 and would clear the hazard now.

Correction: retain explicit immediate/total/residual risk alongside the ranking, and log those fields rather than decoding the sort tuple. Test emitted risk against `action_risk`. Reuse the already calculated values instead of re-running survival just to log them.

This also qualifies the overnight report's interpretation: the existing planner DOES model dropping DEFCON before the next turn at the table. It can prefer CIA first in simple DEFCON-3 fixtures; in this fixture it deliberately accepts the 0.15 prior-sized risk for Decolonization's score. “It does not consider early disposal” is too broad. Some logs also overstate certain defeat because of F1. Neither point disproves the recorded nuclear endings, but aggregate endings do not identify the decision that first made loss avoidable or inevitable.

## Prior findings and other audit observations

- September 17 F1–F5 have code fixes in merged `9cd13a5`: Yuri uses turn effects through its consumer, SEA one-shot/recycling and exhausting-deal accounting changed, next-turn reply context expires modifiers, and the expected-VP wrapper handles modifiers/seat/SEA. Reviewed those changes and relevant tests; do not queue yesterday's fixes again.
- Scoring selection still mostly prices current payout plus `2 * action_round`. Regional urgency guides investment but does not compare an explicit improve → opponent reply → score sequence with scoring now.
- `value_as_held` calls current-position `hold_value`; it is not a true next-turn continuation or a coordinated hold assignment. Gross helpers exist, but the policy still uses local best-use values and a single current `space_card` recommendation.
- `_score_event_ops_order` always favors event-first. Often sensible for repairing damage, but insufficient for minimizing events that can be deactivated, weakened, or timed after scoring.
- The survival module uses observation/public sandbox state; no hidden-hand reads were found in this path. Unknown draws and attacks remain explicit approximations. This is not a fresh proof of all bot information boundaries.
- The latest experiment notes favor retaining reply/access/rival terms. Their aggregate counts suggest investigating hand survival, but do not prove it explains the full strength difference causally. I did not rerun or independently download those experiment artifacts. The pooling implementation uses complete paired seeds and the shared summary routine, which is the right basic unit.
- Documentation is stale in places: STRATEGIC_AI still says the flat DEFCON-drop prior is .75, while code is .15; the old rebuild README is a proposal rather than a current completion report. Update these when touching the relevant implementation.

## Review of the v2 hand-planner plan published during this audit

Main advanced to `65cf804` with [the v2 plan](../claude/2026-09-18-hand-planner-plan.md), not implementation. Its new ordering agrees with the central recommendation here: tactical disposal need not wait for the value rebuild. Preserve that direction, but amend these details before implementing:

1. **Add the verified defects above before tuning the policy.** The zero-risk logs and false certain-loss card classifications weaken instrumentation built around those log fields. The proposed “first certain loss” counter is not yet a trustworthy feasibility counter.
2. **Do not make `lethal_below(card)` a context-free constant.** Borrowed-coup lethality depends on board targets, CMC cancellation, Nuclear Subs, event prerequisites and hand chains. Cache a context-specific result or explicit conditions. “CIA/Lone Gunman can never be spaced” is false under applicable Ops bonuses: the existing test `test_one_op_cia_is_not_spaceable_without_ops_bonus` covers Brezhnev enabling CIA spacing.
3. **Coordinate space and hold before declaring either complete.** A temporary space-only change is testable, but the unspaceable hazard versus spaceable harmful event case needs joint allocation immediately. A single `space_card()` recommendation does not prove a second attempt can never be used: the bot replans afterward. F4 identifies the narrower actual forward-model defect.
4. **Scoring timing does not require an expert rule of thumb before a prototype.** The game supplies exact current payout and small fixtures can establish useful counterfactuals. A region's score at another time in the realized log is a descriptive opportunity trace, not causal regret: choosing a different scoring time would change both players' subsequent actions. Use forks from that decision with a fixed disclosed reply policy to evaluate alternatives, and label the model limitation.
5. **Protect the claimed accounting.** Raw helpers are not already expected VP. Future-play values need consistent state and do not simply add independent frozen-board gains. Reserve Blockade payers conditionally and subtract replacement-draw cost only where it changes the comparison, as discussed below.
6. **Evaluate without importing opponent omniscience.** An adversarial cheap-coup stress test is useful, but an opponent does not know we hold CIA unless entitled to that information. Use public availability/legality and label worst-case stress separately from predicted behavior. Privacy also does not require all simulated replies to be eventless; eventless replies are a scope choice, while public-information-consistent event sampling is allowed.
7. **Use strength plus tactical outcomes as acceptance, not imitation targets.** Low space usage can motivate investigation but does not itself establish how often to space. A Duck-at-DEFCON-3 fixture needs a specified hand/board/alternative; spacing it is not universally better than a safe play now. The human nuclear-loss band is not a correctness target. The paired fixed-anchor comparison is useful, but aggregate nuclear counts alone do not causally identify the entire drift.

## Implementation sequence and acceptance criteria

### Sequencing revision after follow-up discussion

**Safety fixes → last-safe-exit protection → finish the VP rebuild → joint space/hold allocation → scoring/event sequencing.** This supersedes the initial recommendation to implement the full allocator before completing the VP rebuild.

The rebuild is far along in components: schedule, forecast, stochastic payout and gross per-mode helpers already exist. At the audited revision, however, expected-VP potential remains outside default ranking. Affordable evaluation, consistent integration and playing-strength validation still separate implemented components from a shippable replacement.

The full hand allocator must compare Ops, opponent-event damage, space rewards, retained-card value and scoring opportunities. Implementing that larger optimizer against the old evaluator and then replacing its foundation creates avoidable rework. Complete the VP integration first if the remaining performance problem is bounded. The concrete safety defects and narrow disposal guard depend on legality and resource feasibility, so they should not wait for that integration.

| Order | Deliverable | Completion condition |
| --- | --- | --- |
| 1 | Repair safety contracts and diagnostics | F1–F5 regressions pass through card selection and execution |
| 2 | Protect the last reliable disposal window | Closing-window fixtures pass, with valid-exit and immediate-win exceptions preserved |
| 3 | Finish and integrate the VP rebuild | Representative ranking meets an explicit runtime budget; accounting and integration checks pass; paired strength validation is acceptable |
| 4 | Jointly allocate space, hold and other hand resources | One coherent objective and no double allocation of cards or disposal capacity |
| 5 | Add scoring and event sequencing | Concrete improve/reply/score and event-order fixtures pass; measured strength and cost justify the added search |

The checkpoint for step 3 is the cost of the integrated evaluator on representative rankings. If that is solved, completing the rebuild next is compelling. If it still needs unresolved kernel/performance work, record that blocker and revisit the dependency rather than blocking hand improvements indefinitely. Do not equate a large amount of completed code with a small amount of remaining integration work.

### 1. Repair safety contracts and make escape plans inspectable

Fix F1, F2, F4, F5, and add the minimal post-action state checks for F3. Return a structured result per candidate: immediate loss, continuation loss estimate, reliable escape path, required resources, and whether search truncated. A speculative draw or successful space roll is not a guaranteed exit. A space attempt DOES discard its card on failure; only later progress/eligibility is random.

Use one card+mode evaluation for selection and execution. Do not combine `min(risk over modes)` with `max(value over different modes)` and assume a real action achieves both. Preserve actual terminal wins as explicit outcomes.

Done when the reproductions above have integration regressions covering both the card pick and its continuation, existing privacy/isolation tests pass, and risk diagnostics agree with the decision calculation.

### 2. Add a deadline guard for the last safe disposal window

Before choosing a different card at DEFCON 3, evaluate the remaining hand after a legal opponent DEFCON-lowering reply. Also test our own candidate action's DEFCON and target changes. If the hazard cannot then be held, spaced, neutralized, paid away, or safely played, and it can be safely disposed of now, prioritize that disposal over ordinary board gains. At DEFCON 2 with no target, creating the first target is the analogous deadline.

Separate a known resource-feasibility fact from a probabilistic forecast. A global .15 drop rate averages states where drops are impossible with states where a cheap battleground coup is available; it is not the conditional probability needed here. Start with a clearly labeled conservative reachable-reply guard, not an assertion that an unseen opponent card is known. Later calibrate a state-conditioned prior on eligible opportunities, with held-out data and both seats.

Do not turn this into a universal “never coup with CIA” rule. With a reliable unused hold/China/UN/discard escape, the coup can be appropriate. Do not refuse a verified immediate win to protect a future turn. Multiple dangerous cards must compete for the SAME exits, not each independently claim the one space attempt or held-card capacity.

Acceptance: CIA/Lone Gunman before a closing window; controls with a valid hold or legal modified-Ops spacing; two hazards/one disposal; no legal opponent drop; own coup and event-created target; scoring deadlines and forced modes; no hidden-card identity dependence. The Decolonization fixture should prefer clearing CIA under the requested conservative policy, while an exit-preserving control can still prefer Decolonization.

### 3. Finish and integrate the VP rebuild

Reuse the existing schedule, forecast and payout components. First benchmark the intended ranking path on representative positions and set an explicit per-decision/game runtime budget. A fast standalone kernel is not enough if repeated calls or invalidation dominate the integrated cost.

Then carry one consistent VP accounting convention through board changes, direct VP, events, Space Race rewards and risk comparisons. Count scoring opportunities and payouts once, retain whole-potential deltas under a fixed context, preserve actual terminal outcomes, and verify modifier/seat/SEA integration. The previously repaired diagnostic contract is the starting oracle, not evidence that default ranking already uses it.

Completion requires the evaluator to be active in default candidate ranking, the relevant correctness and full-suite checks to pass, and a paired strength/runtime comparison against an explicitly pinned baseline with shared correctness fixes. Do not fold the new hand allocator into this comparison: isolate the value replacement first. Gate dispatch still requires the separate approval specified below.

### 4. Jointly allocate hand resources

Build a small hand-mask dynamic program or enumeration over actual remaining plays, space attempts, holds, China, UN pairings, scoring deadlines, and available discard routes. Ordinary hands are small; do this once per action-round decision, caching gross per-mode values within that decision. Enumerate headline choices outside the allocation as a separate consumption/ordering case.

Objective among survivable plans: board/VP gains + space reward + retained-card continuation − opponent-event damage − actual replacement-draw opportunity cost. Each card is consumed once; UN consumes two cards in one play; China consumes a play but is not an ordinary dealt card. Space consumes both a play and an attempt. Holdings are what remains after actual card flows, not a hardcoded one-card slot. Include extra rounds/forced plays using engine public scheduling helpers.

For disposal, compare avoided damage AND forgone useful Ops/events. Typically an unspaceable hazard goes to hold, a spaceable harmful card goes to space, and a cheap harmless event is allowed to fire. This is not a universal printed-Ops sorting rule. Holding a hazardous card avoids its event now but preserves the problem next turn; do not value it only as its forced play now. Re-evaluate turn effects, eligibility and next-turn disposal opportunities.

Reserve a modified-3-Ops Blockade payer only when its expected benefit exceeds its cost. The earlier plan's unconditional “must reserve” is too strong: Blockade may be unavailable, West Germany may not matter, or paying may be worse than accepting the board loss. Holding is also not necessarily an incremental lost draw between plans with the SAME number of retained cards; a constant draw-cost term cancels. Apply that cost when card flows/hold counts differ, with the appropriate public remaining/recycled pool.

Build the full value-based allocator on the integrated VP evaluator from step 3. Structural feasibility tests and the narrow safety guard can use the current evaluator before then, but do not expand that work into a second production optimizer against the old valuation. If VP integration is blocked beyond a bounded performance task, an explicitly scoped allocator prototype in current raw units is a fallback experiment, not the default sequence or a claim of calibrated expected VP.

Acceptance: two harmful cards do not both consume one escape; unspaceable CIA hold versus spaceable second hazard; two attempts including newly acquired ability; UN consumes its partner; failed space still disposes; current-vs-next-turn modifiers; no held scoring; variable hand sizes; deterministic output independent of option ordering.

### 5. Add targeted timing, not full-game search

An allocation is not an ordering solution. For each held scoring card compare score now against a few concrete one-action improvements followed by a legal opponent reply and scoring next action. Score first when deterioration is more likely; improve first when gains survive repair; flush a bad scoring before an upcoming opponent event worsens it. Date the reply correctly: the opponent may act between our investment and scoring even when we hold the scoring card.

Add a small beam only over timing-sensitive choices: hazard disposal, scoring, Ops modifiers, event deactivation/mitigation, UN/discard pairings and event-before/after-Ops. Reuse actual event transitions and the existing reply model. Replan after each opponent action, chance result or unexpected event. Within an uninterrupted deterministic Ops spend, reuse a legal plan, with snapshot invalidation and reachability unchanged.

Count banked scoring payout once and remove that opportunity from future potential; do not reward the same regional improvement separately as board potential, predicted scoring, and event benefit. Keep unrelated opportunities separate (Asia and SEA in particular).

Acceptance fixtures: scoring now beats a repairable investment; invest then score beats now when the reply cannot erase it; take positive scoring before firing a harmful opponent event; get a bad scoring out before making the region worse; order changes when event prerequisites/targets change; score deadlines remain feasible.

### 6. Validate actual strength and cost throughout the sequence

First use the tiny tactical suite, then the full existing suite. After implementation, run paired seeds in both seats against the parent and a fixed older anchor with shared engine fixes; freeze exact SHAs and use a held-out seed block. Strength gates need the maintainer's explicit dispatch approval under AGENTS.md; none was launched here.

Measure wins, nuclear losses by seat/card, the FIRST decision that destroys the last reliable escape, accepted risk calibration, scoring payout/timing, unused disposal capacity, planner truncation rate, and per-decision nodes/runtime. Do not optimize nuclear-loss rate alone: excessive passivity can lower it while losing more games. Do not target a human aggregate nuclear rate as a correctness invariant.

Keep the allocator outside repeated per-influence ranking and precompute card-mode features. Profile before porting anything. Existing historical “60% survival” notes are not a measurement of this revision. Share bounded search work across candidates without letting a shared budget make the answer depend on candidate iteration order; expose any fallback. Do not revive the expensive whole-board DP inside every hand-search node.

## Validation

- `uv sync --frozen --extra test` succeeded.
- `uv run pytest -q tests/test_defcon_planner.py tests/test_engine_defcon_chains.py tests/test_value_signs.py`: **65 passed in 2.84s**.
- Minimal Python probes executed against the pinned checkout reproduced F1–F5. F2 was driven through real legal engine decisions to terminal US victory; F3 was driven through actual policy card/mode choices.
- `uv run pytest -q`: **917 passed, 4 skipped, 1 xfailed in 327.31s** (exit 0). Code/tests match reviewed SHA; the publication-base update touched documentation only.
- Full-suite output: `logs/audit-20260918/full-suite.log` (untracked run artifact). Local verification was used because `gh` is absent in this environment; no duplicate suite or strength gate was dispatched.
- No playing-strength improvement is claimed from these probes or a green suite.

## Publication

Publication base: `65cf80448b19b7d6e45aa1edefa05d8bf954f6ab`. Main advanced during review with documentation only; source, tests, lockfile and package configuration are unchanged from reviewed `43753a5`. The full suite began on the reviewed revision and continued across only that documentation update. Only this note and its index entry are intended for the notes branch.

The initial push was blocked by automatic approval review pending explicit publication authorization. The user then explicitly requested adding the revised sequence to this Markdown and creating a pull request. The notes branch is `docs/audit-20260918-hand-planner`; the authorized publication contains only this audit note and its index entry.
