# Strategic bot math and repeat audit — 2026-09-13

## Revision and scope

- Reviewed `51e4ca44318e22898bfc0a4684659535342bbea9`, fetched from default branch `origin/main` at audit start. Later or unpushed work is excluded.
- Previous audit baseline: `3f9166b15bded06a0d86bf6c53d570871977dbec`.
- Historical tag baseline: `v0.1.0`, peeled to `3c3125431f2979171101cbda07e95f69b65b5ddd`.
- Reviewed the intervening changes, current handoff notes, strategic evaluator/policy, operations and probability arithmetic, benchmark fixes, observation isolation, and new control-odds collector/fitter. This is a focused repeat audit, not another exhaustive engine/card audit.
- No implementation changes, paid model calls, strength tournaments, remote publication, or work on the experiments described as in flight in the handoff.

## Assessment

Two additional, reproduced consistency defects affect the central value calculation. These predate the change window; they are newly identified, not newly introduced. An influence action is not valued as the difference of the same board potential used for events and search leaves. Even with reply modeling disabled, the accumulated value of placements can depend on their order despite an identical final board and fixed evaluation context.

This is not a claim that every heuristic must be a probability, that all tactical action values must telescope, or that the corrected bot necessarily wins more. Reply and tempo terms may legitimately depend on action order. The examples below isolate the raw board-potential calculation before those considerations. Fix the accounting contract before interpreting another fitted coefficient as a strategic discovery.

## New confirmed findings

### M1 — P1: influence deltas omit changes to other countries' access values

Locations: `src/struggler/bots/strategic/policy.py:1059–1146` (`delta`), `evaluator.py:access`, `evaluator.py:dependents`; compare `policy.py:_resolve_sandbox`.

`delta` subtracts and recomputes only the changed country's `country_value`, plus its regional terms. But changing influence there can change access value attached to other holdings: controlling Nigeria consumes Cameroon's access to an uncontrolled Nigeria; establishing another route changes the other routes' redundancy; changing opponent reach changes contested access. Updating the snapshot correctly does not include these missing terms in the returned sum.

The event sandbox already recomputes the affected countries through `_value_dependents`. Thus events and direct influence evaluate the same resulting board differently, even apart from M2.

**Isolated reproduction:** empty turn-1 board, US Cameroon 1, then add US Nigeria 1. Default weights except `reply_model=0`, `region=0`, and the three margin coefficients zero. `delta` returns **13.9502222222**; the full before/after board difference is **8.4435555556**. The missing **−5.5066666667** is the consumed access value carried by Cameroon.

On an initially empty board, the same two final US points give:

| Placement order | Sum of raw deltas | Final board value |
| --- | ---: | ---: |
| Cameroon, Nigeria | 29.1486222222 | 23.6419555556 |
| Nigeria, Cameroon | 23.6419555556 | 23.6419555556 |

These are algebraic probes, not two asserted legal consecutive placements within one Ops action. The single Nigeria placement from Cameroon is reachable; the reverse-order probe demonstrates the potential function's failure to telescope.

**Consequence:** influence planning and coup/realignment estimates can book access creation without its later consumption, and can miss access gained by removing the opponent's last foothold. Event versus Ops comparisons use different accounting.

**Smallest useful correction:** include the before/after country-value differences for all dependencies of the changed country, using the existing dependency helper. Keep reply adjustment separate. Require raw-delta equality with the chosen full potential on first footholds, control transitions, redundant routes, and last-enemy-point removals. Then benchmark the cost and gate strength; do not assume a full-board rescan is necessary.

### M2 — P1: regional VP has incompatible urgency weighting, including a Southeast Asia spillover

Locations: `policy.py:1126,1144`, `evaluator.py:744–758`, `policy.py:_public_event_value` and `_resolve_sandbox`.

`delta` values a regional score change as `region_weight * scoring_weight(changed_country) * region_vp_delta`. Whole-board evaluation and event evaluation use `region_weight * region_vp_delta`, with no regional urgency multiplier.

Moreover, `scoring_weight(Thailand)` includes both Asia Scoring and Southeast Asia Scoring. Multiplying the **whole Asia tier change** by that country weight credits an Asia presence/domination bonus at Southeast Asia's separate scoring horizon. Pakistan gets a different multiplier for the same Asia tier change. This cannot describe one regional potential.

**Reproductions, reply off and access off:**

