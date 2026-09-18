# The hand planner, v2: disposal, space, hold, scoring timing

> **Superseded in its order of work by [v3](2026-09-18-hand-planner-plan-v3.md)**,
> after Codex's audit. G2 below is wrong as written (the drop is priced at
> 0.15 and accepted, not read as 0), "CIA Created can never be spaced" is
> false under Brezhnev Doctrine, and the "cornered" counts read through the
> F1/F5 instrument defects. The diagnosis stands.

2026-09-18. Builds on
[the 2026-09-11 plan](2026-09-11-the-hand-planner-plan.md), which still
holds for the constraints, the maintainer's rules on the space and hold
slots, and the commitment unit (re-plan every action round, commit within
it). What changes here is the **order of work** and **the evidence**: the
drift investigation ended at the hand, not the value function. The detail
is in [the drift note](2026-09-18-drift-located-at-v0.2.1-v0.2.3.md).

## Why this, now

- **One trap accounts for the whole measured drift.** Against the
  pre-v0.2.2 bot `07d553a` over 1024 seeds, HEAD's USSR loses 196 games
  to DEFCON 1 where v0.2.3's lost 147. HEAD's US pushes the old USSR into
  it 170 times where v0.2.3's did 199. About 78 games change hands, roughly
  0.038 of score, against a measured gap of 0.033.
- **33 of 36 nuclear games in HEAD self-play follow one pattern.** The
  phasing side plays CIA Created (the USSR, 25 games) or Lone Gunman (the
  US, 8) at DEFCON 2. The opponent spends the event's Ops on a
  battleground Coup, and the phasing player is responsible
  (`docs/ARCHITECTURE.md`, "DEFCON responsibility").
- **The bot is cornered turns before it loses.** In 35 of 36 games it had
  already logged "EVERY option is a certain loss". In all 25 CIA games the
  USSR was holding CIA Created when DEFCON fell to 2. The US's Coup caused
  the drop 17 times; the USSR's own battleground Coup caused it 8 times.
- **Nothing in `defcon.py` or `safety_key` changed after v0.2.3.** The rise
  came from value-function changes (five-bucket, factor-2) shifting which
  cards get played and which are left over. Survival is currently a side
  effect of value ordering. Nothing *owns* it.

The maintainer's framing, which this plan adopts: **the hand planner has to
get much better, and the DEFCON trap is its most visible symptom, not its
scope.** It covers four jobs: get rid of cards before DEFCON is 2, decide
what to space, decide what to hold, and decide when to score.

## Baseline (HEAD self-play, 128 seeds, italy/austria, run 35306328917)

Computed from the per-game logs. The script is to become
`scripts/hand_metrics.py` (Phase 0). "Held" means left in hand after the
side's last play of a turn; games that end mid-turn slightly inflate it.

| | US | USSR |
| --- | ---: | ---: |
| lost to DEFCON 1 (of 128) | 9 | 27 |
| Space Race attempts per game | 1.51 | 1.44 |
| turns with a Space attempt | 21% | 20% |
| opponent cards played that went to space | 10% | 9% |
| end-of-turn holds that are opponent cards | 80% | 79% |
| most-held card (turn-ends held) | Decolonization 95, Nasser 88, **Lone Gunman 74** | **CIA Created 150**, **Duck and Cover 129**, Truman Doctrine 82 |
| games holding a DEFCON-2-lethal opponent card *at DEFCON 3* | Lone Gunman 37, We Will Bury You 21 | **CIA Created 86**, Duck and Cover 78, Grain Sales 40 |

Scoring cards (1092 plays): headline 35%, AR1-AR5 21%, AR6-AR7 43%. The
last-round share is mostly the engine forcing the play
(`Engine.must_play_scoring`).

What it says, job by job:

- **Disposal.** The worst cards do go to the hold slot, as the maintainer's
  rule wants ("your two worst cards are generally for space and hold").
  But the worst card for the USSR is often CIA Created, and a held CIA
  Created is a latent loss that turns certain the moment DEFCON reaches 2.
  It was held at DEFCON 3 in two games of every three.
- **Space.** The slot is used on one turn in five. Sankt spaces "basically
  every opposing card that costs you something" (EXPERT_STRATEGY.md). Here
  about nine in ten opponent cards are played and their events fire.
- **Hold.** No reservation, no draw cost, no safety check. The hold is
  whatever is left after the greedy picks.
- **Scoring.** The slot is emergent. Nothing compares "score now" with
  "score later this turn" or "headline it".

## What the planner is today, and where each gap lives

`DefconPlanner` (`bots/strategic/defcon.py`) is a whole-hand **survival**
search. It asks "can this hand be forced into a loss this turn?", and every
number it returns is a probability. The policy turns that into a price
(`safety_key`: residual risk times `game_value`). Card choice itself is
greedy: one decision at a time, best `score`, with risk subtracted.

