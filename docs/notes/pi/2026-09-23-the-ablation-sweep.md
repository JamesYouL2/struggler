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

## Phase 2 reads: run 35978271735 (read 2026-09-24)

1152 pooled games a pair (shared 1149-1151; ten shard jobs failed mid-run
and the wave machinery re-covered every arm to 9 ok shards). Rule applied
as written above, before the number:

| point | paired (point - grid-base) | branch | verdict |
| --- | --- | --- | --- |
| `scoring_final` 0.5 | **+0.027** [+0.008, +0.046] | LB > 0 | beats the shipped 1.0; **nominated for a change gate** |
| `scoring_final` 2.0 | **+0.023** [+0.004, +0.043] | LB > 0 | also beats 1.0; **nominated too** |
| `military` 2.0 | **+0.026** [+0.007, +0.045] | LB > 0 | beats the shipped 1.0; **nominated** |
| `military` 0.5 | +0.007 [-0.010, +0.025] | covers 0 | no move |
| `region` 2.6 | **+0.031** [+0.011, +0.052] | LB > 0 | beats the shipped 1.3; **nominated** |
| `region` 0.65 | -0.015 [-0.036, +0.006] | covers 0 | no move |
| `progress` 1.4 | -0.028 [-0.049, -0.006] | UB < 0 | worse: 2.8 stands against it |
| `progress` 5.6 | -0.014 [-0.036, +0.007] | covers 0 | no move: **2.8 is the peak of the bracket** |
| `vp_base` 0.35 | -0.015 [-0.034, +0.004] | covers 0 | no move |
| `vp_base` 0.75 | +0.001 [-0.019, +0.022] | covers 0 | no move: **the expert 0.5 stands, its first measured support** |

### The tie-break's rule, written before the number (2026-09-24)

