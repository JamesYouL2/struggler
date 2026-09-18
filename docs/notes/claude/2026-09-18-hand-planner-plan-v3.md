# The hand planner, v3: after Codex's audit

2026-09-18, evening. Supersedes the order of work in
[v2](2026-09-18-hand-planner-plan.md), written this morning, after
[Codex's audit of it](../codex/2026-09-18-hand-planner-audit.md) (PR #3).
v2's diagnosis stands: the drift is the CIA Created / Lone Gunman trap, and
nothing owns survival. What changed is **which defects come first** and
**what the evidence says**. Steps 1 and 2 below are implemented in the same
commit as this note.

## Is v2 right? Checked finding by finding

Every one of the audit's five findings reproduces on `70f174c`, from its
own fixtures:

| | claim | reproduced |
| --- | --- | --- |
| F1 | a spaceable suicide card is keyed certain defeat | Duck and Cover `(-1, 0, -317.5)` with `action_risk` `(0, 0)` |
| F2 | CMC is assumed to protect even when its target can pay to lift it | planner risk 0.0; driven through real decisions, the US defuses in West Germany, Coups Cuba, wins |
| F3 | an event that creates the first Coup target is priced on the old board | Fidel event then CIA Created: planner 0.0, US Coups Cuba, wins |
| F4 | reaching box 2 in the search does not grant the second attempt | spacing Duck and Cover: 1.0 against the true 1/3 |
| F5 | the choice log reads the risk from the sort key, whose risk slot is 0 | logged `risk=-0.000`, `action_risk` 0.15 |

Where the audit is right about v2:

- **G2 was wrong as written.** v2 said a DEFCON-3 hold "reads about 0". It
  reads 0.15, and the bot *accepts* it for Decolonization's board value.
  The defect is that 0.15 is a population average applied to positions
  where the opponent has a battleground Coup available. There the
  conditional chance is far higher. The prior is not zero.
- **"CIA Created can never be spaced" is false.** Brezhnev Doctrine's
  Ops bonus makes it spaceable. `test_one_op_cia_is_not_spaceable_without_ops_bonus`
  already said so. A context-free `lethal_below(card)` would have
  hard-coded the error.
- **The adversarial drop imported omniscience.** The US does not know we
  hold CIA Created. The legitimate form is a *legal-reachability* guard,
  labelled as worst case, as step 2 below does.
- **The "cornered" counter was not trustworthy.** F1 inflates "EVERY option
  is a certain loss" and F5 hides accepted risk, so v2's "35 of 36 were
  cornered first" reads the symptom through the broken instrument. The
  game endings are real. The decision that first made them inevitable is
  not identified by them.
- **Several targets were imitation, not correctness.** These were the
  human 3-6% nuclear band, "space like Sankt", and v2's unconditional
  Blockade reservation. The audit is also right that a draw-cost term
  cancels between plans that hold the same number of cards.
- **Scoring regret from the logs is descriptive, not causal.** A different
  slot changes both players' later play. Forks from the decision with a
  fixed reply policy are the measurement.

Where I think the audit is wrong, or under-specified:

- **"Finish the VP rebuild" is not step 3. It is a decision that belongs
  to the maintainer.** The audit sets a checkpoint for this: "if it still
  needs unresolved kernel/performance work, record that blocker and revisit
  the dependency". It does. [The viability verdict](../codex/2026-09-17-potential-delta-design.md)
  puts the potential at 0.2-1.5 s per action-round ranking, 40-120 s per
  game on a 21 s baseline, and says no further wiring lands until the
  maintainer picks a native kernel or stays descoped. So the rebuild blocks
  the allocator only if the answer is "kernel".
- **F1's full fix ("rank card+mode pairs") is the TurnPlan, not a patch.**
  The patch that meets the audit's own rule ("certain defeat means every
  legal continuation loses") is smaller. A card is only as bad as its best
  legal mode, and the modes come from the engine's own `_play_modes`. That
  patch is done. The pair ranking belongs to step 5.
- **F2's "payment that removes the last relevant target" cannot happen.**
  The CMC payment removes the *payer's* influence, and a Coup target needs
  *ours*. The code says so where the rule is read. I did not write a test
  for a state that has no legal path.

## The plan

| | step | status |
| --- | --- | --- |
| 1 | Safety contracts: F1-F5 | **done here** |
| 2 | The last safe disposal window, as a legal-reachability guard | **done here** |
| 3 | Validation: paired, fixed anchor, fresh seeds | dispatched with this commit |
| 4 | Instruments on the fixed log: the first decision that closes the last exit | next |
| 5 | **Maintainer:** kernel or descope for the VP potential | blocks 6's production form |
| 6 | Joint space / hold allocation | after 5 |
| 7 | Scoring and event timing by forks | after 6 |

### 1. Safety contracts (done)

- **F1.** `_score_card_play` looks at the card's non-firing modes (Space
  Race, UN pairing, from the engine's `_play_modes`) before returning the
  Ops play's LOSS. UN Intervention played alone no longer inherits its
  partner's LOSS as a flag. It is priced at the game, and the planner says
  whether the partner is really stranded. Gate:
  `test_certain_defeat_in_the_key_means_certain_defeat_in_the_planner`. The
  key's certain flag and the planner's risk now agree option by option.
  It is listed under bug shape 2, which is now at six instances.
- **F2.** `Engine.cmc_defuse_countries` is the one statement of the defuse
  rule. It was written twice in the engine already. `battleground_coup`
  treats CMC as protection only when it returns nothing.
- **F3.** `latent_hazards` lists the borrowed-Coup cards that are safe only
  for lack of a target. When one is in hand at DEFCON 3 or below, a firing
  event is resolved on a public sandbox and the hand is re-planned there
  (`_mode_risk`). A placement into a battleground we are absent from is
  re-planned the same way (`_placement_risk`). Placements are now priced,
  not ranked, as Coup targets already were. The trigger keeps the cost off
  every other decision.
- **F4.** `DefconPlanner.attempts_allowed(pos)` is proved equal to the
  engine box by box for all sixteen marker pairs.
- **F5.** `safety_key` records each option's `action_risk`, and the log
  prints those numbers. A test checks the logged number against
  `action_risk`.

### 2. The last safe disposal window (done)

`StrategicPlayer.cornered_after_drop`, for card plays and play modes at
DEFCON 3. The opponent must have a legal battleground Coup that lowers
DEFCON; this uses the public board and never their hand. The hand is then
re-planned with that drop taken for certain. A play after which the hand
is certainly lost is priced at residual 1 (the whole game), provided some
option in the decision is not. Fixtures:

- CIA Created before Decolonization, with a legal US Coup in Cuba. This is
  the audit's F5 position.
- The control: a spare card to hold keeps the exit, and Decolonization
  still wins on the board.
- Lone Gunman, the US mirror.
- No legal drop (Nuclear Subs): the prior stays in charge and the 0.15 is
  accepted.

Not covered, deliberately: the headline, and the turn end (v2's G1). The
next turn opens at DEFCON +1 with the USSR moving first. Step 4's
instrument decides whether G1 is worth building. It should not be built on
the strength of the old log counts.

### 3. Validation (dispatched)

Two arms in `experiments.yml` on a fresh block, seeds 30000-31023: this
commit against `07d553a`, and `main` (`70f174c`) against `07d553a` with
`compare_to`, so the reading is paired. Both have `logs` on, so the
nuclear losses by seat and card come from the same games. What counts:

- **the paired difference** is the verdict;
- **USSR nuclear losses** (196 of 1024 at HEAD against 07d553a) should fall;
- **Coups per game** must not collapse. A USSR that stops Couping to win
  is a regression, not a fix.

No gate verdict is claimed here; the runs report on their own.

### 4-7

4 counts, per game, the first decision after which the hand had no exit.
It uses the fixed log and the planner's own risk, so it can say whether
G1 matters. 6 is the audit's step 4 as written: one objective, no double
allocation of an exit, and holds that are what the card flows leave. 7 is
the audit's step 5. If 5 comes back "stay descoped", 6 is built in raw
units and labelled as such. It is the audit's fallback, not a calibrated
expected-VP optimiser.

## Open questions for the maintainer

1. **The VP potential: native kernel, or stay descoped?** (Step 5. It
   decides whether step 6 waits.)
2. The guard is binary and conservative: cornered after a legal drop means
   the play is priced at the whole game. Is "dispose while it is safe"
   right as a rule even when the board gain given up is large, or should
   it be a probability once the conditional drop rate is measured?
3. v2's questions on scoring timing and space aggression stand, minus the
   human-band target. The audit is right that it is not a correctness
   target.
