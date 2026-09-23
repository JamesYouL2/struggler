# Overall sequencing, accounting for the active rebuild branch — 2026-09-16

## Revision and correction to the earlier audit

Main reviewed: `18abdba2cd8725cdd8988ba6dabcb23ad5d2e07a`.
Active branch: `rebuild/value-function`, reviewed at `02c6e1692f4861f69f134ec968c38a890e9abe3f`, based on that main revision.

The [earlier audit](2026-09-16-engine-strategic-rebuild-audit.md) described main correctly but did not include this implementation branch. Do not restart its already completed prototype. Three commits on the branch add:

- `9ddeb45`: deterministic one-region payout prototype, generalized across regions, with whole-potential marginals.
- `8b78046`: pre-integration expert-inversion baseline and a safety-gate record.
- `02c6e16`: explicit schedule records, Southeast Asia payout, and Europe-control query.

The branch is deliberately unwired: none of these components changes the live strategic rankings yet. The main missing milestone is now **stochastic regional payout plus a useful control forecast**, not creation of the Africa module.

## Overall work order

| Order | Work | Completion criterion |
| --- | --- | --- |
| 1 | Close small correctness holes and settle the new interfaces | Fix the two main-policy coup-reply defects; fix the branch's one-shot schedule defect; specify probability conditioning, horizon units, and scoring-time terminal semantics |
| 2 | Implement stochastic regional payout | One expected regional tier from an explicit joint model/approximation; deterministic inputs still match the engine; no duplicate tier accounting |
| 3 | Build the useful control forecast and scoring schedule | Partial influence, legal access, pointwise Ops cost, protection, and horizon affect a coherent US/USSR/uncontrolled forecast; occurrence and timing have explicit meanings |
| 4 | Integrate one shared expected-VP potential | Placement, removals, coups, realignments, events, direct VP, and risk pricing use compatible units and accounting; certain terminal outcomes take precedence |
| 5 | Validate and evaluate the complete candidate | Accounting invariants, held-out forecast calibration, full suite, explained ranking changes, and paired-seat strength/runtime comparison against a frozen baseline |
| 6 | Tune residual discount and pursue further strength work | Tune only after uncertainty has an explicit meaning; deeper search/hand planning remain later hypotheses, with MCTS outside the current queue |

This is dependency order, not a requirement to idle one stream until every unrelated fix merges. The current bot's reply fixes can proceed independently of the unwired rebuild. Carry those fixes into both the eventual comparison baseline and candidate so the rebuild comparison does not conflate a correctness repair with a new value model. Record exact comparison SHAs.

## Immediate branch correction: Southeast Asia can currently score twice

`schedule.opportunities` excludes spent/removed Southeast Asia Scoring and its final-scoring term, but it does not exclude a *live* Southeast Asia card from the generic next-cycle block. A turn-4 observation holding that card with an empty draw pile produces:

```text
bucket 1: occurrence 1.0, turns 0..0
bucket 3: occurrence 1.0, turns 1..6
total occurrence mass: 2.0
```

This contradicts the one-shot lifecycle, even under the current assumption that the game continues. Reproduced directly on `02c6e16`; existing schedule tests cover spent SEA and absence from final scoring but miss live-card recurrence.

Small correction: a live one-shot must not receive an additional post-reshuffle payout. If a future timing model spreads its one possible play across alternative dates, those dates share a total mass of at most one. Add held, unseen, future, spent, and removed one-shot cases. This is a branch integration blocker, not a live-policy regression, because the module is unwired.

## Rebuild sequence in detail

### A. Nail the contracts before supplying fitted numbers

- `Opportunity.occurrence` currently claims `P(pays before game end)` while its nonfinal values omit early termination and mostly assume occurrence. Either label these as conditional placeholders or implement the promised unconditional probability before integration. A rules deadline is not unconditional certainty of a payout: game end and card-removal effects can intervene.
- A `(turns_lo, turns_hi)` interval does not define a timing distribution. Supply explicit dated masses or a documented weighting rule before applying a nonlinear discount; do not silently use the midpoint.
- `ControlForecast.horizon` currently counts scoring opportunities, while schedule horizons count turns. Define their connection explicitly, preferably with distinct fields/types. Per-scoring retention cannot silently become per-turn retention.
- Validate finite probabilities, bounds, normalization, member alignment, and horizon validity at the forecast construction boundary. NamedTuple annotations alone do not enforce these invariants.
- Europe's control helper reports a scoring condition, not an already terminal board. Check automatic victory when Europe actually scores, or when consuming an engine-terminal result. Merely acquiring Europe control before its scoring is not an immediate win.

