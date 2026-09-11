# 2026-09-09 — Follow-up audit through b375ae5

Read-only audit of the recent engine and evaluator changes. Claude's
early-stopping boundary sweep was explicitly excluded; the concurrent
untracked `scripts/validate_early_stopping.py` was left untouched. Findings
below describe the inspected revision, not any subsequent fixes.

### Findings

1. **High — hand-attack values depend on action enumeration order.**
   `StrategicPlayer.event_value` prevents infinite recursion with
   `_events_in_progress`, but cached results retain whichever shallow
   estimate broke the cycle first. In a turn-6, action-round-3 US position
   at DEFCON 5, with Ask Not, Aldrich Ames Remix, Marshall Plan and
   Decolonization in hand, reversing only the legal-option order changed
   Ask Not from 336.82685 to 263.27137 and Aldrich Ames from -136.07948 to
   -302.42137. Both rankings still chose Ask Not in this fixture; the
   demonstrated defect is the large valuation change, not a proven action
   flip. Use a deterministic, explicitly shallow hand valuation inside
   recursive hand-attack estimates instead of caching traversal-dependent
   results. Add a regression that permutes legal options.

2. **High — `evaluate()` leaks scoring flags into its caller.**
   `prepare()` changes `_scoring_flags` and `_coup_bans`, but `evaluate()`
   restores only the observation, urgency, selected caches and influence.
   Reproduction: prepare an otherwise empty board with US control of Taiwan
   (3 influence), evaluate a leaf with `formosan_resolution=True`, then
   inspect the restored position without that effect. Its observation has
   no effect, but `_scoring_flags` is still `(True, False)`; its value changes
   from 25.15609375 to 26.45609375. Restore the complete evaluation context,
   including both flag sets, and test the restoration across differing
   effects as well as differing influence.

3. **Medium — Star Wars maximizes values from the wrong seat.**
   `_hand_attack_value` evaluates the retrieved events from the current
   player's perspective, takes their maximum and clamps it at zero before
   converting for the beneficiary. With the US ahead in space and Marshall
   Plan available in the discard pile, Star Wars values at +50.39304 from
   the US seat but zero from the USSR seat, despite Marshall Plan itself
   valuing at -100.78609 for the USSR. The US chooses the retrieved event
   regardless of who played Star Wars. Optimize from the beneficiary's
   perspective, then convert back to the evaluating seat. The calibrated
   beneficiary discount need not be symmetric, but it does not justify zero
   opponent harm here.

4. **Medium — new hand-event estimates ignore public eligibility.**
   The hand-attack dispatch bypasses the engine event prerequisites.
   Reproductions on turn-8 positions: Star Wars with neither side ahead in
   space has engine eligibility false but estimated value +50.39304; Our
   Man in Tehran with no US-controlled Middle Eastern country has
   eligibility false but estimated value +25.50513. These events have no
   effect in those positions. Reuse authoritative eligibility checks before
   applying the estimates, and test inactive as well as active events.

5. **High, previously reported — final scoring still stops at +/-20 VP.**
   `Engine._finish_game` still uses the immediate-victory VP updater between
   regions. The previously reproduced position starts at US +19, with US
   control of Italy and USSR control of all non-European countries: the
   engine awards US victory at +23 after Europe, although the full regional
   total is -37 and the USSR should win. All regions must be counted before
   deciding the VP winner; Europe control remains an automatic victory.
   See [GMT rule 10.3.2](https://www.gmtgames.com/living_rules/TSRules2nd.pdf).
   The existing test that expects a `vp` ending partway through final
   scoring preserves the defect and needs correction too.

### Progress, scope and verification

The opponent-nuclear-loss attribution fix and winning non-phasing coup fix
address concrete earlier problems. The revised cap and stopping-boundary
calibration were left to Claude's sweep; this audit makes no new claim
about their calibration.

Ran `.venv/bin/python -m pytest tests/test_strategic.py tests/test_events.py
tests/test_engine.py tests/test_evaluator.py tests/test_rollout.py -q
--durations=5`: **263 passed in 9.12 seconds**. The separate reproductions
above expose gaps in that coverage. Neither the full corpus nor the
strength gate was rerun. No implementation changes were made in this audit
or its documentation update.

Priority: final scoring, recursive valuation determinism, complete context
restoration, then beneficiary perspective and eligibility checks.
