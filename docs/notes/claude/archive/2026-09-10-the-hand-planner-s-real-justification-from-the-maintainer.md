# The hand planner's real justification, from the maintainer

Not survival, and not only the disposal urgency the Lone Gunman position
argues for. The objective is **minimising the opponent's event value per
turn while maximising your own, measured in VP per Op** -- which is a
different and much larger thing than "do not die". Every card you must
play is a decision about whose event fires and when; a turn is an
assignment problem over that, and the survival search already enumerates
the state space it would run on.

Their estimate: **about 75% of the value of the MCTS work**, number
explicitly not calibrated. That is worth taking seriously against
tonight's MCTS measurement, which came in at 0.547 +/- 0.062 -- not
significant -- with 58% of its searches choosing a move on fewer than five
visits. If the planner captures most of what a search would, at a fraction
of 650 seconds a game, then the search's remaining case is narrow.

It also reframes the cheap disposal-urgency term: that term addresses the
*survival* corner of this objective only. Worth trying first because it is
a day and it has a test case, but it is not a substitute, and the notes
should not pretend the planner's justification shrinks to scoring timing
and hold choice if it works.
