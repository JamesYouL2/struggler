# The ablation sweep: which live variables earn their keep

The question (maintainer, 2026-09-23): every live variable in the bot
should be shown useful and well tuned. This note is the design and the
pre-registered rules, written before any number from the sweep is
visible. The readings land against it and are recorded here when read.

## The inventory, and what is already settled

`StrategicWeights` has 29 fields. Six ship at 0 (the gated-off terms),
and the sweep does not touch them: their verdicts are recorded -- the
region margin deleted (`docs/notes/claude/2026-09-19-delete-the-region-margin.md`),
`hold_option`'s grid read nothing above 0 (run 35753235236),
`hand_assignment`'s gate shut on -0.240 (run 35814771005, and the loss is
a tie-break, `docs/notes/claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md`),
`potential` stopped at +0.021 [-0.000, +0.042] (run 35790097695),
`access_chain` and `europe_curve` are measured-off alternatives.

Already answered at 1024-seed scale and NOT re-asked:

| variable | the answer in hand |
| --- | --- |
| `reserve` | off lost the gate outright (0.328); useful, keep |
| `reply_coup` | off read -0.059 [-0.082, -0.037], run 35306328917; useful |
| `country_vp_scale` | fitted + gated four dispatches: beats the tiers +0.054 [+0.031, +0.078], halves and doubles measurably worse; tuned |
| `vp_swing` | full grid 1.5/2/3/4/5/6, peak at 3.0, run 35539441015; tuned (but see the flat arm below) |
| `last_window_guard` | strength dead heat off (-0.001) but USSR nukes 37 -> 42; kept for behaviour |
| `scoring_hand` | at 1.0 IS the neutral -- the premium already prices at zero |
| `europe_control_vp` | rules-exact 40 VP, bracketed by fitted-eu20/eu60; not a tuning candidate |
| `space_ability_2/4/6/8` | maintainer prices, "priced for correctness, not for strength"; box 8 fires in ~1% of games and no gate at this size can move it. Pre-declared unmeasurable: excluded, and a dead heat here would mean nothing |

Weak evidence only (128 + 64 seeds, the 2026-09-15 nine-arm run
35022058789 -- its own note says "nothing here is significant") is what
the sweep replaces: `access-half` leaned "do not shrink", `progress-half`
and `coup-discount-flat` had halves violently disagreeing,
`scoring-rival-half` was an inconclusive lean, `region-par` read "free,
not better". `scoring_discount` and `military` have **never been varied
at all**.

One inventory finding, recorded before the sweep runs: **`reply_ops` is
dead at the shipped `reply_model` 3** -- `_reply_budgets` reads it only
under model 1 (policy.py:2387). It is model-1 configuration and test
scaffolding, not a live price. Not an ablation target; a simplification
question for the maintainer.

## Correction, 2026-09-24: the prior art the design missed (run 35306328917)

Asked by the maintainer whether any arm is duplicative, the notes turned
up what the registry did not show: **run 35306328917 (2026-09-18) already
read four of these arms at 1024 paired seeds**
(`docs/notes/claude/2026-09-18-drift-located-at-v0.2.1-v0.2.3.md`), and
`progress` was read at 77 seeds. The registry's `*-off-vs-07d553a` arm
contexts were never marked ANSWERED, so the verdicts live only in the
note -- the design above claims "one wide anchored off arm" where a
full-scale paired read existed. Corrected status per arm:

| arm | the prior read | status |
| --- | --- | --- |
| `ablate-access` | access off **-0.038 [-0.061, -0.015]**, 1024 paired | **replication**, not a new question |
| `ablate-reply-off` | reply look-ahead off **-0.056 [-0.079, -0.032]**, 1024 paired | **replication** |
| `ablate-scoring-rival` | rival urgency off **-0.025 [-0.046, -0.004]**, 1024 paired; the 09-17 knob pair (0.25/0.5 monotone) corroborates | **replication** |
| `ablate-scoring-final` | final scoring off **-0.020 [-0.041, +0.001]**, 1024 paired | **replication, and the one worth re-reading**: its upper bound just touched 0, the only ablation in that sweep not clearly measurable |
| `ablate-progress` | progress at 0.01 read **0.354 REJECTED** (removal catastrophic), 77 early-stopped seeds, 2026-09-12 bot | **replication** of a known-strong effect |
| `ablate-coup-discount` | 1.0 read 0.467 [0.428, 0.506] REJECTED at 256 full seeds (run 34747654283) + the deletion gate ACCEPTED at 128 (run 34750946023) -- and "Nobody has read these numbers yet" | **semi-novel**: never 1024 paired; this arm is the definitive version of a muddled record |
| `ablate-scoring-discount` | 0.55 (the OTHER direction) read 0.438 +/- 0.079 and was DROPPED as confounded; 1.0 never run | novel |
| `ablate-military` | never varied | novel |
| `ablate-vp-swing-flat` | 1.0 vs the old 2.0: dead heat at 39-78 seeds (2026-09-12); 1.0 vs 3.0 never run -- the six-point grid's missing point | novel at this contrast |
| `ablate-region` | region at par (1.0) read "free" twice at 128; `fitted-no-region` ran region 0 only under the fitted weights; 0 at shipped weights never run | semi-novel |

