# Three corrections that change the roadmap

**Win probability is a parameter, not a nicety.** The maintainer, flatly.
Nothing in `bots/` represents it: `game_value` is `GAME_SWING_VP * 40` at
this turn's VP price, whatever the position. So every risk trade the bot
makes is priced against the same constant whether it is winning by
fifteen or losing by fifteen -- and Wargames, whose entire worth is the
uncertainty it removes, cannot be priced at all. This is now the largest
single structural gap, ahead of the hand planner in the queue's logic
even if not in its order, because the planner's objective (opponent event
value against your own) is itself worth different amounts depending on
whether you are ahead.

**My "hardest card to value" answer was wrong, and instructively.** I
argued Bear Trap and Quagmire, because their value depends on *future
draws*. The maintainer: redraws are random and are modelled by an average
draw; the value should change only with **hand knowledge**, yours and the
opponent's. So the temporal axis I invented collapses, and Bear Trap sits
in the same class as Missile Envy and UN Intervention -- a hidden hand,
not an unknowable future. That is a much smaller and more tractable
problem than I made it, and it is a modelling instruction: **do not build
machinery for draw variance; build it for hand belief.**

Which leaves exactly one genuinely missing quantity behind all of these,
and it is the same one: win probability.

**The China Card is worth about 5 to hold.** The floor is a 2 VP swing,
which at the Late War rate of 2 Ops per VP is already 4 Ops, and it is
basically always worth more. The bot charges 4 for playing it (`score`'s
card branch), which encodes a holding value of 4 -- the right shape, a
little low.
