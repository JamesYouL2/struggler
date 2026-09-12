# The Ops-to-VP rate is a parameter, and the rule cannot be expressed

The maintainer: *"We need to make ops_value carry the spread difference,
not vp value. The conversion rules are about ops value changing, not vp
value. This is super important."*

Measured directly, on all 444 corpus positions, at each record's own
captured weights. And the answer is not that the model has the conversion
calibrated wrongly. It is that the model cannot express the question.

## The measurement

| turn | n | `ops_value(1)` | `vp_value` | VP per Op |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 119 | 24.1966 | 12.0983 | 2.000 |
| 3 | 109 | 19.2688 | 11.2388 | 1.714 |
| 5 | 80 | 31.6802 | 21.5550 | 1.470 |
| 7 | 90 | 16.4279 | 13.0388 | 1.260 |
| 9 | 46 | 28.0083 | 25.9322 | 1.080 |

## The right-hand column is an identity

`vp_value` is *defined* as `per_vp * ops_value(1)`. So

    VP per Op  =  ops_value(1) / vp_value  =  1 / per_vp

exactly, and `per_vp = vp_base * vp_swing ** ((turn - 1) / 9)` is a pure
parameter. Evaluated at the old `vp_swing = 2.0`, `1/per_vp` is 2.000,
1.714, 1.470, 1.260, 1.080 -- the measured column to three decimals.

**So the model's Ops-to-VP rate carries no information from the board at
all.** It is the parameter, read back. Measuring it was circular, and an
earlier claim in this repo's notes that "`ops_value` is inverted, rising
1.70x where the rules say it should fall 4x" was reached through that
circle and is withdrawn. The direct reading of `ops_value(1)` in board
units is a 1.16x rise from turn 1 to turn 9, and it is noisy and not
monotonic (24.2, 19.3, 31.7, 16.4, 28.0) -- a quantity in board units,
which are not VP, and so not an answer to the conversion question either.

## Which makes the maintainer's rule structurally inexpressible

The rule -- 1 Op = 2 VP in the Early War, 2 Ops = 1 VP in the Late War --
says VP per Op falls from 2.0 to 0.5. Under `VP per Op = 1 / per_vp` that
requires `per_vp` to rise from 0.5 to 2.0, which is

    vp_swing = 4.0

exactly the 4x the retired three-step era rates implied. So the rule does
not merely *prefer* a curve on the VP side; under this structure it **is**
one, and there is nowhere else to put it. `ops_value` cannot carry the
conversion, because the conversion is applied to `ops_value` rather than
derived from it.

That is the whole difficulty, and it is why this is a rebuild:

- **The expert rule demands `vp_swing = 4.0`.**
- **The measured decisiveness curve demands about 1.0** -- spread(turn) is
  flat from T3 (8.07 -> 6.63, a ratio of 1.22 over 668 games).
- **Play cannot tell them apart.** 4.0 measured 0.491 +/-0.026 over 256
  seeds; 1.0 measured 0.497 +/-0.072 over 78.

Three sources, two of them 4x apart, and the game indifferent to which is
chosen. A parameter that can be moved 4x without measurable effect is not
carrying the effect anyone thinks it is.

## What shipping 1.0 did, stated plainly

`vp_swing` is 1.0 as of today, so `per_vp` is constant and **VP per Op is
now flat at 2.00 for the whole game**, against the rule's 2.0 -> 0.5. At
turn 10 the model says an Op buys 2 VP where the maintainer says it buys
0.5: a 4x disagreement, and it is now the same at every turn rather than
closing as the game goes on.

This is not an argument against the change. The reliability curve and both
play measurements support flat, and `expert_valuations_latewar.json`
already recorded the tension when the value was 2.0 ("either event-granted
VP does not convert at the same rate as VP bought with Ops, or..."). It is
an argument that the disagreement is *structural* and cannot be settled by
choosing a number: whichever value is picked, one of the three sources is
contradicted.

## What the rebuild has to change

For `ops_value` to carry the era swing, board value has to be denominated
in VP to begin with -- so that what an Op buys is a VP quantity read off
the board, not a board-unit quantity converted by a free parameter. That
is exactly what `2026-09-12-value-times-probability-times-discount.md`
describes: `region_vp` at par, the battleground's VP taken from rule
10.1.2 rather than from `w.battleground`, and the sum over buckets
carrying probability. Once board value is in VP, `ops_value` is in VP per
Op by construction and the conversion stops being a parameter.

**The test the rebuild must pass** is this table. Re-measured afterwards,
VP per Op should fall across the game *because the board says so* --
because a late Op buys fewer expected future scorings, each less likely to
arrive -- and not because a curve was fitted to make it do that. If it
comes out flat again, the rebuild has not moved the thing it was for.
