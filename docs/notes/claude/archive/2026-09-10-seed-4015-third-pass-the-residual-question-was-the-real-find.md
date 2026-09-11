# Seed 4015, third pass: the residual question was the real finding

The maintainer, reversing their own correction: **the bot needs to play
Lone Gunman before DEFCON 2.** Carrying it is the error.

So the sequence on this one game was: I claimed two defects, both wrong
(you cannot Space a 1-Ops card, and the planner does see the card); the
maintainer corrected both and said a turn-8 death to Terrorism while
holding it is hand pressure, not a bug; what I left over as "a question
rather than a finding" -- that it sat in hand through all of turn 7 at
DEFCON 5, 4 and 3 -- is the actual defect. The death was not avoidable by
turn 8. **Arriving at turn 8 still holding it was.**

The mechanism, stated so it can become a term. Lone Gunman hands the USSR
its Operations. At DEFCON 3 they spend them on a Battleground Coup, DEFCON
falls to 2, and the game continues. At DEFCON 2 the same Coup ends it, and
the phasing player loses. So the card has a **safe window that closes as
DEFCON falls**, and the bot has no notion of one. It ranked Lone Gunman
last every round of turn 7 because playing it is worth little, which is
true and beside the point: its value is not what it buys, it is that
playing it now costs almost nothing and later costs the game.

This is the clearest argument yet for the hand planner, and unlike the
rest of that case it names the objective precisely: a card is worth
disposing of early in proportion to *the chance its safe window closes
before the hand is emptied*. The DEFCON planner already enumerates the
state space that answers this -- hand, rounds, DEFCON -- and already knows
Lone Gunman is lethal at DEFCON 2. What it does not do is look forward
from a safe DEFCON to an unsafe one and price the difference. That is the
change: the search exists, the objective is missing.

Worth noting for its own sake: the cheap version may not need the full
planner. "Play a card whose forced value is certain defeat at DEFCON 2
while DEFCON is still 3 or more, if nothing better is pressing" is a
disposal-urgency term over the existing per-card risk, and the seed 4015
turn-7 position is its test case. Try that before building the planner,
because if it captures most of the value the planner's justification
shrinks to scoring timing and hold choice.
