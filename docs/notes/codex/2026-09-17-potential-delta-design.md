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

READINGS after the descope (2026-09-17 evening): the per-member-removed
DP is piece one (`1f1f8ef`): `forecast.tier_e_minus`/`tier_e_from_minus`.
Exact to 1e-9 vs the full DP for EVERY member; the single-member
reconvolve measures ~2.96 ms at Europe (full walk ~23 ms). That fixes
the per-delta tier-E cost IF the minus state is cached per
(region, horizon, member) keyed on the OTHER members' features -- but the
wiring lesson before the slice: reach flips at the trial country's
neighbours make the others' feature state move WITH the candidate, so a
plain whole-feature content key never hits across candidates. The shape
that works: the minus state cached per (region, h, member) with the
OTHERS' key stable across candidates of one ranking, plus E(before) from
the base's full DP (cache-hot). Per-delta target ~6-15 ms (own region +
reached-neighbour regions), then the wall-clock discipline decides
whether more is needed before the re-wiring lands.

## Viability verdict (2026-09-17, piece 1 landed, wiring paused)

Even at the improved per-delta cost, the re-wiring is NOT viable in pure
Python, and the arithmetic is the record:

- The delta fan-out is not one call per candidate: `_investment` probes
  1..4 point counts per candidate, and the half-action-round reply model
  (reply_model=3) re-prices a break through `_after_reply`/`_coup_reply`,
  each a further `delta` -- realistically 10-60 `delta` calls per
  candidate, ~10-20 candidates per ranking, every one paying 6-30 ms of
  DP-and-reconvolve work.
- That is ~0.2-1.5 s per action-round ranking, ~40-120 s per GAME on top
  of the ~21 s baseline the shipped bot already spends -- a 150-seed gate
  goes from ~50 min to ~15-100 h per arm. No gate survives that.
- The incremental shave only buys ~2-4x per candidate (the minus DP is
  itself ~15-23 ms and a candidate's neighbours' reach moves with the
  trial), so "the incremental DP makes full games finish" is FALSE at
  the ranking-path fan-out; only a ~1 ms per-region-horizon potential
  cost is compatible with the gate's wall clock.

So the buy-back's remaining options are (1) the native/fast tier kernel
(docs/RUST_PORT_PLAN.md -- an exactness-portable kernel would receive
`tier_e_minus`'s state and `tier_of` as-is), or (2) staying descoped:
the potential remains `scoring_potential`'s diagnostic, the bot's ranks
the pre-rebuild shape, and the factor-2 masses' measured 0.543 remains
the shipped strength. No further wiring lands until the maintainer picks
-- the descoped tree is the correct resting state for the branch.

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
