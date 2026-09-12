# `vp_base` cannot fix the battleground level, and what that points at

The maintainer's target is that a turn-4 Battleground should read at
about 4 VP. It reads at 2.05. The obvious fix -- lower `vp_base`, the
level of the VP curve -- does not work, and finding out why located a
structural problem somewhere else.

## The measurement

2 Ops into the best empty stability-2 Battleground, `delta` divided by
`vp_value`:

| turn | per_vp | vp_value | delta | VP | country |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 0.500 | 16.36 | 56.95 | **3.48** | Egypt |
| 4 | 0.630 | 33.40 | 68.49 | **2.05** | Algeria |
| 8 | 0.857 | 50.72 | 76.46 | **1.51** | Algeria |
| 10 | 1.000 | 56.31 | 72.80 | **1.29** | Algeria |

**Caveat first, because it bounds what this can be used for:** the probe
forces `engine.turn` on an opening board, so these are not realistic
turn-4 or turn-8 positions -- no influence has been placed and nothing is
contested. It isolates the `per_vp` and urgency effects and nothing else.
The *direction* below is arithmetic and survives that; the magnitudes do
not.

## Why the level knob is the wrong knob

`vp_base` is a constant factor in `per_vp(turn) = vp_base * vp_swing **
((turn - 1) / 9)`. It multiplies every row of that table equally and
cannot change its shape. Setting it to put turn 4 at 4 VP requires

    vp_base = 0.630 * (2.05 / 4) / 2 ** (3/9) = 0.256

and that same factor puts **turn 1 at 6.8 VP**.

So the target is a claim about the shape as much as the level, and the
shape is going the wrong way:

    vp_value grows 3.4x across the game  (16.36 -> 56.31)
    a Battleground's delta grows 1.28x   (56.95 -> 72.80)

Battleground value in VP therefore *falls* by 2.7x over the game, and no
`(vp_base, vp_swing >= 1)` pair can reverse that -- a rising `per_vp`
only makes it fall faster. Reversing it would need `vp_swing < 1`, i.e. a
VP getting *cheaper* late, which contradicts both the scarcity fit and
the maintainer's stated reason for the curve.

## So one of two things is wrong, and they are not close together

**Either turn-1 Battlegrounds really are worth about 7 VP**, the level is
simply low everywhere, and `vp_base = 0.256` is right with the shape left
alone.

**Or the board side of the ratio is wrong** and a Battleground's `delta`
should grow far faster with turn than 28%. That points straight at
`battleground`, which `models/provenance.json` already records as one of
only two **known-wrong** constants, with the note that it "carries the
whole region model".

This is a maintainer question, not a measurement one: it asks what a
Battleground is worth in VP early versus late, which is Twilight Struggle
judgement. Recorded here so the `vp_base` entry in the provenance ledger
stops being read as a simple level correction -- its note currently says
"needs per_vp(4) near 0.29", which is true and not sufficient.

## What makes it answerable soon

Under the VP denomination the maintainer set out -- board, hand and deck
value all in VP, evaluated at par -- "a Battleground is worth X VP" stops
being a free parameter and becomes a claim checkable against what
positions actually score in self-play. That is the same argument as in
"Win probability is the objective; VP is the currency", and this is the
first concrete place it would pay.
