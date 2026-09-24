# The weights: what each one does, and what it is worth

One scorecard, every variable the bot plays by (maintainer, 2026-09-24:
"notes for each variable, what it does and how valuable it is"). The
semantics live in the field comments in
`bots/strategic/policy.py` and [STRATEGIC_AI.md](../STRATEGIC_AI.md);
the readings live in `models/experiment_ledger.json` (every arm, every
number) and the notes it points at. What this note adds is the third
column: **how much the variable is worth to play**, mostly from the
2026-09-24 ablation sweep's phase 1 (paired removals, 1152 games each,
run 35937042894) and phase 2 (brackets, run 35978271735). Removal cost
is the importance: what the bot loses without it.

## The ranking, by measured cost of removal

| # | variable | now | removal cost (paired) | standing |
| --- | --- | ---: | --- | --- |
| 1 | `progress` | 2.8 | **-0.271** [-0.291, -0.250] | critical; 2.8 is the bracket's peak |
| 2 | `country_vp_scale` | 2.795 | the whole country layer: +0.054 [+0.031, +0.078] vs the deleted tiers | fitted + gated; foundational |
| 3 | `reserve` | 0.35 | off lost its gate outright (0.328) | load-bearing |
| 4 | `military` | **2.0** | -0.043 [-0.063, -0.023] | shipped 2.0 (gate ACCEPTED 2026-09-24) |
| 5 | `region` | **2.6** | -0.040 [-0.060, -0.020] | shipped 2.6 (gate ACCEPTED 2026-09-24) |
| 6 | `reply_model` | 3.0 | -0.016 [-0.038, +0.006] now; -0.056 on the tiers bot | kept for BEHAVIOUR: poke rate 6.27 -> 0.08 |
| 7 | `vp_swing` | 3.0 | -0.026 [-0.044, -0.008] (flat curve) | tuned on a six-point grid |
| 8 | `scoring_final` | 1.0 | -0.025 [-0.045, -0.005] | tie-break in flight (0.5/2.0 U-shape) |
| 9 | `last_window_guard` | 0.43 | -0.001 on strength; USSR nukes 37 -> 42 | kept for behaviour |
| 10 | `vp_base` | 0.5 | 0.35 and 0.75 both cover 0 | expert rate, first measured support |
| 11 | `access` (+`access_decay`) | 1.5 / 1.445 | **-0.011 [-0.032, +0.011] -- covers 0** | deletion candidate: the biggest machinery measured unimportant |
| 12 | `scoring_rival` | 1.0 | **+0.006 [-0.014, +0.026] -- covers 0** | deletion candidate (was -0.025 on the tiers bot) |
| 13 | `coup_discount` | 0.9 | **-0.005 [-0.025, +0.015] -- covers 0** | deletion candidate |
| 14 | `scoring_hand` | 1.0 | at its neutral already (bonus = 0) | inert by construction |
| 15 | `scoring_discount` | 0.8 | **dead code** -- nothing reads it | delete; the 0.8 describes a bot that does not exist |

## The rest, with their reasons

- **`europe_control_vp` (40)** -- what controlling all of Europe is worth,
  the whole VP track: it ends the game. Rules-exact; 20 and 60 bracketed
  it (-0.005 / -0.004) and 40 stands. Not a tuning candidate.
- **`europe_curve` (0)** -- a continuous Europe curve (20*tanh(k)) in
  place of the tiers' step. OFF; its one read (k=10) leaned worse
  (0.486 vs the tiers). A measured-off alternative, kept as an option.
- **`access_chain` (0)** -- two-hop reach. At 0 since its deletion and
  partial restore; the 0.2/0.4/0.8 grid's readings are in
  [the bisect note](../claude/2026-09-19-bisect-v0.2.1.md). Measured-off.
- **`potential` / `potential_refresh` (0 / 0)** -- the VP-rebuild
  potential term and its table cadence. The verdict read +0.021
  [-0.000, +0.042] at 1023 paired and the pre-registered rule stopped it
  ([the note](2026-09-23-the-potential-verdict.md)). Measured-off.
- **`hold_option` (0)** -- a hold's option value. Grid read nothing above
  0 at 0.25/0.5/1.0 and a measurable loss at 1.0
  ([the note](2026-09-22-the-hold-option-grid.md)). Measured-off.
- **`hand_assignment` (0)** -- the whole-hand allocation planner's gate.
  -0.240 [-0.262, -0.218]; the loss is a tie-break defect, not
  allocation ([the diagnosis](../claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md)).
  Measured-off; the defect is diagnosed and unremedied.
- **`space_ability_2/4/6/8` (1 / 1 / 1.5 / 1)** -- prices for the Space
  Race ability boxes (0 VP in the rules). Pre-declared UNMEASURABLE:
  box 8 fires in ~1% of games and no gate at this sample can move a
  number that rare. Correctness prices, not strength knobs -- "priced
  for correctness, not for strength, and should not be tuned against
  results."

## SurvivalPrior (the hand-survival search's priors)

Not reachable by `--bot-weights` -- the registry cannot ablate them
(the phase-3 mechanism gap in
[the sweep note](2026-09-23-the-ablation-sweep.md)). What each is:

| variable | now | what it does | basis |
| --- | ---: | --- | --- |
| `opponent_lowers_defcon` | 0.15 | P(the opponent takes a legal DEFCON-lowering coup) between our rounds | measured (0.098-0.108 bot-vs-bot); the one prior with data |
| `opponent_hand_attack` | 0.10 | P(an attack card removes one of our safe cards), chosen adversarially | guess |
| `unknown_chain_loss` | 0.25 | hazard for cards the search cannot see (Five Year Plan's random target) | guess |
| `replacement_hazard` | 0.15 | hazard on replacement draws (Missile Envy, Ask Not) | guess |
| `max_states` | 20000 | search budget before the safe-cards fallback | guess (a budget, not a price) |
| `sandbox_states` | 2000 | the event sandbox's search budget | measured |

Three of the four prices are guesses; the flat 0.15 has since been shown
to be a population average where the positions that need it want the
conditional (the last-safe-window guard's caveat). A learned
`OpponentModel` replaces the first two per observation when a checkpoint
is configured.

## How to read this table

Removal cost is an importance measure with one caveat the sweep itself
recorded: a covers-0 read bounds the effect at about +/-0.02-0.04 at
1152 games, it does not prove zero -- which is why rows 11-13 are
*deletion candidates* and not deleted. And the two behaviours kept
(#6, #9) are the reminder that play strength is not the only instrument:
the reply layer's whole justification and the guard's are measured in
poke rates and nuclear losses, not scores.