The rule gap below gets THREE arms, not two, on a fresh block
(`98000-93023` + held `99500-99627`, reserve `99700-99717` -- the tail
reserve's first use), anchor `bc5ef93`, paired:
`scoring-final-tb-base` (1.0, the shipped value), `scoring-final-tb-05`,
`scoring-final-tb-20`. Three arms because the U-shape -- 1.0 worse than
BOTH neighbours -- is phase-2's most surprising claim, three of ten
cleared points is the false-positive arithmetic, and the first question
is whether the U replicates at all. Read in this order:

1. For each of 0.5 and 2.0 against base: LB above 0 means that beat
   replicates.
2. Exactly one replicates -> that value goes to the change gate.
3. Both replicate -> **0.5** goes to the gate, UNLESS the fresh block
   reads 2.0's paired diff strictly higher while 0.5's covers 0 (the
   one-clearance case again).
4. Neither replicates -> the U was the phase-2 block's noise:
   `scoring_final` stays 1.0, the nomination is withdrawn, and the two
   clearances join the false-positive arithmetic.

The 2.0-vs-0.5 ordering is only ever a difference of paired reads on one
block; the fallback in (3) is CONVENTION -- minimum effective dose, and
the larger phase-2 estimate -- not measurement, and it says so.

### What the rule does NOT decide, said now rather than invented later

`scoring_final` cleared at BOTH points -- 0.5 and 2.0, on opposite sides
of the shipped 1.0. The rule nominates each point individually ("LB
above 0 -> that value beats the shipped one") but orders nothing between
TWO clearing points, and their intervals overlap (+0.027 vs +0.023, not
measured apart). Both cannot ship; the frozen text cannot pick. The
honest reading: **1.0 is measured worse than both of its neighbours** --
not a smooth optimum, and possibly one true point and one near-miss
(both lower bounds clear zero by 0.008 and 0.004). The deciding
measurement is one arm -- 0.5 against 2.0 directly, paired -- with its
rule written first. It is an experiment, not a gate, and it is the only
thing that can say which value a change gate carries.

### The nominations (a change gate each -- the maintainer's call)

Three defaults face a gate, and they are coherent as a direction: the
value terms are UNDER-weighted as shipped. `region` 2.6 (+0.031) with
phase 1's removal at -0.040 says the term matters and 1.3 is too small;
`military` 2.0 (+0.026) says the rule-exact 1.0 is too small (2.0 sat
here once, before the rescale flattened it); `scoring_final` says its
price is wrong somewhere -- which side is the tie-break's question.
`progress` and `vp_base` are the two brackets whose shipped values are
the peak: nothing to gate there.

What none of this settles: every nomination is ONE block's paired read
at the lower edge of its interval (lower bounds +0.004 to +0.011), and
three clearances out of ten points is about what one false positive per
twenty predicts. "Beats the shipped value" here means exactly that --
the gate is what turns a nomination into a default.

### Closed by the gates (2026-09-24)

Both gated nominations were ACCEPTED and merged, sequentially so the
second gate measured the marginal on top of the first:

- `region` 1.3 -> 2.6 -- PR #50, gate run 36032056574: ACCEPTED
  (0.547 +/- 0.039 over 75, curtailed; no WARN), merged `a55fa4a`.
- `military` 1.0 -> 2.0 -- PR #51, gate run 36045490201: ACCEPTED
  (0.540 +/- 0.034 over 75; no WARN), merged `e1994cf` on top of it.

"ACCEPTED" means not measurably worse on fresh gate seeds; the strength
case is the phase-2 grid's paired reads, cited in each PR. `scoring_final`
remains open behind its tie-break arm, and the rule gap above is where
its story starts.

## Phase 1 reads: run 35937042894 (read 2026-09-24)

1152 pooled games a pair (shared seeds 1147-1151; every arm pooled 9 ok
shards -- ten shard jobs failed mid-run and the wave machinery re-covered
them). The rule applied as written above, before the number:

| arm | paired (arm - base) | branch | verdict |
| --- | --- | --- | --- |
| `ablate-progress` | **-0.271** [-0.291, -0.250] | (b) | USEFUL, overwhelmingly: presence credit is load-bearing. Phase 2 grids it |
| `ablate-military` | **-0.043** [-0.063, -0.023] | (b) | USEFUL: MilOps at 1 VP/Op earns its keep. Phase 2 grids it |
| `ablate-region` | **-0.040** [-0.060, -0.020] | (b) | USEFUL: the region tier term matters even under the fitted weights. Phase 2 grids it |
| `ablate-vp-swing-flat` | **-0.026** [-0.044, -0.008] | (b) | USEFUL: the curve beats flat; 3.0 stands as tuned (the grid's missing point is now measured) |
| `ablate-scoring-final` | **-0.025** [-0.045, -0.005] | (b) | USEFUL: the final-scoring bucket clears zero where 35306328917's -0.020 [-0.041, +0.001] grazed it. Phase 2 grids it |
| `ablate-access` | -0.011 [-0.032, +0.011] | (c) | deletion candidate: the whole access term is not measurable at 1150 games. Phase 2 (its decay grid) cancelled |
| `ablate-coup-discount` | -0.005 [-0.025, +0.015] | (c) | deletion candidate: 0.9 vs 1.0 not measurable. Phase 2 (its grid) cancelled |
| `ablate-scoring-rival` | +0.006 [-0.014, +0.026] | (c) | deletion candidate: the rival urgency not measurable -- and the point estimate moved sign vs 09-18. Phase 2 (its grid) cancelled |
| `ablate-reply-off` | -0.016 [-0.038, +0.006] | arm context | consistent with its own gate (a strength dead heat at 96 seeds). **No change follows from this alone**; the poke-rate instrument is required before any |

And one read that is not an ablation:

| `ablate-scoring-discount` | +0.000 [+0.000, +0.000] | **INVALID** |

`scoring_discount` is **dead code**. The arm played byte-identical to
base -- same score 0.540, same seats 0.596/0.484, same signed VP, same
nuke split -- because nothing reads the field: `_scoring_weight_uncached`
(policy.py:1762), the scoring term's only consumer, reads
`scoring_hand`, `scoring_rival` and `scoring_final` and says in its own
comment "No residual discount yet: 1.0 is the documented
documented baseline until a measurement asks for one". The shipped
default of 0.8 describes a bot that does not exist; play has run
undiscounted since the value rebuild. The identical rows are stronger
proof than the grep. Second dead default found this sweep after
`reply_ops`.

### The replications against run 35306328917 (the pre-registered question)

The 09-18 reads were on the tiers bot, before the fitted weights, the
margin deletion and vp_swing 3.0. What moved:

| knob | 09-18 (tiers bot) | now (fitted bot) |
| --- | --- | --- |
| access off | -0.038 [-0.061, -0.015] measurable | -0.011 [-0.032, +0.011] covers 0 |
| reply off | -0.056 [-0.079, -0.032] measurable | -0.016 [-0.038, +0.006] covers 0 |
| rival off | -0.025 [-0.046, -0.004] measurable | +0.006 [-0.014, +0.026] covers 0, sign moved |
| final off | -0.020 [-0.041, +0.001] grazed | -0.025 [-0.045, -0.005] now clears |

The pre-registered note said a moved sign would be this sweep's most
interesting result. What happened is broader: **the fitted rebuild
absorbed three of the 09-18 gains** -- access, the reply look-ahead and
rival urgency were measurable on the tiers bot and are inside noise on
the fitted one, where the fitted country weights price much of what they
approximated. The one that moved the other way (final scoring) is the
term the fitted weights do NOT cover -- end-of-game odds are not country
importance. That is a coherent story and it is a story, not a mechanism:
nothing here isolates the interaction.

## Phase 2: the arms and the rule (written before the number)

Survivors only (branch (b) above), the vp_swing grid's shape -- half and
double bracket the shipped value -- plus the vp_base grid the design
queued regardless. Fresh block `95000-96023` + held `97000-97127`,
anchor `bc5ef93`, all paired against `grid-base` on identical machinery:

| arm | weights |
| --- | --- |
| `grid-base` | -- (the shipped bot again, on the fresh block) |
| `grid-military-05` / `grid-military-20` | `military` 0.5 / 2.0 |
| `grid-progress-14` / `grid-progress-56` | `progress` 1.4 / 5.6 |
| `grid-region-065` / `grid-region-26` | `region` 0.65 / 2.6 |
| `grid-final-05` / `grid-final-20` | `scoring_final` 0.5 / 2.0 |
| `grid-vp-base-035` / `grid-vp-base-075` | `vp_base` 0.35 / 0.75 (never varied; expert 0.5) |

**The rule, before the number:** each point read paired vs `grid-base`.
LB above 0 -> that value beats the shipped one and the default faces a
change gate at it (gate first). UB below 0 -> that value is worse and the
shipped value stands against it. Covers 0 -> indistinguishable at 1152
and no move. Both points at or below 0 means the shipped value is the
peak of what is measured; both clearing 0 on one side means the bracket
missed the peak and the next question extends that side. A half that
beats full while double loses is a peak below the shipped value and
prices a reduction.

Deliberately NOT in phase 2: `access_decay` (the design queued it
regardless, but `access` itself is now a deletion candidate -- its fate
is the maintainer's and a gate, and a decay grid on a term headed for
deletion measures nothing durable); `scoring_discount` (dead -- no grid
can touch it); `coup_discount` and `scoring_rival` grids (rule (c)
cancelled them). The three deletion candidates -- `access`,
`coup_discount`, `scoring_rival` -- and the two dead defaults --
`scoring_discount`, `reply_ops` -- go to the maintainer: deletion is a
code change and ships through a gate, the region-margin precedent.

## The mechanism gap: SurvivalPrior

Six priors (`unknown_chain_loss`, `opponent_hand_attack`,
`replacement_hazard`, `max_states` are provenance `guess`) live on
`SurvivalPrior`, which `--bot-weights` cannot set -- the registry test
requires arm weights to be `StrategicWeights` fields. The sandbox arm's
precedent (`sandbox-base` by `bot_ref`, run 35614516089's kin) works but
is one arm per value per prior. Phase 3, and it needs either a
`bot_ref`-style arm per setting or an experiments.json schema extension
-- a maintainer decision on which.
