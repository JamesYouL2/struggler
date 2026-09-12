# The hand planner: the plan, and what has to happen first

Four separate investigations on 2026-09-11 ended at the same place, which
is the argument for doing this rather than any of them:

- **Break commitment.** A 4-Op card breaks for 3 Ops and sends the fourth
  elsewhere 71% of the time. `_investment` is per-country by construction
  and the ranking re-compares after every point, so neither can ask
  "should this card's last Op finish a job or start one".
- **The nuclear rate**, ~12.6%, above the human 5.4-11.7% band. The
  maintainer's reading: insufficient hand planning.
- **Defectors**: 56 plays in 32 games, 100% Ops, *zero* headlines, by
  either side. Which card to headline is a hand question.
- **Nasser and Sadat at 1 Op** spent for their Ops. Disposal is a hand
  question too.

`DefconPlanner` is **not** this. It is a whole-hand *survival* search --
"can this hand be forced into a loss" -- and every quantity in it is
risk. There is no value allocation in it at all. This is a new thing
beside it, and its search is the model for making one affordable.

## The order, and why the first two come first

**1. Denominate in VP.** Today the chain is board movement -> Ops -> VP:
`vp_value = era_rate * ops_value(1)`. Every quantity is in raw board
units whose absolute scale is arbitrary, which is what
`Q/O = (1-r)(S/O) - 40er` showed -- the board weights cancel.

A hand planner has to compare an event, four Ops, a space attempt,
holding a card, and conceding 1 VP to Defectors. Two of those are
*natively VP*. Converting VP into Ops to compare them drags a real,
bounded, game-deciding unit through an arbitrary one. With Ops priced in
VP the objective is "expected VP from this turn", every term is
commensurable, and the space race and Defectors need no special case.

This was identified months of work ago as "price Ops in VP, not VP in
Ops -- the fix the invariance points at", and dropped from the queue. It
is a prerequisite, not a cleanup.

**2. Split the value functions into gross per-mode values.** The current
ones return *the value of the best use*, not *the value of each use*:

```python
space_value = vp_value * expected_vp - 0.4 * ops_value(ops)   # nets an opportunity charge
card_play_value = ... max(ops, event) ...                     # picks, internally
```

An assignment planner needs `value_as_event`, `value_as_ops`,
`value_as_space`, `value_as_held` *separately*, and makes the comparison
globally. The existing `max()` becomes the degenerate one-card case. This
is a refactor with the parity corpus as its oracle, so it is verifiable
without spending a gate -- and it is independently useful: the card table
could then report *why* a card was spent for Ops, not only that it was.

**3. The assignment planner.** Hand x modes, maximise expected VP for the
turn, subject to the constraints below. It captures the four findings
above; it does not capture sequencing.

**4. Beam search, only if sequencing shows up as the residual.** It buys
ordering -- Containment before the big plays, breaking before the
opponent can answer -- at a cost multiplied by the beam width, on a path
that is already 60% of a game's time, against a one-hour gate budget. And
an assignment can be printed as a table and checked by eye; a beam
cannot.

## Constraints the planner must respect

- **Action rounds:** 6 on turns 1-3, 7 on turns 4-10. One card each.
- **The headline** is a separate card, chosen before the round begins.
- **Scoring cards are forced**: no Ops, cannot be spaced, must be played
  this turn. They are not a choice and must not be scored as one (they
  swamped the first card table for exactly this reason).
- **One card is held** -- hand limit 8 (turns 1-3) or 9, against 7 or 8
  plays.
- **Space Race attempts: one per turn, or TWO from box 2.** The ability
  key is `space_race_double_attempt_holder` and
  `Engine._space_attempts_allowed` returns 2 for its holder. The engine
  enforces it and `DefconPlanner` tracks `space_attempts_left` -- but the
  *policy* does not: `space_card()` returns a single card, "the card this
  turn's space slot is for", and only that one card is ever given the
  space valuation. With box 2 held, the second attempt is invisible to
  the value function. The planner must take the allowance from the
  engine, never assume one.
- **The Space Race also needs the Ops**: box N has a minimum
  (`RULES["space_race_boxes"][N]["ops"]`), rising 2/2/2/2/3/3/3/4, so a
  1-Op card cannot be spaced at all and a 2-Op card cannot be spaced past
  box 4.

## Sign invariants, now tested

The maintainer's, in `tests/test_value_signs.py`:

- **"Space is better than nothing."** The *gross* expected VP of an
  attempt is positive whenever the rules allow one. Tested on the gross
  term, not `space_value`, which nets the opportunity charge and is
  negative for a big card by design -- which is the point of step 2.
- **"Playing any non-opponent card is better than nothing."** Only an
  *opponent's* card can price below zero, because playing it fires their
  event.

Both hold today. They are gates, not open defects, and they are worth
having because this repo's failures are sign failures: the forward
search's discount inverted and looked like a no-op for a day, and a
`CardSide is Side.US` comparison priced a term at zero.

## The commitment unit: the action round (maintainer, 2026-09-11)

Re-plan every action round, and commit to the plan *within* it -- the
card, the mode, and the whole Ops spend -- unless that turns out to be
stupid expensive.

This is the answer that makes the planner fix the break finding rather
than re-derive current behaviour. The 4th Op wanders off because the
ranking re-computes after every *point*; a plan made once at the start of
the action round and followed through the spend keeps it. Nothing else in
the design had to change to get that.

**The machinery already exists, as a speed hack.** `RolloutPolicy`
commits the same way below the MCTS root: `_placement_plan` spends "the
Ops as the parent would, but commit each country's best point count at
once instead of re-ranking after every point", and `_served` answers the
rest of the action round from it. It was written to make rollouts cheap.
The same shape in the main policy is a correctness fix, and it is already
tested (`tests/test_rollout.py`).

Cost: about 7 plans per turn per side, 140 a game, against one per turn.
Each plan is over hand x modes, which is smaller than the per-decision
ranking it replaces -- and it *removes* the re-rank after every point,
which is where the current cost is. It should be cheaper, not dearer, but
that is a claim to measure rather than assert.

Re-planning every round also dissolves the staleness problem: no
precondition triggers, no plan going stale across the opponent's turn.
The plan only has to survive the round it was made in.

## Two more requirements from the maintainer

**Reservation, which is not mode assignment.** In the Early War the US
must plan to hold a 3+ Ops card while Blockade is live and it controls
West Germany, or lose all its Influence there. Blockade *is* modelled --
`US_PAYABLE_DISCARDS` in `defcon.py`, and `policy.py` prices the choice
when it fires -- but only reactively. The survival planner's own comment
says why it never reserves: "refusing is always allowed (a board hit,
never a loss)". Correct for a survival search, and exactly wrong for a
value one.

So the planner needs a third concept beside assignment and commitment:
**keeping a card against a foreseeable demand**. Latin American Debt
Crisis is the other card in that set, and the China Card question has the
same shape.

**Held value costs a draw.** Holding a card means being dealt one fewer
next turn, so the value of a hold is the card's value next turn *minus*
the expected value of the card that would have been drawn instead -- a
discount on every hand, which `_unseen_holds` already has the pool to
compute. The maintainer adds that it does not apply the same way when a
reshuffle falls next turn, since the pool drawn from is then the returned
discards rather than the remaining draw pile. Reshuffles land on turn 3
and turn 9 (measured), so this is a per-turn condition and not a constant.

Currently `value_as_held` applies no discount at all beyond the certain
loss for a scoring card.

## Division

Steps 1 and 2 are mechanical and parity-checkable, and they are
prerequisites. Step 3 is where the Twilight Struggle judgement lives.
