# Claude working notes (Fable)


A scratchpad for whoever picks this up (Astra, or another model): the
strategy principles the maintainer has stated, what the bots do about
each, and what is still open. Principles are quoted as given; evidence is
linked. Update this file when a principle is implemented or refuted.


## Contents

One file per topic. Recent entries sit here; older ones are in
`archive/`. `bug-shapes.md` is the defect registry and has a stable
path because `tests/test_recurring_defects.py` parses it.

- [Handoff, 2026-09-13 — written for Codex, for a second viewpoint](2026-09-13-handoff-for-codex.md) — 2026-09-13
- [What a random move costs](2026-09-12-what-a-random-move-costs.md) — 2026-09-12
- [Handoff, 2026-09-12](2026-09-12-handoff.md) — 2026-09-12
- [`access` is the tiebreaker, so the ablation cannot accept](2026-09-12-access-is-the-tiebreaker.md) — 2026-09-12
- [The reliability curve, and why the headline number is the least trustworthy part of it](2026-09-12-the-reliability-curve-says-anchor-at-t3.md) — 2026-09-12
- [The battleground revamp: every formula, current and target](2026-09-12-battleground-revamp-plan.md) — 2026-09-12
- [Importance is a function of Ops efficiency, and that alone makes the bot worse](2026-09-12-importance-is-ops-efficiency-but-not-alone.md) — 2026-09-12
- [The reshuffle fix was correct and cost eight points](2026-09-12-the-reshuffle-fix-cost-eight-points.md) — 2026-09-12
- [The flat VP curve fixed the battleground level, and the Ops rate is still a parameter](2026-09-12-the-flat-curve-fixed-the-battleground-level.md) — 2026-09-12
- [`access` should be a conversion probability, not three guessed weights](2026-09-12-access-wants-a-conversion-probability.md) — 2026-09-12
- [The Ops-to-VP rate is a parameter, and the rule cannot be expressed](2026-09-12-the-ops-vp-rate-is-a-parameter-not-a-measurement.md) — 2026-09-12
- [Board value is three variables per battleground](2026-09-12-value-times-probability-times-discount.md) — 2026-09-12
- [What deserves the 256-seed ceiling: `battleground`](2026-09-12-what-deserves-256-seeds.md) — 2026-09-12
- [The bot does not cycle the deck, and the third scoring is rarer than it looks](2026-09-12-the-bot-does-not-cycle-the-deck.md) — 2026-09-12
- [The reshuffle is where the information is](2026-09-12-the-reshuffle-is-where-the-information-is.md) — 2026-09-12
- [Shared rules arithmetic left the greedy bot](2026-09-11-shared-rules-arithmetic-left-the-greedy-bot.md) — 2026-09-11
- [The Space Race had a zero-VP wall in front of every reward](2026-09-11-the-space-race-had-a-zero-vp-wall.md) — 2026-09-11
- [`vp_base` cannot fix the battleground level, and what that points at](2026-09-11-vp-base-cannot-fix-the-battleground-level.md) — 2026-09-11
- [Win probability is the objective; VP is the currency](2026-09-11-win-probability-is-the-objective-vp-is-the-currency.md) — 2026-09-11
- [The hand planner: the plan, and what has to happen first](2026-09-11-the-hand-planner-plan.md) — 2026-09-11
- [Tournament-shaped stats, and where the bot field differs from a human one](2026-09-11-tournament-shaped-stats-and-how-the-bot-field-differs.md) — 2026-09-11
- [When the deck reshuffles, and why the estimate was early](2026-09-11-when-the-deck-reshuffles-and-why-the-estimate-was-early.md) — 2026-09-11
- [Would a full Rust port give ten times, and is numpy a correctness tool?](2026-09-11-would-a-full-rust-port-give-ten-times.md) — 2026-09-11
- [2026-09-11 — The gate's time budget: under an hour, and why ten minutes is not close](2026-09-11-the-gate-s-time-budget-under-an-hour-and-why-ten-minutes-is.md) — 2026-09-11
- [2026-09-11 — Breaks by Operations spent: the maintainer's 4 > 3 > 2, measured](2026-09-11-breaks-by-operations-spent-the-maintainer-s-4-3-2-measured.md) — 2026-09-11
- [Wipe exposure is a variance term, not a discount — and turn 1 is not turn 4](archive/2026-09-10-wipe-exposure-is-a-variance-term-not-a-discount-and-turn-1-i.md) — 2026-09-10
- [Win probability: the shape, and the ceiling](archive/2026-09-10-win-probability-the-shape-and-the-ceiling.md) — 2026-09-10
- [Win probability is now the answer to four separate questions](archive/2026-09-10-win-probability-is-now-the-answer-to-four-separate-questions.md) — 2026-09-10
- [Why the bot buys exactly one point: `_investment` keeps the smallest tie](archive/2026-09-10-why-the-bot-buys-exactly-one-point-investment-keeps-the-smal.md) — 2026-09-10
- [What function fits the three tiers: one VP per Op, and Europe is not special](archive/2026-09-10-what-function-fits-the-three-tiers-one-vp-per-op-and-europe.md) — 2026-09-10
- [Wars have dice, and 1-Op cards have no exits](archive/2026-09-10-wars-have-dice-and-1-op-cards-have-no-exits.md) — 2026-09-10
- [VP are not linear, and two places are discontinuous](archive/2026-09-10-vp-are-not-linear-and-two-places-are-discontinuous.md) — 2026-09-10
- [Urgency never reaches zero, and its absolute level is not a parameter](archive/2026-09-10-urgency-never-reaches-zero-and-its-absolute-level-is-not-a-p.md) — 2026-09-10
- [Two exceptions, and both are arithmetic](archive/2026-09-10-two-exceptions-and-both-are-arithmetic.md) — 2026-09-10
- [Twenty Late War valuations, and what my errors were actually made of](archive/2026-09-10-twenty-late-war-valuations-and-what-my-errors-were-actually.md) — 2026-09-10
- [Turn-1 Battleground importance for the US, priced in Ops-to-reach](archive/2026-09-10-turn-1-battleground-importance-for-the-us-priced-in-ops-to-r.md) — 2026-09-10
- [Turn 10 action round 7: the play that cannot be answered](archive/2026-09-10-turn-10-action-round-7-the-play-that-cannot-be-answered.md) — 2026-09-10
- [Three corrections that change the roadmap](archive/2026-09-10-three-corrections-that-change-the-roadmap.md) — 2026-09-10
- [Threat is effect minus printed Ops, and it inverts the whole wipe table](archive/2026-09-10-threat-is-effect-minus-printed-ops-and-it-inverts-the-whole.md) — 2026-09-10
- [The yardstick is a coup: why the Battleground scale cannot be tuned](archive/2026-09-10-the-yardstick-is-a-coup-why-the-battleground-scale-cannot-be.md) — 2026-09-10
- [The win-probability fit: the maintainer's shape wins, and it saturates](archive/2026-09-10-the-win-probability-fit-the-maintainer-s-shape-wins-and-it-s.md) — 2026-09-10
- [The scale invariance, stated properly -- and what it makes unbuildable](archive/2026-09-10-the-scale-invariance-stated-properly-and-what-it-makes-unbui.md) — 2026-09-10
- [The same-Ops tie-break, specified](archive/2026-09-10-the-same-ops-tie-break-specified.md) — 2026-09-10
- [The rule: twice means a test](archive/2026-09-10-the-rule-twice-means-a-test.md) — 2026-09-10
- [The rule that explains the whole exercise](archive/2026-09-10-the-rule-that-explains-the-whole-exercise.md) — 2026-09-10
- [The region margin, specified](archive/2026-09-10-the-region-margin-specified.md) — 2026-09-10
- [The poke count: the forward search does not yet work in play](archive/2026-09-10-the-poke-count-the-forward-search-does-not-yet-work-in-play.md) — 2026-09-10
- [The hand planner's real justification, from the maintainer](archive/2026-09-10-the-hand-planner-s-real-justification-from-the-maintainer.md) — 2026-09-10
- [The game is not worth 40 VP from where you are standing](archive/2026-09-10-the-game-is-not-worth-40-vp-from-where-you-are-standing.md) — 2026-09-10
- [The dead Battleground is not dead: it is an option on Control](archive/2026-09-10-the-dead-battleground-is-not-dead-it-is-an-option-on-control.md) — 2026-09-10
- [The complete list of exits, corrected](archive/2026-09-10-the-complete-list-of-exits-corrected.md) — 2026-09-10
- [The bugs this repo actually gets](bug-shapes.md) — 2026-09-10
- [The VP-cycle fix was rejected, and the reason is worth keeping](archive/2026-09-10-the-vp-cycle-fix-was-rejected-and-the-reason-is-worth-keepin.md) — 2026-09-10
- [The USSR asymmetry is still not established, and the row counts lied](archive/2026-09-10-the-ussr-asymmetry-is-still-not-established-and-the-row-coun.md) — 2026-09-10
- [The Middle East cannot be overprotected, and Asia cannot be wiped](archive/2026-09-10-the-middle-east-cannot-be-overprotected-and-asia-cannot-be-w.md) — 2026-09-10
- [The China charge is in the wrong units, and rescaling is not a no-op](archive/2026-09-10-the-china-charge-is-in-the-wrong-units-and-rescaling-is-not.md) — 2026-09-10
- [The Battleground table, answered as structure rather than numbers](archive/2026-09-10-the-battleground-table-answered-as-structure-rather-than-num.md) — 2026-09-10
- [The Battleground scale, measured: the bot is 4x low, 5x flat, and orders it wrong](archive/2026-09-10-the-battleground-scale-measured-the-bot-is-4x-low-5x-flat-an.md) — 2026-09-10
- [The 2x was the 10.1.2 bonuses, and Southeast Asia is the third exception](archive/2026-09-10-the-2x-was-the-10-1-2-bonuses-and-southeast-asia-is-the-thir.md) — 2026-09-10
- [Thailand is not a multiplier, and Southeast Asia is priced as the wrong kind of thing](archive/2026-09-10-thailand-is-not-a-multiplier-and-southeast-asia-is-priced-as.md) — 2026-09-10
- [Seed 4015, third pass: the residual question was the real finding](archive/2026-09-10-seed-4015-third-pass-the-residual-question-was-the-real-find.md) — 2026-09-10
- [Price Ops in VP, not VP in Ops -- the fix the invariance points at](archive/2026-09-10-price-ops-in-vp-not-vp-in-ops-the-fix-the-invariance-points.md) — 2026-09-10
- [Per-country adjustments, and the class of card that makes overprotection useless](archive/2026-09-10-per-country-adjustments-and-the-class-of-card-that-makes-ove.md) — 2026-09-10
- [P(SEA scores) is ~0.95; the discount is in the payout, not the odds](archive/2026-09-10-p-sea-scores-is-0-95-the-discount-is-in-the-payout-not-the-o.md) — 2026-09-10
- [One source of truth for what winning is worth](archive/2026-09-10-one-source-of-truth-for-what-winning-is-worth.md) — 2026-09-10
- [Measured: the bot prefers an inert point in a 40-Ops war to an empty Battleground](archive/2026-09-10-measured-the-bot-prefers-an-inert-point-in-a-40-ops-war-to-a.md) — 2026-09-10
- [Improving DEFCON is worth about an Op, and the bot prices it at zero](archive/2026-09-10-improving-defcon-is-worth-about-an-op-and-the-bot-prices-it.md) — 2026-09-10
- [Four answers, two of which are predictions about the forward search](archive/2026-09-10-four-answers-two-of-which-are-predictions-about-the-forward.md) — 2026-09-10
- [Forced defensive spend, and why Europe is not like the other regions](archive/2026-09-10-forced-defensive-spend-and-why-europe-is-not-like-the-other.md) — 2026-09-10
- [Europe Control is priced as a scoring, not a win -- and the U-shape is already there](archive/2026-09-10-europe-control-is-priced-as-a-scoring-not-a-win-and-the-u-sh.md) — 2026-09-10
- [Correction: urgency is already right; the VP function is the only wrong part](archive/2026-09-10-correction-urgency-is-already-right-the-vp-function-is-the-o.md) — 2026-09-10
- [Correction: those points are not inert, they are cheapest-possible breaks](archive/2026-09-10-correction-those-points-are-not-inert-they-are-cheapest-poss.md) — 2026-09-10
- [Correction: the turn-10 worst card is about one Op, not eight](archive/2026-09-10-correction-the-turn-10-worst-card-is-about-one-op-not-eight.md) — 2026-09-10
- [Correction: the three prices are functions, and the bug is the fixed multipliers](archive/2026-09-10-correction-the-three-prices-are-functions-and-the-bug-is-the.md) — 2026-09-10
- [Correction: the break exchange is n : n-1, not 2:1](archive/2026-09-10-correction-the-break-exchange-is-n-n-1-not-2-1.md) — 2026-09-10
- [Correction: playing The China Card costs *more* than holding it, and it decays](archive/2026-09-10-correction-playing-the-china-card-costs-more-than-holding-it.md) — 2026-09-10
- [Correction: improving DEFCON is usually a gift to the *opponent*](archive/2026-09-10-correction-improving-defcon-is-usually-a-gift-to-the-opponen.md) — 2026-09-10
- [Correction: Aldrich Ames is not an exit, because the opponent chooses](archive/2026-09-10-correction-aldrich-ames-is-not-an-exit-because-the-opponent.md) — 2026-09-10
- [Control efficiency reproduces the bot's order, not the expert's](archive/2026-09-10-control-efficiency-reproduces-the-bot-s-order-not-the-expert.md) — 2026-09-10
- [Aldrich Ames is already right; Five Year Plan's whole risk is unpriced](archive/2026-09-10-aldrich-ames-is-already-right-five-year-plan-s-whole-risk-is.md) — 2026-09-10
- [A country's value is three terms, and a wipe destroys only one of them](archive/2026-09-10-a-country-s-value-is-three-terms-and-a-wipe-destroys-only-on.md) — 2026-09-10
- [2026-09-10 — The bugs this repo actually gets, and what would stop them](archive/2026-09-10-the-bugs-this-repo-actually-gets-and-what-would-stop-them.md) — 2026-09-10
- [2026-09-10 — MCTS does not replicate, and Military Ops needed a discount](archive/2026-09-10-mcts-does-not-replicate-and-military-ops-needed-a-discount.md) — 2026-09-10
- [2026-09-09 — Two claims I got wrong before measuring them](archive/2026-09-09-two-claims-i-got-wrong-before-measuring-them.md) — 2026-09-09
- [2026-09-09 — The scoring horizon, and why the old weights were near a ceiling](archive/2026-09-09-the-scoring-horizon-and-why-the-old-weights-were-near-a-ceil.md) — 2026-09-09
- [2026-09-09 — The rest of Codex's list, and what the gate said](archive/2026-09-09-the-rest-of-codex-s-list-and-what-the-gate-said.md) — 2026-09-09
- [2026-09-09 — The pure-function extraction, and the bug that forced it](archive/2026-09-09-the-pure-function-extraction-and-the-bug-that-forced-it.md) — 2026-09-09
- [2026-09-09 — The gate compared a change against itself](archive/2026-09-09-the-gate-compared-a-change-against-itself.md) — 2026-09-09
- [2026-09-09 — One scoring implementation, and the overrides the bot could not see](archive/2026-09-09-one-scoring-implementation-and-the-overrides-the-bot-could-n.md) — 2026-09-09
- [2026-09-09 (overnight) — Green baseline, and the slowdown is real but not attributed](archive/2026-09-09-green-baseline-and-the-slowdown-is-real-but-not-attributed.md) — 2026-09-09
- [2026-09-09 (night) — Audit: the gate, the bot's speed, its strength, and what is off those three lists](archive/2026-09-09-audit-the-gate-the-bot-s-speed-its-strength-and-what-is-off.md) — 2026-09-09
- [Where this stands: one failing test, one uncommitted slice](where-this-stands-one-failing-test-one-uncommitted-slice.md)
- [What is still open, roughly in order](what-is-still-open-roughly-in-order.md)
- [VP in Ops (the largest miscalibration found so far)](vp-in-ops-the-largest-miscalibration-found-so-far.md)
- [US opening setups: the math (opening board, seed 4000)](us-opening-setups-the-math-opening-board-seed-4000.md)
- [Turn-1 review (seed 4004, and the opening board)](turn-1-review-seed-4004-and-the-opening-board.md)
- [The value function's terms, and which to keep](the-value-function-s-terms-and-which-to-keep.md)
- [The point of the game](the-point-of-the-game.md)
- [Resolved: the two "nuclear losses" were the gate measuring the working tree](resolved-the-two-nuclear-losses-were-the-gate-measuring-the.md)
- [Principles from strong play](principles-from-strong-play.md)
- [Option C, step 1: the parity corpus](option-c-step-1-the-parity-corpus.md)
- [Option C, step 1: baseline profiles (8ba89db, gate running concurrently)](option-c-step-1-baseline-profiles-8ba89db-gate-running-concu.md)
- [MCTS prototype follow-up](mcts-prototype-follow-up.md)
- [How to look at things](how-to-look-at-things.md)
- [For Astra: handoff, 2026-09-08 evening](for-astra-handoff-2026-09-08-evening.md)
- [Early stopping, shadow-validated (2026-09-09)](early-stopping-shadow-validated-2026-09-09.md)
- [Codex's MCTS findings (docs/notes/codex/)](codex-s-mcts-findings-docs-codex-notes-md.md)
- [Astra's corpus review (2026-09-08): what was done](astra-s-corpus-review-2026-09-08-what-was-done.md)
- [Architecture, as of Sept 2026](architecture-as-of-sept-2026.md)