| gap | where | consequence |
| --- | --- | --- |
| **G1: the horizon ends at the turn.** `_solve` returns 0 when `rounds <= 0`. | `defcon.py` | Holding a DEFCON-2-lethal card into next turn is free. Next turn opens at DEFCON 3 or better, the opponent drops it again, and the card is still there. |
| **G2: survival is min over our own replies against one drop.** `_next` applies one per-round chance (0.15) of the opponent lowering DEFCON, and we answer optimally after it. | `defcon.py` | At DEFCON 3 with spare safe cards, "I can hold CIA to the end" is feasible, so the risk reads about 0. It stops being feasible after two or three greedy plays spend the safe cards, and by then there is no exit. |
| **G3: no disposal value.** Nothing prices "this card is safe to play *now* and will not be later". | `policy.py` | Playing CIA Created at DEFCON 3 costs a little value (1 Op, a US Op, the hand revealed) and buys nothing in `score`, so it loses to anything positive. |
| **G4: one space card.** `space_card()` names a single card, the worst opponent card the Space Race accepts. The second attempt from box 2 is invisible. The slot never competes with the hold slot. | `policy.py` | The slot is used on 20% of turns. |
| **G5: the hold is a remainder.** `value_as_held` is `hold_value`: no draw cost, no reservation (Blockade payer), no DEFCON check. | `policy.py` | Holds are the leftovers of greedy ordering. |
| **G6: scoring timing is a comparison of this decision's values.** `scoring_card_value` resolves the scoring now. Nothing prices the opponent's rounds in between, or the value of scoring after improving. | `policy.py` | The headline, early and late shares are an accident of the ranking. |
| **G7: our own battleground Coup at DEFCON 3.** `coup_survival_risk` re-plans at DEFCON 2 with the turn horizon (G1) and the one-drop model (G2). | `policy.py` | The USSR Coups into Zaire at DEFCON 3 holding CIA Created: 8 of 25 losses. |

## Design

