# 2026-09-17 — Potential-delta rewrite: the design (draft, pre-gate)

The next model slice after the factor-2 consumer: the ranking path moves
from "region VP now x urgency + margin partial credit" to a whole-board
potential, per the rebuild README's raw-action-delta contract:

    raw_action_delta = potential(after) - potential(before)

## What it replaces, and where the seams are

`evaluator.board_value` has three terms -- the per-country aggregate
(country_value = importance x urgency, progress/guard/access), the shared
region term `ev.region_potential(t, w, urgency, nets)` (Codex M2's one
rule, called from `board_value`, `StrategicPlayer.delta` and the event
sandbox), and `margin_basis` partial credit. The candidate replaces:

- the region term: `region VP now x region_urgency` ->
  `sum over opportunities: mass x E[payout at e]` (forecast-backed,
  overrides threaded as today);
- the margin term: DELETED -- its job was smoothing the 0/1 control step
  toward the next scoring, and the fitted forecast already carries that
  drift continuously (a half-influenced country reads through
  `p_control_at_scoring`'s Ops-cost feature);
- the per-country aggregate: importance stays (tier x urgency) so the
  progress/guard/access terms keep their structure, but urgency becomes
  the masses we shipped in 5cf67af and the per-country VP amounts are
  later work (factor 1 at par), NOT this slice.

## The performance shape

The DP is not free; `delta` runs per candidate placement per action
round. The potential after a one-country placement differs from before
ONLY through: (a) the changed country's member triple in its own region's
forecasts, (b) reach flips at immediate neighbours, which enter the fit's
reach feature, (c) any override whose premise is the changed control.
So the candidate caches per (region, horizon, overrides) and invalidates
exactly the regions containing the changed country or its neighbours --
the same neighbourhood `ev.others_moved_by` already walks. Targets: the
forecast dots are 12-parameter sigmoids (cheap), the DP is the cost; the
parity suite's pole (test_parity_corpus, 385 records) is the runtime
thermometer, and the gate's wall clock checks the per-game total.

## What does not change

Banked VP accounting, access/progress/guard terms, defcon planner,
opponent models, the sandbox's event pricing machinery. reply/tempo stay
separate per the README. scoring_final stays only on bucket 5.

## Gate strategy

This slice hands the gate an integrated WORTH relation for the first
time: placement deltas will change value functionally, not just through
the urgency scale. Expect the corpus to move (recapture follows the
slice) and the strength expectation is genuinely unknown -- that is the
step the plan has been saving.
