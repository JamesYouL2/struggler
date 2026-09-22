# The assignment planner: step 3's design

Step 3 of [the whole-hand planner note's](../../notes/claude/2026-09-20-the-whole-hand-planner.md)
"The order this implies": *the assignment planner behind a weight,
alongside the DP, scoring timing included from the start (ruling 5) and
the space slot count handled by the two-solve approximation (ruling 1).*
Shape (a) from that note: **separable prices, exact constraints.** The
prices this project has calibrated all year stay as they are; what
changes is that the turn's allocation is *solved* instead of tie-broken.

## The problem, exactly

A hand of 8-9 cards over 1 headline plus R action rounds:

    max  sum over cards of value(card, slot)
    s.t. one headline; R round units; at most one UN unit (UN card +
         one opponent card, consumed together in one round); the space
         unit(s) go to the ruling-4 policy pick(s); every remaining card
         is held; a scoring card is NEVER held.

Round units are one card each in one mode: an ordinary play (its
`card_play_value` price, both modes already maxed), a space play
(consumes the card and the round), or the UN unit (two cards, one round).
Holds are the remainder and cost nothing to assign.

## The slots, and where each price comes from

| slot | price (unchanged code) | notes |
| --- | --- | --- |
| headline | `_score_card_play`'s headline price + `headline_pick_risk` | per card |
| round play | `card_play_value` (best legal mode) | per card per round |
| space | `space_value(...)` | **only** the ruling-4 pick(s): "the worst opponent card the Space Race accepts" |
| UN unit | the pairing's play price (`play_price` of the UN card) | partner fixed at `un_card`'s pick -- that policy stands, like ruling 4's; enumerated partners are a later refinement |
| hold | `value_as_held` (= `hold_value`, `hold_option` at 0 after its grid) | scoring cards ineligible |

What the assignment buys (the note's list): no double allocation (the
`space_card`-skips-`un_card` hack is subsumed *in the planner's path* --
the shipped `space_card` keeps its guard until the per-card path is
deleted, because the parity corpus pins it), space and UN and hold
decided together, and the headline chosen knowing what the rest of the
hand needs.

## Ruling 5: scoring timing from the plan, not a constant

`+2 x action_round` is gone under the planner. The scoring card's price
in round k becomes

    play[k] = score_now + sum over rounds j < k of gain(card assigned to j)

where `gain(c)` is the caller-supplied expected improvement the plan's
own play in round j makes to the scoring region (its Ops weight in that
region). The coupling breaks pure separability -- the price of one slot
depends on the assignment -- so it is solved as a **two-pass fixed
point** (cap 3 passes, stop when the assignment stops changing): solve
flat, re-price the scoring card's rounds from that solution, re-solve.
Bounded, explainable, and it is exactly the information "+2 x AR" was a
stand-in for.

## Ruling 1: the second space slot is stochastic

The second attempt exists only if the first advances the box, and that
is a die roll. Per the ruling's cheap approximation: **solve once per
slot count and weight by P(the first attempt advances the box)**. The
output is therefore a weighted list of allocations (one per slot count),
not a single plan: execution uses the allocation for the slot count that
has realised. The exclusivity clause (the slot denies them the doubling)
is `space_ability_2`'s problem and stays a price, not a constraint.

## What the DP keeps (ruling 2)

`DefconPlanner` is untouched. The note's objective subtracts
P(loss) x game_value, but the DP already vetoes lethal plans on hazard
hands (that is its whole content: DEFCON drops, hand attacks, trap
states, the China card). v1 = the assignment maximises value with the DP
retaining its current override; subsumption is the LATER step ("build
it, prove it reproduces the DP's risks on the corpus, then delete").

## Shipped shape

- `bots/strategic/hand_planner.py`: the solver. Pure -- it sees prices
  and constraints and returns an allocation (DP over subsets; 10 cards x
  7 rounds is ~58k states, exact, dependency-free). No evaluator or
  engine imports, the same contract `evaluator.py` has.
- A weight (`hand_assignment`) at **0** as shipped. At 0 the allocation
  is **not computed at all** -- the table prices through the event
  sandbox, and a gate that is off should cost nothing -- so the ranking
  is byte-identical and the parity corpus pins it. (The first draft of
  this note said "computed and ignored"; measured practice beat it.) The
  arm prices the term like every other one here.
- The plan reaches exactly one place: the ranking for a card choice,
  where its pick leads WITHIN the safety key's own order --
  `(certain, pref, risk/score)`. Certain defeat still refuses a play
  outright, the risk/score blend orders everything the plan does not
  name, and `pref` is constant 0 whenever the gate is off.
- Infeasible hands (more scoring cards than play slots) return `None`
  and the caller keeps today's per-card behaviour. The planner is never
  a source of crashes.

## Found while wiring: the double-attempt grant has no writer

Ruling 1's "second attempt at box 2 (6.4.4)" exists twice and is granted
nowhere: `Engine._space_attempts_allowed` reads the game effect
`space_race_double_attempt_holder`, and **nothing in `src/` writes it** --
while `DefconPlanner.attempts_allowed` states the marker rule the ruling
describes. The two implementations disagree and the engine's may never
fire. The plan takes the engine's count as the count and estimates the
mid-turn opening from the ruling's own words; when the grant is fixed
(or the two rules unified), `_space_slot_mix` is the only caller to
update. One occurrence, so a note -- twice and it becomes a shape.

## Measuring it

Not by corners -- the survival side is nearly solved. The tail: a third
of USSR seat-games touch 0.25 whole-hand risk without closing out
(`scripts/measure_last_exit.py`, watch the mass at 0.25). And the
anchored arm goes before any merge, with the honest prior stated: the
last three measured wins were +0.039, +0.031 and +0.043 and none was a
search.

## Next slices, in order

1. ~~The solver and its exactness tests~~ **done**: `hand_planner.py`,
   10 exact tests, a mutation check on the may-hold constraint.
2. ~~Wiring~~ **done**: policy's `hand_prices`/`hand_plan` (the table is
   the scorer's own `play_price`, minus the two plan-owned terms), the
   ranking lead behind `hand_assignment`, the corpus backfilled with
   `hand_assignment: 0.0` (the `reply_model=0` precedent, 355 records),
   the parity oracle green unchanged -- the refactor is bit-identical.
3. The arm (base/on pair, 1024 seeds, one dispatch), with
   `scripts/measure_last_exit.py` before and after for the tail.
4. Ruling 2's question: does it reproduce the DP's risks on the corpus?
   Only then delete the DP.
