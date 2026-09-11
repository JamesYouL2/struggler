# Correction: playing The China Card costs *more* than holding it, and it decays

The reasoning in the section above was backwards. It guessed that because
playing China transfers the card rather than destroying it, the charge
must be *less* than the 5 Ops holding is worth. The maintainer:

> playing it costs 8 ops, yes, until end of game. Basically whoever has it
> on t10 is going to play it 100% of the time (even with a 2 VP swing).
> the transfer is a ton... So playing it is a hand planner decision.

**The transfer is the expensive half.** You lose the option and hand the
same option to the opponent, so the cost is roughly double the hold value,
not a fraction of it. 8 Ops against 5.

And it is **not a constant**: it is a rounds-remaining quantity. On turn 10
there is no future to hold it for, so the charge is zero and the card is
played unconditionally -- against a 2 VP swing, even. The same shape as
`military_credit`, which already divides by `_rounds_left`.

So the target is a term worth about 8 Ops with a full game ahead, decaying
to 0 by the last turn, where the bot currently charges 0.06 Ops flat. That
is not a rescale of `CHINA_HOLD_RAW`; it changes when China is played in
most games and needs a gate. And the maintainer's own conclusion is that
the decision belongs in the whole-hand planner, not in a constant applied
at the point of play -- which makes this the second thing waiting on the
planner, after the safe-window problem.

`docs/EXPERT_ASKS.md` item 7 is answered: holding 5 Ops, playing 8,
decaying to 0 at the end of the game.
