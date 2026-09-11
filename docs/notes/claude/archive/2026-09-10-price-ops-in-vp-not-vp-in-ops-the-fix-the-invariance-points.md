# Price Ops in VP, not VP in Ops -- the fix the invariance points at

The maintainer: "maybe ops value needs to be calculated by VP... that's
actually how most players think about it."

That inverts the dependency, and it is what breaks the invariance rather
than working around it.

**Today, VP is priced from the board.** `vp_value = e * ops_value(1)`,
and `ops_value` is the best action the board offers. So the unit of
account is "what an Op buys here", which is itself a board quantity --
there is no absolute anchor anywhere in the system, and
`game_value = 40 * e * ops_value(1)` inherits that. Everything floats
together, which is precisely why `Q/O` eliminates the board weights.

**Proposed: VP is the anchor and Ops are priced in it.** Board terms
are denominated in VP directly; `ops_value(n)` becomes "the VP that n
Operations buy on this board", a derived quantity rather than the unit.
`game_value` becomes a number of VP -- 40, or `20 - vp` -- that does not
reference the board at all.

**The invariance breaks, which is the point.** With `V_game = G` fixed
in VP rather than `40eO`:

```
Q/O = (1-r)(S/O) - r * G/O
```

Scaling every board weight by `k` scales `S` and `O` together, so `S/O`
holds -- but `G/O` falls by `k`. The risk term shrinks as the board
grows. **Board weights stop cancelling**, which is exactly what the
turn-4 calibration needs in order to be expressible at all.

**Two things may fall out for free.**

The **era rates** (`vp_early` 0.5, `vp_mid` 1.0, `vp_late` 2.0) exist to
convert between the two units. If board value is already VP, an Op is
worth more early because there is more to take, not because a constant
says so -- the rate becomes emergent. Worth checking against the
measured 1.76 Ops per VP before assuming it.

And the **coup anchor** stops mattering as a yardstick. A cheap Nigeria
coup would still be the best available Op, correctly, but it would no
longer set the price of a VP for every other decision in the position.
The thing that made the yardstick move goes away rather than being
tuned around.

**Cost, honestly.** Every board weight is currently denominated in Ops
and would need re-expressing -- which is what the maintainer's turn-4
table supplies, so the recalibration and the re-denomination are one
job rather than two. The parity corpus moves wholesale. And the
documented `coup -> vp_value -> ops_value -> coup` cycle disappears,
which is a simplification but invalidates the reasoning in
`tests/test_order_independence.py` that currently justifies fixing the
VP price once per decision.

This supersedes the three-step order in the section above. It is not a
bigger change than those three together; it is the same change, done at
the root instead of three times at the branches.