- Empty turn-1 board, US +2 Iran: raw delta **52.9822222222**, full board difference **47.6666666667**. The gap is `1.3 * 4 VP * (2.0222222222 - 1)`.
- Empty board, USSR +3 Cuba: `delta` **21.9532444444**, actual Fidel sandbox event **22.9897777778**. Fidel produces the same influence change, with no VP or military-Ops change in this fixture.
- US controls Thailand and Pakistan by adding two points to each: Thailand then Pakistan accumulates **118.5570666667**; Pakistan then Thailand **116.5602666667**. Both final boards evaluate to **109.2502222222**. Reply and access are disabled, so neither explains the order dependence.

**Smallest useful correction:** define one regional-potential function and call it from deltas, event evaluation, and whole-board evaluation. If urgency is intended, use Asia's own scoring schedule for Asia's tier/bonuses, and model Southeast Asia's own country payouts separately. Choosing the strength-optimal weighting remains a strategic decision; eliminating contradictory implementations does not.

## Earlier findings, rechecked

| Earlier finding | Status at reviewed SHA |
| --- | --- |
| F1: collector resolves selection rather than actual scoring | Fixed in `3400fc2`; actual scoring hooks and canceled-headline/final-scoring regressions added. |
| F2: access sum is nonmonotonic | Still open; reproduced below. Explicitly unstarted in current handoff. |
| F3: incomplete-pair accounting differs between stopping and acceptance | Fixed in `9068a19`; both use `complete_pairs`, rejecting duplicate seats and excluding singletons. |
| F4: stalled runs silently succeed | Core issue fixed in `5a6f99c`: exit 6 and persistent incomplete metadata; zero timeout corrected. Known follow-up remains: one arm's stall stamps complete other-arm reports as stalled. Handoff already identifies an uncommitted fix; not a new finding. |
| F5: reply after the last possible opponent action | Still open in `main`; `_after_reply` has no response-horizon guard. Handoff places fix on an experiment branch. |
| F6: Our Man in Tehran blind choice | Still open in `main`; hidden queue is not supplied to the choosing seat. Handoff reports in-flight work. |
| F7: context mutation and ordinary payload `\|=` | Fixed in `734a7cb`; decision context copied/frozen and `__ior__` refused, with regression coverage. Physical CHANCE option-history gap also addressed. |
| F8: harvesting accepts almost no held-out evidence | Still open in `main`; verdict still depends on mean error among successful answers. Handoff reports in-flight work. |
| Q1/Q2: illegal reply reach and retake Ops overcount | Still open; reproduced on this SHA. Handoff places fixes on an experiment branch. |

**F2 math:** if each of `k` routes receives `(1-p)^(k-1)`, total is `k*(1-p)^(k-1)`, not `1-(1-p)^k`. Isolating Nigeria with urgency 1 and other target urgencies 0 gives **5.000000**, **5.765395**, **4.985967** for US holdings in Cameroon, then Ivory Coast, then Saharan States. The third route lowers the aggregate below one route. For the stated independent-route model, a first-route-normalized aggregate is `[1-(1-p)^k]/p`; symmetric per-route allocation divides that aggregate by `k`. Independence itself remains unproven.

**Q1:** empty board except US Angola 1, US +1 Zaire, fixed reply budget 4: raw **21.512711**, adjusted **−23.843867**, although USSR lacks placement access.

**Q2:** empty board except USSR Angola 1, US +1 Zaire, fixed reply budget 3: raw and adjusted both **26.046533**. The reply actually needs 3 Ops, two for its first point and one after control breaks, but the model charges 4 and declines to apply it.

## Mathematical judgments and limits

- Conversion and retention are different conditional probabilities. `P(control next scoring | currently only reachable)` is not a per-turn decay and cannot simply replace a temporal discount. Even a two-state model needs acquisition and retention: `P(own next) = retention * P(own now) + acquisition * (1-P(own now))`; three control states and unequal horizons need more care. The new collector is useful, but its horizon index does not make time homogeneous.
- The fitter excludes games ending before scoring and reports that censoring. Its target is therefore control **conditional on that scoring occurring**. Combining it with a scoring-probability term requires matching conditioning, rather than assuming independence. This is a modeling requirement, not a newly reproduced implementation defect.
- `ops_value` is documented as concave, but discrete control/tier thresholds do not mathematically guarantee concavity. Treat concavity as a hypothesis; do not build normalization or fitting that requires it without checking observed scales.
- Coup die averaging, realignment outcome aggregation, Space Race success weighting, and seat signs were inspected. No additional confirmed defect is reported in those arithmetic paths. This is not proof of complete tactical or card correctness.

