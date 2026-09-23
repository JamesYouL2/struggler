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