**One object, a turn plan, re-made at every action round** (the
maintainer's commitment unit):

```
TurnPlan
  headline:   card                          (headline phase only)
  rounds:     [(card, mode) for each remaining action round]
              mode ∈ {ops, event, space_race, un_intervention (+ card)}
  hold:       cards left at turn end        (never a scoring card)
  exits:      for each DEFCON-hazardous card, the slot that removes it
  value:      expected VP of the plan
  risk:       P(this turn or the next turn's opening is lost to DEFCON 1)
```

The objective is **expected VP minus P(loss) times the game swing**. That
is the same price `safety_key` already uses, now computed over a plan
instead of one decision. Per-mode values come from the split already done
in step 2 of the 09-11 plan (`value_as_ops`, `value_as_event`,
`value_as_space`, `value_as_held`). The planner compares those; it does
not re-derive them.

The search is **over assignments, with order only where order changes
something**: the DEFCON-dependent cards, the scoring cards, and the Space
Race box (its Ops minimum rises). Everything else is order-free within the
turn under the frozen-board approximation `DefconPlanner` already makes. A
hand of at most 9 cards, with 2 space attempts and 1-2 holds, is an
assignment of 9 cards to at most 4 kinds of slot. That is small enough to
enumerate with the same `lru_cache` state machine `_solve` uses, carrying
value alongside risk.

### Job 1: get rid of cards before DEFCON is 2

For each card, precompute **`lethal_below(card)`**: the highest DEFCON at
which firing it can end the game for us. It is 2 for the reducers
(Duck and Cover, We Will Bury You, KAL 007, Olympic Games at 2) and for the
borrowed-Coup cards (CIA Created, Lone Gunman, Grain Sales, Tear Down This
Wall, Ortega). `_event_risk` already knows every one of these; this lifts
its knowledge into a per-card property the plan can schedule against.

Then two rules, as constraints on the plan rather than priced suggestions:

1. **Every hazardous card gets an exit in the plan**, in a slot where it is
   safe under the plan's own DEFCON path. The exits are:
   - play it while DEFCON is above its threshold;
   - send it to the Space Race (needs the Ops: CIA Created and Lone Gunman
     are 1 Op and can never be spaced);
   - pair it with UN Intervention;
   - hold it, *only* if the next-turn check below passes.

   The DEFCON path includes **every drop the plan itself makes** (our
   battleground Coups; that is G7) and the opponent's drops.
2. **The opponent's drops are a turn-level budget, not a per-round coin.**
   Replace the single 0.15-per-round drop with "the opponent can lower
   DEFCON at their next round, and will if it wins". While we hold a
   borrowed-Coup card at DEFCON 3, the US dropping to 2 is not a random
   event; it is their best move. 17 of the 25 CIA losses were exactly this.
   Keep the measured prior (0.098-0.108) for reducers the opponent does
   not control and for the unknown; use the adversarial model where the
   opponent profits from the drop.

**Across the turn end (G1).** A held card is evaluated at next turn's
opening: DEFCON +1, then the opponent's headline and first round. A hold
of CIA Created passes only if the USSR can still play it at its first
action round at DEFCON 3 or better. **The USSR moves first in each action
round, so AR1 is always safe for it unless a headline dropped DEFCON.**
The US moves second, so a held Lone Gunman is exposed to the USSR's AR1
Coup. This asymmetry is worth a fixture on each side.

The cheap rule that falls out, and should be the first thing tested:
**the USSR never ends an action round holding CIA Created at DEFCON 3 or
better unless a guaranteed exit remains** (UN Intervention in hand and
kept for it, or enough safe cards that no sequence of opponent drops
corners it). Mirror it for Lone Gunman. It is expected to remove most of
the 25 + 8 losses by itself.

### Job 2: what to space

- **The attempts come from the engine** (`_space_attempts_allowed`: 1, or
  2 from box 2), never assumed to be one. That is G4, flagged in the 09-11
  plan and still open.
- **Rank candidates by disposal gain**: `max(value_as_ops,
  value_as_event) - value_as_space` for each card the box accepts
  (`space_race_boxes[N].ops`). An opponent event whose best use for us is
  negative is the natural candidate. A DEFCON-hazardous card that *can*
  be spaced (Duck and Cover: 3 Ops) gets its exit here before anything
  else.
- **The slot competes with the hold for the worst cards** (the maintainer:
  "your two worst cards are generally for space and hold"). The assignment
  gives each of the two worst cards a slot, and chooses which goes where
  by which slot is *also* wanted for something else: reservation (Job 3)
  or a spaceable hazard (Job 1).
- **Keep the box abilities priced** (`space_ability_2/4/6/8`). Sankt calls
  box 6's held-card discard "by far the most important ability with this
  rabid spacing style". Its value rises when the hold slot is carrying a
  hazard, which the plan can now see.
- **Expert caution to encode as a fixture, not a weight:** do not enter the
  Mid War holding a 2-1 space lead (One Small Step jumps it).

Target: space usage moves toward Sankt's style, meaning most turns with a
harmful opponent card in hand and an eligible box use the slot. Do not set
a numeric target without the maintainer. EXPERT_STRATEGY.md is explicit
that the source covers turns 1-3 only.

### Job 3: what to hold

The hold slot is contested by four jobs. The plan resolves them in this
order:

1. **Safety.** Never hold a card that fails the next-turn DEFCON check
   (Job 1). Never hold a scoring card (`value_as_held` returns `LOSS`;
   keep that).
2. **Reservation.** Keep a card against a foreseeable demand. The US needs
   a 3+ Ops payer while Blockade is live and West Germany is US-controlled
   (maintainer, 09-11); Latin American Debt Crisis is the same shape. UN
   Intervention is kept for the opponent card it best neutralises (`un_card`
   already names it). **When reservation applies, it wins the hold slot and
   disposal falls to the Space Race.**
3. **Disposal.** Otherwise hold the worst card that is safe to hold.
4. **Draw cost.** A hold is worth its value next turn **minus the
   expected value of the card it displaces from the deal**. The unseen
   pool is already built for the reply budgets. At a reshuffle turn (turn
   3 and turn 9, measured) the pool is the recycled discard, not the
   remaining deck. This is the maintainer's point from 09-11, still unpriced.

The USSR turn-3 hold ordering from Sankt (EXPERT_STRATEGY.md: Five Year
Plan > UN Intervention > a strong 4-Ops US event > Indo-Pakistani War >
Duck and Cover > Defectors > other US events) is a **fixture to check
against**, not a rule to hard-code. Note that Duck and Cover appears there
as a hold. It is lethal at DEFCON 2, so the ordering assumes the holder
manages DEFCON; the plan must hold it only where the next-turn check
passes.

### Job 4: when to score

Today: 35% headline, 21% early rounds, 43% final rounds (mostly forced).
The plan chooses the **slot** for each scoring card in hand, among
headline (if still in the headline phase), each remaining round, and
"forced last". It compares expected VP per slot:

- **Now** is the region's current score (`scoring_card_value` resolves it
  exactly).
- **Later in the turn** is the current score, plus what our plays before
  the slot add to the region, minus what the opponent's rounds before the
  slot can take. The reply look-ahead already prices the opponent's best
  answer to a placement. The same machinery answers "their best play in
  this region" per intervening round, eventless as mandate #4 requires.
- **Headline** resolves before any action round, but after the
  opponent's headline when theirs has more Ops (a scoring card has 0 Ops).
  So a headlined scoring card scores after their headline moves the board.
  The plan must price that ordering, not assume the headline scores the
  board as it stands.
