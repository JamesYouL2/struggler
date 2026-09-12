# `access` should be a conversion probability, not three guessed weights

The maintainer: *"Access probably stays but should be a formula with a
math basis."*

It should, and the basis is the one already chosen for everything else.
Under `value x probability x turn_discount`, a holding's reach is not a
separate kind of quantity -- it is the same product applied to a country
we do not hold yet, with the probability term doing the work.

## What it is today

Three weights, all `guess / underdetermined` in `models/provenance.json`:

    access            1.5    master multiplier, applied in country_value
    access_redundant  0.35   another holding already reaches it
    access_contested  0.25   the opponent reaches it too

and the term itself:

    total += weight * importance(t, w, urgency, n) / stability[n]

So: a tier value, divided by stability, scaled by whichever of two flat
constants applies. Nothing in it is derived.

## What it should be

A stake in country `i` is worth the *option* it creates on an adjacent
uncontrolled battleground `n`: the chance of converting reach into control
before `n` next scores.

    access(i, n)  =  VP(n)  x  dP(control n | we hold i)  x  discount(n)

`VP(n)` is factor 1 -- the rules' VP for controlling `n`, from rule 10.1.2
and the tier it swings, exactly as for a country we already hold.
`discount(n)` is factor 3, already in the model. So the whole of `access`
reduces to **one new quantity**: `dP`, the marginal probability that this
holding converts.

## The marginal probability, and why two of the three weights disappear

Let `p` be the probability that one route -- one adjacent holding --
converts into control of `n` before `n` scores. With `k` routes already in
place,

    P(control n)  =  1 - (1 - p)^k

so the marginal value of adding one more route is

    dP  =  (1 - p)^k - (1 - p)^(k+1)  =  p (1 - p)^k

The first route is worth `p`; the second `p(1-p)`; the k-th
`p(1-p)^(k-1)`.

**That is what `access_redundant` is.** The ratio of the second route to
the first is exactly `1 - p`. It is not a taste parameter: the shipped
0.35 asserts `p ~ 0.65`, a claim about how often reach becomes control,
which is measurable and has never been measured.

It also shows the current term is wrong in a way a flat constant cannot
fix: every redundant route gets the same 0.35, where the formula says the
k-th is worth `(1-p)^(k-1)`, decaying. The third and fourth directions
into the same battleground are over-valued, and the code cannot express
the decay because it has one constant, not a rate.

`1 / stability[n]` is the current proxy for `p` -- harder countries
convert less often -- and the instinct is right. The formula makes it
explicit: `p` is a function of stability and of the influence already
present, not a separate divisor multiplied by a flat weight.

`access_contested` is the same story from the other side. If the opponent
converts with probability `q`, our chance of ending up in control is
reduced accordingly; 0.25 asserts a large `q` and asserts it as a
constant, when it is a function of their influence and Ops just as `p` is
a function of ours.

And `access = 1.5`, the master multiplier, is the same shape as
`region = 1.3`: an exactly-derivable VP quantity scaled by a guess. At par
it is 1.0.

## Measured, 2026-09-12

`scripts/measure_access_conversion.py`, 16 self-play games, 688 resolved
opportunities. An opportunity is opened once per turn per (side,
battleground) where the side holds a neighbour and does not control it, and
resolved when that battleground's region next scores -- the horizon the
value function prices against, since a battleground pays at scoring and not
before.

| stability | n | p |
| ---: | ---: | ---: |
| 1 | 57 | 0.456 |
| 2 | 221 | 0.344 |
| 3 | 288 | 0.306 |
| 4 | 122 | 0.180 |
| **all** | **688** | **0.308** |

**`p` is a function of stability, monotonically, across a 2.5x range.** That
is the derivation's central claim and it survives measurement: no constant
can express this column.

Two things follow, and both say the shipped term is wrong.

**`access_redundant` should be about 0.69, not 0.35.** It is `1 - p`, and
`p = 0.308`. The shipped 0.35 encodes `p ~ 0.65` -- the conversion rate
roughly inverted, undervaluing a second route by half.

**`1/stability` is too steep as the proxy for `p`.** Normalised it decays
1.0 / 0.50 / 0.33 / 0.25, a 4x fall; measured `p` decays 1.0 / 0.75 / 0.67 /
0.40, a 2.5x fall. Fitting the exponent gives `p ~ stability ** -0.67`, not
`** -1`. High-stability countries are penalised harder than their actual
conversion rate warrants.

### And the loop has to count k

The maintainer: *"It should be one number, of course... tuned
exponentially"* and *"we do need to count k"*.

Right, and that is a real change rather than a relabelling. `access()` today
asks a BOOLEAN -- is there another holding that reaches this -- and applies
the flat constant if so. The geometric form needs the number of existing
routes:

    route 1: p        route 2: p(1-p)        route k: p(1-p)^(k-1)

Summed over three routes the flat form pays `1 + 0.35 + 0.35 = 1.70`; the
geometric form at `p = 0.308` pays `0.308 * (1 + 0.692 + 0.479) = 0.67`.
Different by 2.5x, and diverging further the more routes exist.

### The caveat this number carries

`p` is measured from THIS BOT PLAYING ITSELF, so it is the rate this bot
converts reach into control -- a descriptive rate being used as a
prescriptive weight. A stronger bot would convert more, which would justify
valuing reach more, which would change how it plays. That circularity is
real and unavoidable at this stage; it is still far better than a guess, and
the stability curve is the part least likely to be an artifact of it.

Opportunities that never resolve -- the region does not score again before
the game ends -- are dropped, which biases toward regions that score.

## What this buys

Three guessed, underdetermined weights collapse to **one measurable
function**, `p(stability, influence)` -- the per-route conversion
probability -- on top of the VP and discount the rest of the model already
supplies.

And `p` is measurable without any new machinery. From played games: given
we hold a neighbour of an uncontrolled battleground at turn `t`, how often
do we control that battleground by the time its region next scores? That
is a count over replays, not a gate, and it produces a curve in stability
rather than a number.

## Where this sits relative to the rest

`access_chain` is already gone -- ablated to 0.0 and its loop being removed
-- so this is about the first-hop term only, which is the cheap 8% of the
traversal rather than the 92%. That ordering was luck rather than
judgement, but it is the right one: the expensive half was removed on a
measurement, and the cheap half gets a derivation.

This is part of the rebuild, not a change to make first. It depends on
factor 1 (VP from the rules) and factor 3 (the bucketed discount) already
being in place, because `access` is those two multiplied by a probability.
Doing it before them would mean fitting `p` against a board value in
units that are about to change.
