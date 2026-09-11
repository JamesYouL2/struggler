# P(SEA scores) is ~0.95; the discount is in the payout, not the odds

The maintainer: "P(SEA scores) is at least .9, almost certain it's .95.
It's just E(Scoring) that's much lower."

Measured: **11 of the first 12 games, 92%**, run still going.

Which corrects the formula from two sections up. It was written as
`P(SEA scores) * 4 VP`, with the discount carried by P. P is nearly 1, so
that form would price Thailand's Southeast Asia contribution at almost its
full 4 VP swing. The discount belongs in the *payout*: whether you still
hold the country when it scores, what else you hold in the subregion, and
which turn it lands on.

**And that is not a constant to be supplied -- it is a position, which the
evaluator already computes.** So the right implementation adds no new
number at all:

```
Southeast Asia contribution = 0.95 * (Southeast Asia VP swing on this board)
```

with the swing read off the position exactly as the six tiered regions
already are. One measured constant near 1, and no per-country table.
