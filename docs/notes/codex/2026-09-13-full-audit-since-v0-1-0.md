# Full repository audit since v0.1.0 — 2026-09-13

## Reviewed revision and scope

- Reviewed HEAD: `3f9166b15bded06a0d86bf6c53d570871977dbec`, verified against `origin/main` on this audit's fetch.
- Baseline: annotated tag `v0.1.0`, peeled commit `3c3125431f2979171101cbda07e95f69b65b5ddd`. The tag object's own SHA is not the source revision.
- Started with the baseline-to-HEAD diff, then followed callers across engine/replay/observations, strategic evaluation and reply planning, MCTS/rollout/DEFCON planning, LLM adapters and schemas, training/benchmarking, calibration scripts, and CI/gate wrappers.
- This is a broad code audit with targeted reproductions and the full existing suite, not a proof of all 110 card implementations or a new strength tournament. No paid API calls or long A/B tournaments were launched. Code and model weights were not changed.

## Assessment

Eight additional actionable findings were confirmed, alongside the two reply defects from the preceding quick audit. The most consequential new problems are in the measurement layer: calibration can count a scoring that never happened; early stopping and acceptance use different sets of observations; and a stalled benchmark can produce an apparently successful, unmarked partial report. These are reasons to repair the instruments before relying on another small tuning result. They do **not** establish that every historical gate result was wrong.

The new access formula also differs mathematically from its stated probability model. More redundant routes can reduce the aggregate access value. That is a concrete implementation/model inconsistency; the best replacement and its effect on playing strength still need measurement.

Priorities below use P1 for issues that can invalidate a central measurement or value-model claim, P2 for bounded correctness/behavior defects, and P3 for a smaller CLI problem.

## New findings

### F1 — P1: access calibration records card selection as scoring resolution

