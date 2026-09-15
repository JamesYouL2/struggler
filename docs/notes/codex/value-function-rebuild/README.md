# Value-function rebuild

The next development priority is a coherent expected-VP value function for the default strategic bot. MCTS work is outside this plan.

This is a proposed implementation contract, not a completed change or a claim of improved playing strength. It is based on the repository reviewed at `bfaa229e91e36fe69b5b3fd32f266cca52789352` on September 15, 2026. Preserve the current bot as the comparison baseline. Develop the components on one rebuild branch and evaluate the integrated candidate before proposing it for main.

## Why rebuild

The recent fixes made influence deltas, event sandboxes, and whole-board evaluation agree more closely. Preserve that accounting contract. The remaining problem is what the potential represents:

- Country importance still includes guessed board-unit weights alongside actual regional scoring.
- The scoring schedule conflates scoring this turn with scoring later in the same deck cycle and cannot represent every later cycle.
- Most scheduled scorings lack an explicit probability of occurring before the game ends.
- Control uncertainty and temporal discount do overlapping work.
- `vp_value` is defined as a fixed multiple of `ops_value(1)`, so changing the board's Ops value cannot independently change that exchange rate.

Further weight tuning can compensate for these assumptions without resolving them.

## Target value function

From one seat's perspective:

```text
V(state) = signed banked VP
         + sum over future scoring opportunities e:
             P(e occurs | state)
             * discount(time of e)
             * E[signed scoring VP at e | state, e occurs]
```

This expresses value × probability × turn discount with explicit meanings:

- **Value:** the scoring payout under the rules, averaged over forecast future positions.
- **Occurrence probability:** whether that scoring opportunity happens before the game ends.
- **Control uncertainty:** which side controls the countries when scoring occurs, inside the expected payout.
- **Residual time discount:** any deliberate preference for nearer payouts that remains after those uncertainties are modeled.

All quantities added to banked VP must be in VP units. The discount is dimensionless. If a scoring opportunity has materially different possible times, sum over those times rather than silently substitute a mean time into a nonlinear discount.

Terminal wins and losses remain explicit outcomes; expected VP must not override a certain win or defeat. Europe control and other immediate-win rules need explicit terminal treatment rather than an arbitrary ordinary VP price. This formula is the board/scoring foundation, not a claim that space abilities, hand options, and every persistent event already have a complete valuation.

## Count regional value once

The per-scoring payout has three parts:

1. Battleground bonuses.
2. Enemy-superpower adjacency bonuses.
3. Regional presence, domination, or control tiers.

The first two are additive across countries, subject to the applicable scoring rules and modifiers. Regional tiers are joint outcomes: several countries can together enable the same domination bonus. Assigning each country's full marginal tier swing to that country and then summing can count one bonus multiple times.

Compute the expected payout once per region and scoring opportunity. Derive an action's board value by subtracting the whole potential before the action from the potential after it:

```text
raw_action_delta = potential(after) - potential(before)
```

Retain this contract for placements, influence removal, coups, realignments, and event board changes. Explicit reply or tempo adjustments may depend on the action sequence; keep them separate from the raw potential. Banked VP changes must be added exactly once.

Non-battleground countries must remain in the regional calculation: they affect presence, country-count requirements for domination, adjacency bonuses, and access. Southeast Asia Scoring has its own payout and timing; it must not multiply Asia's tier payout.

## First concrete deliverable

Implement and document one region's expected-scoring calculation before extending it across the map or integrating the complete schedule. Africa is a useful initial case because it exercises battlegrounds, non-battlegrounds, and tier thresholds without superpower adjacency or Europe's automatic victory.

The component should accept a position, seat, and scoring horizon/context, and return a signed expected payout in VP with a breakdown of country bonuses and regional tier contributions. Keep the forecast separate from the rules payout so each can be checked independently.

For an immediate scoring, bypass the future forecast and reproduce the engine's actual payout. For a future scoring, represent US, USSR, and uncontrolled outcomes and document how the regional approximation handles their joint distribution.

The first implementation must answer:

- How does partial influence affect control probability?
- How do legal access, pointwise Ops-to-control cost, and overprotection affect it?
- How does the forecast change with the scoring horizon?
- How are regional tiers computed without counting them separately for every country?
- What correlation assumptions does that computation make?

## Dependency order within one rebuild

