# The Battleground scale, measured: the bot is 4x low, 5x flat, and orders it wrong

The per-Battleground question finally asked in the right units. Flipping
one Battleground from USSR control to US control, and measuring the whole
board value in VP (seed 4002, start of turn 4, all seven scoring cards
live):

| Region | Mean swing | Range |
| --- | ---: | --- |
| Africa | **1.32** | Angola 1.37 … Nigeria 1.24 |
| South America | 1.30 | Chile 1.36 … Brazil 1.26 |
| Central America | 1.11 | Cuba 1.13 … Panama 1.09 |
| Asia | 0.99 | Thailand 1.32 … Pakistan 0.89 |
| **Europe** | **0.98** | West Germany 1.05 … East Germany 0.89 |
| Middle East | 0.91 | Iraq 0.93 … Libya 0.88 |

The maintainer's answer, same board: **a Battleground is worth at least 4
VP** at turn 4 unscored, the spread between best and worst is **2 to 3
VP**, and the order is **Europe top, South America and Asia second,
Middle East and Central America least**.

Three separate defects, and they are independent of each other:

1. **Scale.** Every Battleground on the map swings about 1 VP where it
   should swing 4 or more. Four times low.
2. **Spread.** The bot's whole map spans 0.88 to 1.37, a range of 0.49 VP,
   against a stated 2 to 3. Five times too flat. Thailand is the only
   country anywhere that stands out, and only because Southeast Asia
   Scoring counts it twice.
3. **Order.** The bot ranks **Africa first and Europe fifth of six**. The
   expert ranks Europe first and Africa in the middle. Central America is
   third for the bot and last for the expert. This is not a
   miscalibration; the ranking is close to inverted at the top.

The third is the one that cannot be fixed by tuning, and the reason is
structural. A Battleground's importance is `w.battleground * urgency`,
and `urgency` is built *only* from how soon and how often the region will
score. It has no term for what Control is worth when it arrives, so
Europe -- where Control ends the game -- cannot rank above a region that
merely scores more often. Africa comes first because it has five
Battlegrounds and cheap tiers, not because anyone thinks it matters most.
**Europe's premium has to enter as its own term**, which is the same
conclusion the forced-defensive-spend section reached from the other
direction.