### B. Finish the stochastic payout component using supplied probabilities

`expected_tier_payout` currently raises `NotImplementedError` for nondegenerate forecasts. Resolve this before fitting probabilities that the consumer cannot use.

A declared country-independence approximation is a reasonable first baseline, provided its limitations are measured. Compute a distribution over the region's relevant country/BG counts and apply the rules' tier payout to each outcome; do not apply tier thresholds to expected counts. Correlated regional scenarios are an alternative if an explicit scenario model already exists. Choosing between them requires modeling judgment, not more interface scaffolding.

Keep immediate deterministic scoring exact. Test small stochastic regions against an exhaustive outcome oracle, both seat signs, non-BG domination requirements, and deterministic reduction. Preserve SEA as its separate linear payout. With Shuttle/Formosan, make both the total and the bonus/tier decomposition honor modifiers; matching only the summed total can conceal misclassified components.

### C. Forecast controls and date scoring opportunities

Replace horizon-invariant current control with a three-outcome forecast conditional on the scoring occurring. Include partial progress, pointwise placement cost, overprotection, and legal access; do not equate lack of immediate placement reach with impossibility of eventual acquisition through all routes/events/coups.

Use supplied horizons while completing the schedule. Then replace the old 50/50 placeholders with an explicit public-information model for possession/drawing/playing and continuation to scoring. Keep repeated scorings distinct from alternative dates for one scoring. Retention belongs inside the control forecast, not as a second multiplier charging the same control loss.

### D. Integrate coherently, then compare

Build signed banked VP plus the sum of occurrence-weighted, time-discounted expected payouts. Banked VP is added once without discount. Recompute raw action deltas from the same potential, including changes in neighboring access. Retain separate explicit reply/tempo adjustments and test raw telescoping with them disabled and context held fixed.

Convert Ops/event/direct-VP/risk comparisons together. Start with a clearly stated residual-discount baseline, such as no extra discount beyond modeled uncertainty, rather than copying the superseded discount by habit. Keep explicit terminal precedence, including scoring-time Europe control. Remove or retire old weights only when their callers have moved and historical weight/corpus compatibility is handled deliberately.

Test calibration on held-out games, not rows randomly split from the same games. Expert-order checks are useful diagnostics but are neither universal ground truth nor substitutes for paired-seed, both-seat evaluation. Run the full suite before adoption; retain the old corpus, explain candidate ranking changes, and capture candidate expectations separately. Strength-gate dispatch still follows the repository's authorization policy. Do not run repeated strength gates on unwired scaffolding: identical live bots cannot establish the new model's strength.

## Where performance, typing, and other work fit

- **Small independent performance task:** precompute fixed card allegiance in the DEFCON planner. The earlier audit found a concrete hotspot. Preserve rankings, risk results, search node counts, and truncation behavior. This need not block the prototype.
- **Before the final evaluation:** profile the integrated candidate. Stochastic regional payout may create a new dominant cost; optimize that actual cost instead of accumulating speculative caches now.
- **Low priority:** memoizing completed reply-budget distributions and pure coup outcomes. Both were small costs in the earlier profile.
- **Typing now:** forecast, payout, timing, and reply-context boundaries. General annotation/lint debt can wait. Existing strict type tests and snapshot/accounting regressions remain required.
- **Defer:** more old-model weight sweeps, opening churn, deep search, broad refactors, and language-port work. They do not unblock the current rebuild and complicate attribution.

## Validation and note status

Static review of the branch modules, tests, and progress notes; focused execution used the branch's source in an isolated detached worktree. `test_forecast.py` and `test_schedule.py`: **21 passed**. The live-SEA double-scoring reproduction above succeeds despite those passing tests. This was a sequencing review, not a full branch audit or rerun of its strength gate.

Only documentation in the audit-notes checkout was updated; no implementation was changed. The user subsequently authorized publication to a separate branch in JamesYouL2/struggler. These notes accompany the earlier audit on `docs/audit-20260916-engine-strategic-rebuild`; no PR or merge is requested.