| Component | Deliverable |
| --- | --- |
| Scoring schedule | Represent this turn, later before reshuffle, later deck cycles, and final scoring, with explicit timing and occurrence mass. Treat these as reporting categories; do not limit the representation to one date per category. |
| Control forecast | Forecast US / USSR / uncontrolled at each horizon from current influence, access, Ops-to-control costs, and overprotection. |
| Regional payout | Combine expected country bonuses and expected tiers once per region, including non-battlegrounds and applicable modifiers. |
| Common units | Denominate board potential in expected VP; derive Ops value from legal operations' changes to that potential. Update event, direct-VP, and risk comparisons coherently. |
| Residual discount | Start with a clearly specified baseline, then measure whether extra temporal discount helps after uncertainty is explicit. |

The one-region prototype can use supplied horizons while the schedule is developed. These are implementation dependencies, not instructions to ship partially converted models. Preserve the old evaluator and its corpus while building the candidate; generate a separate candidate corpus only after explaining the intended behavioral changes.

## Hardest modeling choice: regional dependence

Per-country control probabilities do not uniquely determine the probability of domination. The outcomes are correlated: a player has a limited Ops budget and usually pursues a regional objective across several countries.

An independence approximation is a possible first implementation, but it is an assumption, not a consequence of the rules. Likewise, applying tier thresholds to expected country counts is not the same as calculating expected tier payout. Choose an explicit approximation, document its limits, and test regional calibration before increasing complexity. No particular forecasting architecture is mandated by this plan.

## Use the existing measurements carefully

The September 13 control-odds fits provide initial evidence, not universal constants. They estimate control conditional on a scoring actually occurring, and the recorded positions and outcomes came from the old policy's games.

- Preserve that conditioning when combining the forecast with scoring-occurrence probability.
- Do not treat a per-scoring conversion rate as a per-turn retention rate.
- Do not multiply a forecast that already includes loss of control by another retention factor charging the same uncertainty.
- Keep the uncontrolled outcome explicit; both seats' probabilities must be mutually consistent.
- Validate on held-out games, not randomly separated rows from the same games.
- Better prediction on old-policy games is not proof of a stronger policy after integration.

A held scoring card is due this turn if the game continues and no effect removes or cancels it. Do not equate that rules deadline with unconditional certainty that its payout occurs before the game ends.

## Acceptance criteria

### Correctness and accounting

- Immediate scoring agrees with the engine for the chosen region and, before full integration, every scoring region and supported modifier.
- Deterministic control forecasts reproduce the corresponding exact board payout.
- US / USSR / uncontrolled probabilities lie in [0, 1] and sum to one per country and horizon.
- Both seats use the correct signed payout; rules-specific asymmetries are retained.
- Battleground, adjacency, and regional tier payouts are each counted once.
- Non-battlegrounds affect the appropriate regional outcomes.
- Raw action deltas equal the full potential difference with context fixed, including changes to neighboring access.
- Reordered raw board changes telescope to the same final potential when the final board and context are identical.
- Already banked VP is never discounted or counted a second time.
- Removed scoring opportunities and opportunities beyond game end contribute zero; one-shot scorings do not recur.
- Immediate terminal outcomes take precedence over nonterminal expected VP.

### Evidence before adoption

- Test forecast calibration on held-out games and report the conditioning and coverage.
- Compare the complete candidate against the frozen current bot with paired seeds and both seats under the project's existing gate policy.
- Report runtime separately from playing strength; measure the cost of regional forecasts on the ranking path.
- Run the full suite and explain candidate ranking changes before replacing reference corpus data.
- A green correctness suite establishes implementation consistency, not improved strength. A strength gate does not waive the accounting requirements above.

## Recommended work order

1. Write the one-region forecast/payout interface and choose the first explicit regional dependence approximation.
2. Build that region's evaluator with exact immediate-scoring and raw-delta checks.
3. Extend the schedule and other regions, preserving one shared VP potential across evaluation paths.
4. Integrate direct VP, Ops, event, and risk pricing in the same units.
5. Evaluate the integrated rebuild; tune residual discount only after its meaning is no longer ambiguous.

Do not reopen the resolved access-accounting, regional-urgency, or reply-legality defects as new tasks. Their regressions are requirements for this rebuild.

## Related notes

- [Previous value × probability × discount proposal](../../claude/2026-09-12-value-times-probability-times-discount.md)
- [Control-odds measurements and fitted forms](../../claude/2026-09-13-control-odds-fits.md)
- [Three-part battleground value and regional smoothing](../2026-09-14-battleground-value-three-terms.md)
- [Accounting contract and September 13 findings](../2026-09-13-strategic-math-followup.md)

This README records the requested development priority; implementation has not started.
