# Handoff, 2026-09-18 evening: hand safety landed, fitted weights gating

What happened today, where each piece is, and what is still running.

## Landed on main

- **PR #4, hand safety** (`72a6a0a`). Codex's audit F1-F5 were each
  reproduced and fixed with a test that fails without the fix. It adds
  the last-safe-window guard and `forecast.tier_weights` (the potential's
  exact per-position linear weights). See
  [the v3 plan](2026-09-18-hand-planner-plan-v3.md).
  - Against `07d553a` on fresh seeds 30000-31023: 0.520 [0.503, 0.537],
    where the old main read 0.477 [0.460, 0.494]. The paired gain is
    **+0.043** [+0.032, +0.055].
  - The bot's nuclear losses as the USSR fell from 169 to 37 (of 512).
    Coups per game held.
  - The gate against the parent: ACCEPTED.
- **PR #5, 1024-seed drift** (`e965489`). `drift.yml` turns each anchor
  into an anchored `experiments.yml` arm (sharded into 8 x 128 seeds and
  pooled), then applies the canary's verdict (`scripts/drift_verdict.py`).
  `experiments.yml` is now also `workflow_call`.

## Branches with work not yet on main

| branch | what | state |
| --- | --- | --- |
| `feat/fitted-country-weights` | fitted per-country weights (on by default at 2.795), `europe_control_vp`, `europe_curve`, the fit and audit scripts | PR to open; the gate runs on it |
| `measure/defcon-drop-rate` | `last_window_guard` (the guard as a probability), `scripts/measure_defcon_drop.py` | guard arms running; PR after they report |

## Results in, and what they decided

- **Fitted country weights** ([note](2026-09-18-fitted-country-weights.md)):
  - At the matched scale they beat the guessed tiers, 0.518 [0.502,
    0.534], over 1024 seeds.
  - Half (-0.036) and double (-0.026) are both measurably worse.
  - Removing the region term costs 0.067; it is not double counting.
  - Europe Control at 40 VP beats 20 and 60, by a little on each side.
  - Decided: default flipped to 2.795.
- **The guard's drop probability** (32 self-play games): when the other
  side holds a borrowed Coup, DEFCON 3 falls in the mover's round
  60/140 = 0.43 of the time (US 0.36, USSR 0.60). A legal drop existed
  in every one of 570 rounds at DEFCON 3. The survival prior's 0.15 is
  2-4x too low at DEFCON 3; that is a separate item.
- **The Europe curve cannot be fitted from self-play.** No position came
  near Europe Control, so the exact potential is linear there. k=10 is a
  judgment. Curves do fit the small regions better (Central America R²
  0.62 to 0.72).

## Later the same evening

- **PR #6 (fitted weights) gate: ACCEPTED**, 0.507 +/- 0.036 over 76
  seeds. It waits for the maintainer's merge.
- **Guard arms:** on reproduced PR #4 exactly; off is -0.001 (USSR
  nuclear losses 37 -> 42); 0.43 plays identically to 1.0. PR #4's gain
  was F1-F5. **PR #7** sets the default to the measured 0.43.
- **Europe curve k=10: 0.486 [0.471, 0.501]**, not adopted.
- The drift run was still going at 41/74 shards.

## Still running at the time of writing (check `gh run list`)

| run | what | reads as |
| --- | --- | --- |
| 35374218178 | guard on / off / 0.43 vs 07d553a, paired | `guard-on` must reproduce 0.520 exactly. Off separates the guard from F1-F5. 0.43 is the maintainer's "probability x 40 VP" |
| 35371538598 | 1024-seed drift, all 9 tags, on the PR #4 code | `scripts/drift_verdict.py`: DRIFT if any upper bound < 0.500 |
| 35387907944 | `europe-curve-k10`, fit off | the first dispatch (35368252815) stuck in queued for 3h with no runner; cancelled and re-dispatched |
| the fitted branch's PR gate | fit on by default vs main | the gate verdict |

GitHub runs about 20 jobs at a time for this repo. With ~100 shards
queued, "queued" for hours is capacity, not a fault, unless a job shows
started with no runner (the 35368252815 failure).

## Next

1. When the guard arms report, set `last_window_guard` to the winner and
   open the PR for `measure/defcon-drop-rate`.
2. When the fitted gate reports, merge if accepted (the maintainer
   merges). Then a paired anchored arm against `07d553a`, since a
   parent-only gate missed the drift once.
3. The v3 plan's step 4: the instrument for the first decision that
   closes the last exit, now that F1/F5 make the logs trustworthy.
4. Candidates: a curve for every region (measured to help the small
   ones); the DEFCON-3 survival prior (measured 2-4x too low); the T9
   headline hot spot (25 s for one decision, in the event sandbox).
5. Open for the maintainer: the VP potential's native kernel (the
   per-position weights put a delta at 4 us, but no timed game yet).
