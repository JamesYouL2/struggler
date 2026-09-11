# Win probability: the shape, and the ceiling

The answer to the open question of what win probability should *do*, which
was the one thing I said I should not decide alone.

**Direction: variance is worth more when you are behind.** The maintainer:
"a 75% to win is definitely worth less when you're winning, you want to
take tons of DEFCON / Europe Control shots when behind." So a high win
probability lowers the value of a risky line and a low one raises it. The
bot has no such term: it prices a risky line the same whether it is ten
ahead or ten behind, which means it declines the shots that are the only
way back from a losing position and takes ones it does not need.

**Ceiling: win probability tops out around 0.75 to 0.90**, at the start of
a turn before cards are drawn, *even when far ahead on the board*, because
you cannot force a win and the opponent can always take shots at you. And
it is **asymmetric: lower for the USSR**, "because USSR has to die more."

That ceiling is the most useful part of the answer and the easiest to get
wrong. **A fitted estimator will happily report 0.99 from a dominant board
and be wrong**, and an over-confident estimator inverts the whole term:
the bot would stop taking shots exactly when a human would judge the
position not yet safe. Any estimator has to be clipped, not just fitted.

The USSR asymmetry is plausible and mechanically motivated but **not yet
measured**. What is on hand is weak: over the 192-game hunt, `defcon_1`
endings split 8 USSR to 5 US, and three explicit "USSR is responsible"
lines appear across the session's logs. Thirteen events is not a result.
Worth measuring properly before the asymmetry is built in, since it is a
per-seat constant and those are exactly what the mirror gate cannot see.
