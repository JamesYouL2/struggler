# Turn 10 action round 7: the play that cannot be answered

The maintainer, refining the China charge:

> it's actually basically 8 ops up until t10, where it replaces playing
> your worst card ... t10 ar7 is always like 5 to 10 vp at final scoring
> (I guess we can call it 7), because 4 ops can almost always double break
> and can't be countered. That's a special case.

Two corrections to the section above, and one finding larger than China.

**The decay is not smooth.** The charge is a flat 8 Ops until turn 10, not
a quantity shrinking with the rounds left. On turn 10 it stops being a
charge at all and becomes a comparison: playing China replaces playing
your worst card, so its worth is the gap between the two. That is a
different formula, not a smaller number, and it means copying
`military_credit`'s `_rounds_left` division would be the wrong shape.

**And the last action round inverts it.** At turn 10 action round 7 China
is worth **5 to 10 VP, call it 7**, because four Ops can almost always
break two countries at final scoring and *nothing can answer it*. So the
term is not monotonic: 8 Ops of cost for most of the game, roughly zero on
the last turn, and a large positive on the final action round.

**The generalisation is the part worth keeping.** Nothing about that
depends on the card. The final action round of turn 10 is the one play in
the game with no response, so *any* Ops spent there are worth their full
uncontested effect on final scoring -- no discount for the opponent
rebuilding, no risk of a counter-Coup, no defensive spend forced in reply.
The bot has `scoring_final * final_scoring_odds` for whether the game
reaches final scoring at all, and nothing whatever for **who moves last**.
Every term that quietly assumes the opponent gets a reply is wrong in that
one round, and it is the round that settles a close game.

That makes three quantities now found in turn order rather than on the
board -- the Military Operations requirement, the DEFCON hand-off, forced
defensive spend -- plus this fourth, which is the extreme case of the same
thing: the value of moving last.
