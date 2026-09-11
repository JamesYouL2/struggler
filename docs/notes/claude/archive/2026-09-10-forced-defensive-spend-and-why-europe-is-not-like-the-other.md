# Forced defensive spend, and why Europe is not like the other regions

The maintainer, correcting the Aragorn row rather than accepting it:
Europe's 4th Battleground is **2 VP plus about 2 Ops the opponent must
spend defending**, and at Mid War that is a lot. The 2 VP figure is not
wrong so much as half the quantity. And the reason it generalises to
*every* Europe Battleground, and to no other region, is Control.

Europe Control is an automatic loss for the opponent. So any credible
progress toward it **obliges them to spend Ops defending**, whether or
not you ever get there. Everywhere else Control is 5 to 9 VP --
unpleasant, survivable, and therefore optional to contest. That is the
asymmetry, and it is not in the tier structure at all: it is a cost
imposed on the opponent's *future turns*, not a change in what the region
scores.

So the region-margin specification gains a seventh element:

7. **Forced defensive spend.** Proportional to the credibility of your
   Control threat times what Control costs them. In Europe that is large
   for every Battleground; elsewhere it rounds to nothing.

Which also settles the "Europe's 4th is only 2 VP" reading I had checked
as internally consistent. I made it consistent by inferring a ~4% chance
of Europe Control -- the table silently embedding a probability. The
maintainer's answer is better: the threat pays whether or not it is
realised, because the defending Ops are spent either way. **A term keyed
on P(Control) alone would still be wrong; it has to charge for the
defence the threat forces.**

This is the third quantity found today that lives in turn order and
opponent obligation rather than on the board -- after the Military Ops
requirement and the DEFCON hand-off. The position evaluator cannot see
any of them, and that now looks like a category rather than a list.

**Calibration point agreed: start of turn 4.** Per-Battleground values
are to be defined there, which is exactly where all six regions first
weigh the same (Africa, Central and South America go 0.51 -> 0.80 ->
1.64 across turns 1, 3 and 4, matching Europe/Asia/Middle East). Turn 4
is the one board on which a single flat table is even coherent.
