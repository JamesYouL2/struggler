# VP are not linear, and two places are discontinuous

The maintainer: "the 20th VP is much, much more important than the 19th.
I guess the 20th VP, and the 6th and 7th VP in the Late War, are
discontinuously important. It's probably some kind of very sharp
exponential in early/mid war."

`vp_value` is **one price per VP per era** (`vp_early` 0.5, `vp_mid` 1.0,
`vp_late` 2.0), so the twentieth VP costs exactly what the first does.
Two discontinuities it cannot express:

- **The 20th ends the game.** Going +19 to +20 is winning; +18 to +19 is
  nothing. The auto-victory is a step, not a slope.
- **The 6th and 7th in the Late War are Wargames.** It ends the game and
  hands the opponent 6 VP, so at +6 you tie and at +7 you win. The
  seventh VP is worth the game and the sixth is worth a draw -- which is
  exactly the maintainer's earlier reading of Wargames as
  `(1 - win_pct) * game_value`, now placed on the VP curve rather than on
  the card.

And a convexity underneath both: being further ahead is worth more than
linearly, sharply so in the Early and Mid War. That is the same quantity
as win probability, which is what makes the previous section's directive
coherent -- a VP curve and a win-probability function are two
parameterisations of one thing, and calibrating either fixes both.