Why the replications still have their run (stated before the numbers,
not after): the 1024-seed reads were taken on the 2026-09-18 bot --
**before** the fitted country weights shipped (09-21, the biggest
valuation change here), before the region-margin deletion (09-19) and
before vp_swing's 3.0 restore. Ablations are interactions: "access is
worth +0.038 on the tiers bot" need not hold on the fitted bot. If the
replications agree with 35306328917's signs, the four gains are robust
to the rebuild; if any sign moved, that is the most interesting result
this sweep can produce. The arm-level rules above do not move either way.

And one hazard retired on the same evidence: the 2026-09-11 four-hour
hang that made `progress-001` use 0.01 instead of 0.0 (`access 0.0`
then) is stale -- run 35306328917 played `access: 0.0` through all 81
shards at 1024 seeds. The three 0.0 arms in flight are safe on that
evidence.

Process defect this exposed, worth a gate someday: **an arm whose
context is never marked ANSWERED is invisible to the next dispatch.**
The registry keeps the arms; the verdicts live only in prose notes, and
a design that greps the registry sees "never paired at scale" where a
1024-seed read sits in a note under another tree.

## Phase 1: the arms (usefulness)

One dispatch, eleven arms, paired against `ablate-base` on identical
machinery: seeds `92000-93023` + held `94000-94127` (1152 pooled games,
fresh -- every registry block below 89000 is burned), anchor `bc5ef93`.

| arm | weights | neutral is | prior evidence |
| --- | --- | --- | --- |
| `ablate-base` | -- | the shipped bot | the paired reference |
| `ablate-access` | `access: 0` | the whole reach term off | half read 0.481 at 128+64; off never paired at scale |
| `ablate-region` | `region: 0` | the region tier term off | 1.0 read "free" twice at 128; 0 never run |
| `ablate-progress` | `progress: 0` | partial-control credit off | half split its halves 0.547/0.434 |
| `ablate-scoring-discount` | `scoring_discount: 1.0` | future cycles count as much as this one | never varied |
| `ablate-scoring-rival` | `scoring_rival: 0` | pre-deck-tracking behaviour | 0.5/0.25 leans + a wide off arm |
| `ablate-scoring-final` | `scoring_final: 0` | no final-scoring bucket | one wide anchored arm |
| `ablate-coup-discount` | `coup_discount: 1.0` | no randomness/efficiency discount | halves disagreed 0.516/0.422 |
| `ablate-military` | `military: 0` | MilOps unpriced | never varied |
| `ablate-vp-swing-flat` | `vp_swing: 1.0` | the flat curve 52bb329 had | the grid never included 1.0 on the peak's block |
| `ablate-reply-off` | `reply_model: 0` | the whole reply look-ahead off | shipped on a strength dead heat for behaviour (poke 6.27 -> 0.08) |

**The rule, identical in every arm's `context`, written here before the
number and not moved after it:** read the paired difference arm minus
`ablate-base`, one-sided 95% by seed.

- lower bound **above 0** -- removing the variable helps: it is harmful
  at its shipped setting. The default faces a change gate and phase 2
  becomes a retune, not a tune.
- upper bound **below 0** -- the variable is **useful**. Keep it; phase 2
  prices its grid.
- the interval **covers 0** -- not measurably doing anything at 1152
  games: a deletion candidate by the region-margin precedent (deleted on
  +0.001 [-0.022, +0.024] at 1024), and phase 2 is cancelled for it.

What phase 1 cannot settle, said up front: a dead heat cannot separate
"does nothing" from "does something rarer than this sample can see"
(the `space_ability_8` problem in miniature); and `ablate-reply-off`'s
strength read does not measure the reply layer's actual justification --
behaviour -- so no change to it follows from strength alone, and
`tests/test_poke_rate.py`'s instrument is required before any.

## Phase 2: tuning grids (only for phase-1 survivors)

Separate dispatch, because nothing may depend on an earlier verdict
while unattended -- the arm sets are chosen after the phase-1 reads.
Shape per survivor: current value bracketed by half and double on one
fresh block against a fresh `*-base`, the `vp_swing` grid's shape. Also
queued for phase 2 regardless of phase 1: `access_decay` (1.445 is
measured-derived from one conversion rate; brackets 1.2 / 1.8) and
`vp_base` (expert 0.5, never varied; brackets 0.35 / 0.75).

## The mechanism gap: SurvivalPrior

Six priors (`unknown_chain_loss`, `opponent_hand_attack`,
`replacement_hazard`, `max_states` are provenance `guess`) live on
`SurvivalPrior`, which `--bot-weights` cannot set -- the registry test
requires arm weights to be `StrategicWeights` fields. The sandbox arm's
precedent (`sandbox-base` by `bot_ref`, run 35614516089's kin) works but
is one arm per value per prior. Phase 3, and it needs either a
`bot_ref`-style arm per setting or an experiments.json schema extension
-- a maintainer decision on which.
