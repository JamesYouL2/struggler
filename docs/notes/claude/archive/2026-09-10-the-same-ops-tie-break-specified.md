# The same-Ops tie-break, specified

The maintainer, on Decision 8, where Arms Race and NORAD score 35.40 to
the bit:

> I would rather play NORAD because you can event Arms Race for the event
> later... Ops value is the same, but you hold the card with the highest
> **remaining event value** during tiebreaks. It's really expected over
> end of turn, but calculating that is probably not a good use of
> resources; I fully expect the heuristic to be good enough.

So the rule is: **among plays of equal Ops, spend the card whose event
you least want to keep, and hold the one with the highest remaining event
value.**

That is not quite what the earlier note in these notes said. It framed
the tie-break as "burn the least valuable event", which invites using
`event_value` — the *immediate board effect* of firing it now. The right
quantity is the **option value of playing it as an event later**, which
is a different thing:

- **NORAD**'s event is a conditional flag (one Influence when DEFCON
  falls to 2, if the US holds Canada). Near-worthless to keep.
- **Arms Race**'s event is real VP off the Military Ops comparison, and
  it is worth keeping for a turn when the comparison is favourable.

Both are 3-Ops US cards in a US hand, so neither fires when played for
Ops and the Ops value is identical. The whole difference is which one you
would rather still be holding.

**And the maintainer has pre-empted the obvious over-engineering.** The
exact quantity is the expectation over the rest of the turn — will a
better moment for this event arrive before the hand runs out — and they
judge that not worth computing, expecting the plain heuristic to
suffice. Worth recording, because the hand planner exists and it would be
easy to route this through it for no gain.

This is the third thing the planner might have owned and should not:
China's play charge and the safe windows genuinely need lookahead, and
this does not.

**Implementation.** `_score_card_play` returns the same number for both,
so the tie is broken by the engine's option order. The fix is a
tie-break key: among plays whose value ties, prefer the lower
`event_value` of the card *as a future play from our own seat*. The 26
indifference positions in `docs/POSITION_PACK.md` Part C are the test
set, 19 of them card plays.