- **Holding a scoring card costs rounds.** Each scoring card left for the
  end takes a round the hand might need for an exit (Job 1). The plan sees
  that because both live in the same assignment.
- **Our own scoring cards also change DEFCON-independent risk.** A scoring
  card that ends the game (Europe control, 20 VP) is a certain win and
  outranks everything, as `safety_key` already handles.

The maintainer has not stated scoring-timing rules, and the outside source
explicitly does not cover them (EXPERT_STRATEGY.md, "does not cover ...
when to score a region"). Job 4 therefore starts as **measurement**. It
reports, per scoring play, the VP at the chosen slot against the VP at the
other feasible slots, computed after the fact from the game logs. It only
becomes a decision once that report shows a systematic loss. Add the
question to EXPERT_ASKS.md.

## Phases

Each phase is independently shippable. Each is gated the new way:
**1024 seeds against `07d553a`, paired with `base-vs-07d553a` via
`compare_to`**, plus the self-play hand metrics before and after. A
parent-only gate is not enough here. The drift that started this was
invisible to every parent gate.

| phase | scope | success is |
| --- | --- | --- |
| **0. Instruments** | `scripts/hand_metrics.py`: the baseline table above, from any run with `"logs": true`. Add a "held at DEFCON 3" and a "cornered" (first "certain loss" log line) counter to the benchmark report so every run carries them without logs. Regression fixtures from the self-play logs: at least three of the 25 CIA positions (e.g. seeds 22052, 22055, 22073, one US-dropped and two USSR self-drops) and two Lone Gunman positions, rebuilt by replaying the seed to the decision where the exit still existed (the engine is seeded and the strategic bot has no RNG), then saved with `Engine.serialize` so the fixture does not depend on today's bot to reach it. | The fixtures fail on HEAD, for the right reason. |
| **1. Disposal** | `lethal_below` per card; horizon across the turn end for held hazards; the adversarial opponent drop for borrowed-Coup cards; `coup_survival_risk` against the extended horizon; the CIA / Lone Gunman rule. Inside `defcon.py` and `safety_key`, no new planner object yet. | USSR self-play nuclear losses fall from 21% toward the human 3-6% band. The fixtures pass. The paired arm against 07d553a is positive. **A USSR that stops Couping to win is a regression, not a fix**: watch coups per game. |
| **2. Space slot** | Multi-attempt from the engine; disposal-gain ranking; spaceable hazards first. | Space attempts per game rise. The paired arm is non-negative. The fixture for "Duck and Cover at DEFCON 3 with an attempt left goes to space" passes. |
| **3. Hold slot** | Safety, then reservation, then disposal, then draw cost. The Blockade payer fixture from 09-11. | No end-of-turn hold of a hazard that fails the next-turn check. The Blockade fixture passes. The paired arm is non-negative. |
| **4. Scoring timing (measure)** | Per-play slot regret from the logs. | A report, and an EXPERT_ASKS entry. A decision rule only if the regret is systematic. |
| **5. The TurnPlan** | Replace greedy card choice with the plan, committed per action round (the 09-11 step 3). Jobs 1-3 move into it as constraints and objective terms. | Paired against 07d553a and against Phase 3's head. Decision time measured locally, alone: the survival search is already about 60% of a game's time. |

Phase 1 is first because it is the measured loss, it is small, and it
needs none of the planner machinery. Phases 2 and 3 are the parts of the
old plan that the baseline shows are furthest off. Phase 5 is the real
planner and should not block the others.

## Things not to do

- **Do not "fix" the nuclear rate by retuning `SurvivalPrior`.** The 0.15
  drop prior is not the fault: the losses come from positions the search
  correctly finds hopeless, reached through choices the search never
  priced (G1, G2, G3).
- **Do not make risk lexicographic again.** `safety_key`'s own history
  records why pricing it replaced ranking it (0fb7dd1): a bot that never
  buys risk loses to DEFCON 1 38x to 82x less often than a human field and
  is weaker for it. The target is the human band, not zero.
- **Do not hard-code the Sankt orderings.** They are turn 1-3, from one
  school, and EXPERT_STRATEGY.md records where Sankt and Ziemowit disagree.
  Use them as fixtures that the plan's choices can be checked against.
- **Do not measure a phase against its parent alone.** See above.

## Open questions for the maintainer

1. Scoring timing: any rule of thumb for headline vs early vs last? (The
   outside source is silent.)
2. Space aggression: is "space every harmful opponent card when a box
   accepts it" the target, or is there a floor below which Ops win?
3. CIA Created as the USSR: play it at AR1 whenever DEFCON is 3+, or is
   headlining it ever right? (Headlining exposes it to a US headline that
   drops DEFCON first, since CIA Created's 1 Op resolves after almost
   anything.)
4. Is a USSR nuclear-loss rate in the human 3-6% band the right target for
   a bot, or should it sit lower?
