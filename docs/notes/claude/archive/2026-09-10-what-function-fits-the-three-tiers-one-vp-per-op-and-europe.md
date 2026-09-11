# What function fits the three tiers: one VP per Op, and Europe is not special

Asked what function fits Presence, Domination and Control together. Every
region's three tiers were priced as (Ops to reach the tier uncontested, VP
received including the 10.1.2 bonuses), giving 18 points.

**First answer, and it was wrong.** Using the *minimum* Ops -- the
cheapest country for Presence, the cheapest Battleground plus cheapest
non-Battleground for Domination -- the best fit was strongly concave,
`VP = 3.30 * sqrt(Ops)`, and a constant VP-per-Op model was three times
worse. The maintainer: "consider avg ops, not minimum." That concavity
was an artifact: taking the cheapest country makes the low tiers look
artificially cheap, and the low tiers are where the curvature came from.

**On average Ops the relationship is linear with slope one.**

| Fit | Mean abs error | Max |
| --- | ---: | ---: |
| linear `1.76 + 0.83*Ops` | 1.11 VP | 2.64 |
| power `1.27 * Ops^0.94` | 1.25 VP | 4.25 |
| **proportional `1.00 * Ops`** | 1.42 VP | 3.46 |
| sqrt `3.17 * sqrt(Ops)` | 1.40 VP | 2.93 |

The power fit's exponent is **0.94** -- near enough to 1 that the honest
reading is a straight line. So, over eighteen points spanning three tiers
and six regions:

> **A region pays about one VP for each Op of stability you have to buy to
> reach a tier.**

Two parameters buy little: the linear fit's 1.76 intercept is the fixed
bonus for entering a region at all, and its slope drops to 0.83 to pay
for it. `VP = Ops` is one number and within half a VP of the two-parameter
fit on average.

**This reconciles with the 2-Ops-per-VP rate rather than contradicting
it.** These Ops are the *uncontested* cost of control. Real games are
contested, so if taking a country actually costs about twice its
stability, the realised rate is the familiar 2 Ops per VP -- and the
reason to play the board rather than buy VP directly is that the board
pays double when the opponent lets you have it.

**And Europe is an ordinary region on this curve.** At its printed
Control value it is 13 VP for 15 Ops, against a predicted 15.0 -- and
every region sits between 0.92x and 1.18x of the curve. The scoring
table is internally consistent and Europe is not special in *scoring*
terms at all. Its premium is entirely the automatic victory, which is why
`Europe Control = 40` sits 3.6x off the curve, and why the maintainer
corrects the earlier "3.5x" reading to about **1.67x**: that implies an
effective Europe Control of roughly 15 VP, not 40. The 40 is what it is
worth when it happens; the 1.67x is what it is worth to chase.

**What this says about the bot.** `importance` is
`w.battleground * urgency` -- one constant per region, flat across
Battlegrounds, with no dependence on how many Ops the region absorbs. The
data says value tracks Ops-to-take almost exactly. A region weight
proportional to its summed stability, plus a separate Europe premium of
about 1.67x for the win threat, is a better starting shape than six free
constants -- and it has one parameter instead of six.
