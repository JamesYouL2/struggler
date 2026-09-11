# The scale invariance, stated properly -- and what it makes unbuildable

Astra's algebra, which is not a model of the ranking but literally
`safety_key`:

```
V_vp   = e * O                 vp_value  = era multiplier x best one-Op value
V_game = 40 * e * O            game_value = GAME_SWING_VP x vp_value
Q      = (1-r) * S - r * (40 e O)        the ranking key, policy.py:665
```

Divide by `O > 0`, which preserves order:

```
Q/O = (1-r)(S/O) - 40 e r
```

**So any change that scales both the action value `S` and the one-Op
reference `O` leaves the ranking alone.** Not a hypothesis: raising
`battleground` from 5.0 to 40.0, an eightfold change, moved the measured
Battleground swing from 1.08 VP to 1.10.

Three consequences, and the third is the one that matters.

**Only three things move the risk/value trade.** `e` (the era
multiplier), the constant 40, and `r` (the residual loss probability).
They survive the division; everything in the board weights does not.
That is why `vp_mid` was the *only* lever that moved the swing when I
swept for one, and it explains a run of null results tonight rather than
leaving them as coincidences.

**It predicts the `ops_value` change fails, and why.** Pricing an Op on
placement instead of the best coup lowers `O` roughly fourfold without
touching `S`, so `S/O` quadruples and value dominates risk four times
more. More risk-taking, more nuclear losses -- which is exactly how the
historical attempt failed (0.434, 13 nuclear losses) and how gate B
failed tonight (0.464, 21). Twice for the same algebraic reason.

**And it means the maintainer's turn-4 calibration is currently
unbuildable.** Its *scale* half -- an ordinary Battleground swinging 4 VP
where the bot measures 1 -- is expressed entirely in board weights, and
board weights cancel. There is no setting of `battleground` that
produces it. I spent a stretch tonight preparing to fit those numbers
without noticing that the fit could not take.

The relative half is not equally hopeless. A weight change is inert *to
the extent it moves the best available option*, so a region-specific
change (Europe up against Asia) shifts `O` far less than a global one
and should survive partially. That is testable and worth testing before
anyone assumes either way.

**Which reorders everything.** The dependency runs:

1. decouple `game_value` from `ops_value`, without the asymmetry that
   lost gate D on strength;
2. then board weights stop cancelling and the region calibration becomes
   implementable at all;
3. then `ops_value` on placement can be gated for its own merits rather
   than failing on a coupling.

And the maintainer's "20th VP" hypothesis is load-bearing for step 1: if
the 2x risk premium is really the auto-victory discontinuity, a convex
`vp_value` supplies it and `game_value` can stop being a flat multiple
of anything. Three changes that have each failed alone may only work
together.
