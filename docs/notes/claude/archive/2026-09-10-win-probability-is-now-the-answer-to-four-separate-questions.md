# Win probability is now the answer to four separate questions

The maintainer, on the swing constant: "the sentinel being 30 as an
average is probably better (or variability calculated). But win
percentage is more important."

So the cheap fix is `GAME_SWING_VP = 30`, as the average reachable swing
rather than the track's full width -- one line, and strictly closer to
the truth than 40 for the same cost. The better fix is to compute the
reachable swing per position, `20 - vp` and `20 + vp`. Neither is the
real answer.

**The real answer keeps being the same one.** Win probability has now
been named as what a quantity actually depends on in four places:

| Where | What was said |
| --- | --- |
| Late War valuations | "Late War values are the most conditional on **win probability** of any period" |
| Wargames | its worth is `(1 - win_pct) * game_value` -- the uncertainty it removes |
| Terrorism | "swingy on win percentage" |
| `GAME_SWING_VP` | "win percentage is more important" than any average swing |

It appears seven times across `docs/` and `models/`, and **zero times in
`src/`**. The bot has banked VP, a board value, and a flat 40-VP constant;
it has no notion of how likely it is to win, so every one of those four
becomes a constant where the truth is a function.

That is now the largest single missing piece, ahead of the hand planner,
and it is cheaper than it sounds: the benchmark already plays thousands of
games from known positions, so a first estimator could be fitted from
recorded play rather than derived -- board value and VP margin and turn
in, win frequency out. It would replace a constant in at least four
places, and it is the one thing that makes Late War card values
expressible at all.