Source: [measure_access_conversion.py:98–120](https://github.com/JamesYouL2/struggler/blob/3f9166b/scripts/measure_access_conversion.py#L98-L120). Added after v0.1.0.

The script determines the region from `action.payload['card']`, steps the engine once, then resolves all outstanding conversion and retention opportunities in that region. A `HEADLINE_PLAY` merely commits a card; the other headline has not been chosen, Defectors may cancel it, and higher-Ops events may still change the board before it scores. Other card-identifying decisions can also name a scoring card without scoring it. Conversely, final scoring has no corresponding card-selection action for each region.

**Reproduction:** use an events-on bare engine at turn 4, US Japan 4 and India 1, USSR hand `['Asia_Scoring']`, US hand `['Defectors']`, and advance to the first headline pick. Run the script's real `play` loop with that engine supplied in place of `new_game` and a first-legal driver, stopping after the two headline decisions. Both steps leave VP at zero and Defectors cancels Asia. Nevertheless, the collector produces:

```text
conversion samples: {2: [False], 3: [False]}
retention samples: {(4, False): [True]}
```

The collector counted two failed conversions and a retained Japan from a scoring that never occurred. These are the measurements cited next to `CONVERSION_P` and the route decay.

**Correction/acceptance:** collect observations at actual region-scoring resolution, including final scoring, with access to control at that instant. Verify canceled headlines add no samples; a higher-Ops headline changing control is reflected in the sample; discarding a scoring card adds no sample; final scoring resolves the appropriate pending opportunities. Recompute conversion/retention figures before treating the current values as calibrated. The magnitude of the bias has not been measured here.

### F2 — P1: the symmetric route formula is nonmonotonic and is not the stated probability sum

Source: [evaluator.py:518–550](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/strategic/evaluator.py#L518-L550). Added after v0.1.0.

Each of k routes is assigned `x ** (1-k)`, yielding total `k * x ** (1-k)`. With `x = 1/(1-p)`, this is `k * (1-p) ** (k-1)`. It is not the normalized geometric sum implied by `P(control) = 1 - (1-p)**k`. The former eventually decreases; the latter increases toward a ceiling.

**Reproduction:** isolate the Nigeria contribution by setting its urgency to 1 and all other countries' urgency to 0. On an otherwise empty board, sum `ev.access` for the US holdings at the listed neighbors, using current default weights:

| Holdings reaching Nigeria | Total access contribution |
| --- | ---: |
| Cameroon | 5.000000 |
| Cameroon, Ivory Coast | 5.765395 |
| Cameroon, Ivory Coast, Saharan States | 4.985967 |

The third route reduces access value below even one route. Other value terms may offset this in a full ranking; this probe isolates the faulty contribution rather than claiming every such placement becomes a bad move overall.

**Correction/acceptance:** if the stated independent-conversion model is intended, calculate a monotonic aggregate such as `[1-(1-p)**k]/p` when the first route is normalized to one, then allocate it symmetrically if the architecture requires per-holding contributions. Account explicitly for home access and influence already in the target. Test monotonicity and saturation before gating playing strength. Symmetry does not require assigning every route the last route's marginal value.

### F3 — P1: early stopping and final acceptance disagree about incomplete seed pairs

Sources: [benchmark.py:1011–1030](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/benchmark.py#L1011-L1030), [seed_scores:477–486](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/benchmark.py#L477-L486), and [reporting:1164–1179](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/benchmark.py#L1164-L1179). Present in the reviewed tree; the stopping machinery itself predates this change window.

`_decided` uses only seeds with two finished games. The main loop stops and saves **all** finished games, including singleton seats. `seed_scores` and `acceptance` then include those singletons. Thus the stopping calculation is predicting a different statistic from the one ultimately reported and gated. Asynchronous completion creates exactly these partial pairs.

**Reproduction:** construct 75 complete seeds, each one win plus one loss, split alternately between two samples. Add 10 one-seat losses for other seeds and set the plan to 50 seeds per sample. Direct calls return:

```text
_decided(...) -> True
acceptance(saved_reports) -> False
pooled score 0.441, SE 0.018, one-sided upper bound 0.470
```

The stopping calculation sees only the 75 tied pairs and predicts acceptance. The saved reports reject. Separately, `acceptance` accepts two synthetic samples totaling 150 winning **US-only** games; it does not enforce the paired-seat design.

**Correction/acceptance:** use one complete-pair definition in stopping, statistics, evidence counts, and acceptance, requiring one US and one USSR game per seed. Either finish already-started pairs or exclude/mark unmatched games consistently. Add the above adversarial partial-pair example and duplicate-seat cases. Do not call curtailment deterministic across machines merely because seeds are deterministic: completion order is also an input to the observed prefix.

### F4 — P1: a stalled benchmark can succeed and lose its incomplete-run status

Source: [benchmark.py:1138–1179](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/benchmark.py#L1138-L1179). Stall handling added after v0.1.0.

After any game completes, a timeout terminates the remaining work, writes results, and falls through with `None`, which means CLI exit 0. The `stopped_after`/`planned_games` fields exist only in the stdout summary. Saved reports rebuild their summaries with `summarize(subset, ...)`, losing those fields and the run configuration. There is no stop-reason field distinguishing a stall from accepted curtailment. Gate/drift consumers cannot reliably identify the censored sample, and acceptance does not veto it.

**Reproduction:** replace only the multiprocessing pool with a deterministic fixture yielding one completed record and then `multiprocessing.TimeoutError`, and call the real benchmark `main` with four planned games:

```text
main return: None (exit 0)
stdout summary: stopped_after=1, planned_games=4
saved report: no stopped_after, planned_games, or stop_reason
```

A stalled game's duration can depend on the candidate and position. Omitting it is not equivalent to observing a neutral result, nor to a justified early-stop verdict.

**Correction/acceptance:** preserve partial results but mark every report with stop reason, planned/completed counts, unfinished jobs/pairs, and bot/weight configuration. Return a distinct nonzero status on a stall and make gate/drift acceptance reject an incomplete run unless an explicit, separately justified policy applies. Test timeout after some completed games, not only timeout before the first result.

**Related P3 CLI defect:** help says `--stall-timeout 0` waits forever, but `results.next(timeout=0)` polls immediately. Actual command:

```bash
uv run python -m struggler.bots.benchmark --bot greedy --opponent greedy \
  --seeds 1 --workers 1 --stall-timeout 0
```

It immediately prints `STALLED: no game finished in 0s` and exits 4. Translate zero to `None` and reject negative values.

### F5 — P2: the reply discount applies after the game's last possible response

Source: [policy.py:_after_reply](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/strategic/policy.py#L1298-L1366). Added after v0.1.0.

The helper checks control and a hypothetical Ops budget, but never whether the opponent gets another move before the outcome being valued. On the final US action in turn 10, repairing control after the US spends its Ops is impossible before final scoring.

**Reproduction:** events-on engine, turn 10, phase `action_rounds`, action round 7, `_ars_played=14`, no extra-round effects, Zaire US 0 / USSR 1, US Angola 1. Begin US 2-Ops influence placement. With fixed reply budget 4:

```text
raw gain for US +1 Zaire: 67.2
_after_reply gain: 6.0
engine after the legal placement: terminal=True, final_scoring_ran=True,
                                 pending_decision=None
```

**Correction/acceptance:** apply a reply only when an opponent response is available before the relevant payout. At minimum cover the final US move, plus reversed play order and extra-action-round effects. Use the actual public turn-order rules; a check for `turn == 10` alone is insufficient. Scoring timing elsewhere is a larger strategic question.

### F6 — P2: Our Man in Tehran gives its owner a blind keep/discard choice

Sources: [events.py:1661–1701](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/engine/events.py#L1661-L1701) and [core.py:observe](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/engine/core.py#L245-L290). Predates v0.1.0; not the documented physical-mode no-op.

Examined cards are stored only in `_our_man_queue`, excluded from every observation. The US receives `keep` and `remove` choices without the card identity. Protecting the opponent's information also removed the information the US needs to perform the event.

**Reproduction:** two otherwise identical events-on engines, seed 123, US Israel 4. Set one draw pile to `['Fidel']` and the other to `['Marshall_Plan']`, then fire Our Man in Tehran. Their hidden queues differ but:

```python
first.observe(Side.US) == second.observe(Side.US)  # True
```

No observation-only player can distinguish these decisions. Existing tests explicitly ensure neither side sees the card, locking in the wrong ownership boundary.

**Correction/acceptance:** add actor-scoped private reveal data for the examined card(s), visible to the US and absent from USSR observations and shared history. Test both positive visibility to the entitled player and negative visibility to the opponent. Keep/discard should depend on the card, not its position in an unseen queue.

### F7 — P2: observation isolation remains mutable through ordinary operations

Sources: [core.py:observe](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/engine/core.py#L245-L272), [types.py:FrozenPayload and Decision](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/engine/types.py#L133-L187). The shared context predates v0.1.0; the incomplete payload freeze is part of the newer isolation fix.

Two independently reproduced paths remain:

1. `Observation.pending_decision` shares the engine's mutable `context`. Begin a 1-Op placement, then assign `obs.pending_decision.context['ops_remaining'] = 99`. After one legal placement the engine offers **98** remaining Ops.
2. `FrozenPayload` overrides assignment/update but not `dict.__ior__`. With `payload = obs.pending_decision.options[0].payload`, `payload |= {'country': 'INVALID'}` changes the engine's own legal option. This uses the normal `|=` operator, not an explicit `dict.__setitem__` bypass.

**Correction/acceptance:** isolate or recursively freeze public decision context and close ordinary payload mutation paths, including `|=`. Preserve JSON/pickle support and do not expose extra hidden data while copying. Add behavioral tests that the original engine budget and legal actions stay unchanged after attempted player-side edits. This is an accidental-mutation API defect, not a claim of an exploited malicious bot.

### F8 — P2: valuation harvesting can certify almost no validation evidence

Source: [harvest_card_valuations.py:164–183](https://github.com/JamesYouL2/struggler/blob/3f9166b/scripts/harvest_card_valuations.py#L164-L183). Added after v0.1.0.

Failed held-out responses are omitted from `errs`, and `USABLE` depends solely on the mean error among successful responses. The printed claim that this is the bot's same tolerance gate is also too strong: `expert_check` counts individual out-of-tolerance rows, whereas the harvester uses an average.

**Reproduction:** run the real script with an injected client that returns the exact expert value for its first held-out card and raises on every subsequent request. No live API used. Output report:

```json
{"mae": 0.0, "within_tolerance": 1, "n": 1, "failed": 18, "verdict": "USABLE"}
```

**Correction/acceptance:** require a defined validation coverage/success floor, finite numeric results, and the intended per-card tolerance or explicitly documented aggregate criterion. Incomplete evidence must not yield `USABLE`. Add failures, nonfinite values, and one very wrong row hidden by many exact rows. Keep proposals separate from the maintainer's reference values. This script has not yet been established as a production valuation source, so this is a pre-use fix.

## Earlier quick-audit findings: both still open

These were reproduced on the same reviewed SHA; they are not counted as new findings above.

### Q1 — P2: reply model credits unreachable influence placement

[policy.py:1341–1353](https://github.com/JamesYouL2/struggler/blob/3f9166b/src/struggler/bots/strategic/policy.py#L1341-L1353) never checks opponent placement reachability. On an empty Zaire and no USSR access, a US point has raw gain **27.973867**, but the fixed-4-Ops reply model returns **−22.467200**. Repair would be illegal. Check reachability and applicable placement prohibitions before charging the response; event-granted US footholds can reach this path too.

### Q2 — P2: retaking a country charges the doubled influence cost for every point

The same code uses `undo = need * cost`, freezing the initial per-point price. At Zaire US 1 / USSR 0, with USSR access from Angola, the real engine retakes control with **3 Ops**: two for the first point, one after control breaks. The model prices it at **4**, and under a fixed 3-Ops reply budget applies no discount at all. Price the sequence with the cost changing after each point. Pin the 3-Ops retake and overprotected variants.

## Other observations and boundaries

- The direct nonacting `observe(side)` hand-option leak is acknowledged in current code as a pending separation between analysis and player views. It was not relabeled as a new discovery here.
- Physical-mode random-discard decisions can retain all candidate card options in shared history because `Decision.public()` exempts CHANCE. Reproduced with a known USSR hand of Fidel/Nasser/Blockade: after Fidel is discarded, the shared event still lists all three. This is an additional bounded privacy gap to consider while fixing F6/F7; standard nonphysical random discards have only the single preselected option and do not have this particular leak.
- Even with F1/F2 fixed, measuring conversion conditional on **any** access does not by itself identify independent per-route conversion probability. Opportunities within a game are correlated. Validate those modeling assumptions before describing the current binomial errors as sufficient calibration evidence.
- The full-game horizon, public optional-card configuration, and card-in-flight accounting deserve broader deck-posterior tests. No new quantified strength conclusion is made from these concerns.
- MCTS remains a sampled hidden-state search with a fixed opponent policy; this review did not find a new independently reproduced MCTS-specific defect. The existing parent evaluator/reply issues still affect it. No claim is made that a language rewrite, a deeper tree, or more simulations will repair these value and measurement errors.
- LLM provider calls were reviewed statically; live SDK/provider compatibility, costs, and model quality were not tested. Existing documented fallback and context-growth limitations remain.
- No blanket refactor is recommended. The largest immediate return is consistent scoring/measurement events and consistent sample accounting, followed by the bounded reply fixes.

## Validation

Full suite on the pinned checkout:

```bash
uv run --extra test pytest -q
```

Result: **769 passed, 4 skipped, 2 xfailed, 1 failed**. The failure was `tests/test_process_checks.py::test_a_monitoring_loop_is_not_a_gate`; rerunning it alone reproduced the same failure.

This container exposes a mismatched PID namespace through `/proc`: an independent probe returned `os.getpid() == 8` while `/proc/self/status` reported PID 17113, and both `/proc/8/cmdline` and the still-running child PID path were absent. The failed test reads `/proc/{proc.pid}/cmdline`, so it fails before exercising its matcher. Treat this as an environment-limited process-monitor check, **not** evidence of a game-engine failure or a fully green suite. No suite rerun with that check silently excluded was used to claim success.

Targeted standalone probes additionally verified F1–F8 and Q1–Q2. Synthetic fixtures were used for asynchronous completion order, injected client failures, and isolation of a single access term; these are correctness probes, not tournament results. The preceding quick pass's 35 focused tests passed but did not catch the two reply defects.

## Recommended work order

1. Fix F3/F4 together: complete-pair accounting, explicit stop reasons, persisted run metadata, and failure status for stalls. These protect all subsequent experiments.
2. Fix F1 and rerun calibration; fix F2 against its intended probability model, then measure playing strength without claiming that correctness alone proves improvement.
3. Fix Q1/Q2/F5 as one small reply-model patch: legal response, incremental cost, and real response horizon.
4. Fix F6/F7 with explicit private/public observation boundaries and mutation tests; include the physical CHANCE-history case.
5. Fix F8 before using harvested valuations. The timeout-zero correction belongs with F4.

Each item is independently reviewable. Implementation changes should carry the focused regression checks described above and follow the repository's existing test/gate policy. This audit changes notes only.