## Reproduction recipe for M1/M2

Run from this checkout with `uv run python`, using this setup; each probe starts from a fresh engine and keeps the turn/context fixed:

```python
from dataclasses import replace
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import Engine, Side

def setup(**weights):
    e = Engine(seed=1)
    for inf in e.board.influence.values():
        inf.update(US=0, USSR=0)
    b = StrategicPlayer(replace(StrategicWeights(), reply_model=0, **weights))
    return e, b

e, b = setup(region=0, margin_presence=0,
             margin_battleground=0, margin_country=0)
e.board.influence['Cameroon']['US'] = 1
obs = e.observe(Side.US)
b.prepare(obs)
before = b.value(b.board, Side.US)
raw = b.delta(obs, 'Nigeria', own=1)
b._add_influence('Nigeria', Side.US, 1)
print(raw, b.value(b.board, Side.US) - before)

for order in [('Thailand', 'Pakistan'), ('Pakistan', 'Thailand')]:
    e, b = setup(access=0)
    total = 0
    for cid in order:
        obs = e.observe(Side.US)
        b.prepare(obs)
        total += b.delta(obs, cid, own=2)
        e.board.influence[cid]['US'] += 2
    print(order, total, b.evaluate(e.observe(Side.US)))
```

## Validation

Full existing suite: `uv run --extra test pytest -q`: **796 passed, 4 skipped, 2 xfailed, 1 failed**. The failure is `tests/test_process_checks.py::test_a_monitoring_loop_is_not_a_gate`: `FileNotFoundError` reading `/proc/217/cmdline`, before its matcher runs. An independent environment probe returned Python PID 8 while `/proc/self/status` reported PID 7884; its live child had PID 9 but `/proc/9/cmdline` did not exist. This reproduces the PID-namespace limitation identified in the previous audit, not a newly established bot failure. The suite is not reported as fully green.

The passing suite includes the added collector, complete-pair, stall, observation-isolation, and Blockade helper-chain regressions, plus evaluator, scale/order, replay, and parity checks. Standalone probes above ran against this checkout's editable install and reproduced all quoted numeric examples. No strength claim follows from these checks.

## Recommended order

### Priorities beyond mathematical consistency

The highest-priority non-math correction is the **response model's legal and temporal boundary**: it must not discount a move for an opponent placement that is unreachable, prohibited, or occurs after the relevant payout. Q1 and F5 are tactical correctness defects in the main policy, not requests for a deeper search architecture. Complete the in-flight reply-fixes branch, pin legal reach and the final-action/extra-round cases, and verify what actually merged before starting duplicate work. Q2's changing placement cost belongs in the same patch, though it is arithmetic.

Next, **finish the benchmark stall follow-up**. The dangerous silent-success case is fixed, but the current writer can mark a fully completed sample as stalled because another sample stalled; the reader then rejects it. Scope status to the report's own unfinished games and retain the incomplete-run veto. This is an experiment-reliability fix, already in flight, not evidence that earlier fully completed games are invalid.

**Our Man in Tehran's missing private reveal** is the next bounded engine/API fix. Give the US the information the event entitles it to, hide it from the USSR/shared history, and make the bot's keep/discard decision use that information. It is a real correctness bug with narrower frequency than the reply defect, so P2 rather than a repository-wide emergency. The current handoff reports implementation in flight.

**Harvest validation coverage** must be fixed before harvested valuations influence weights or become reference data. Require adequate successful held-out coverage and finite results; one exact answer plus 18 failures must not certify a model as usable. This is a blocker for that workflow, not the currently executing strategic bot.

After these, opponent coup replies and a shallow hand planner are plausible strength improvements, not mandatory fixes established by this audit. Test each against the existing policy. No additional verified P1 engine defect is asserted merely to lengthen the queue, and no broad rewrite is recommended.

### Work sequence

1. Finish the already-started reply legality/cost/horizon fixes; avoid duplicating work in the handoff.
2. Establish the shared board-potential contract and fix M1/M2 with before/after and order-invariance regressions on raw deltas.
3. Fix F2's aggregate and only then recalibrate access/retention under the intended probability model.
4. Measure paired-seat strength and runtime separately. A corrected mathematical model may need retuning because existing weights can compensate for old accounting errors.
