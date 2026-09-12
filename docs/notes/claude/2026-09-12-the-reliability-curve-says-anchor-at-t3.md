# The reliability curve, and why the headline number is the least trustworthy part of it

`scripts/vp_spread.py` was overnight.sh's step 8 and never ran -- the hang
blocked the queue at step 5. Run now over every VP trace on disk (the
2026-09-11 gate reports plus the 256-seed vp_swing run), **668 decided
games**:

| turn | n | P(US) | slope | spread | sd(swing) | per_vp |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 668 | 0.57 | sep | -- | 17.18 | -- |
| 2 | 668 | 0.57 | 0.048 | 20.76 | 16.97 | 0.0120 |
| 3 | 643 | 0.55 | 0.124 | 8.07 | 16.04 | 0.0310 |
| 4 | 624 | 0.56 | 0.126 | 7.93 | 15.03 | 0.0315 |
| 5 | 584 | 0.55 | 0.139 | 7.17 | 14.86 | 0.0349 |
| 6 | 542 | 0.56 | 0.136 | 7.36 | 14.32 | 0.0340 |
| 7 | 494 | 0.56 | 0.143 | 7.01 | 13.70 | 0.0356 |
| 8 | 434 | 0.57 | 0.156 | 6.40 | 12.44 | 0.0391 |
| 9 | 352 | 0.56 | 0.150 | 6.69 | 13.55 | 0.0374 |
| 10 | 279 | 0.58 | 0.151 | 6.63 | 13.98 | 0.0377 |

The script's headline is `spread(T2) / spread(T10) = 20.76 / 6.63 =
**3.13**`.

## The headline moved 35% on overlapping data

Last night the same fit over fewer games printed **2.32**. Tonight, with
the 256-seed run added, **3.13**. Nothing about the game changed; what
changed is how many games fell into the one turn the ratio is anchored on.

A number that moves that far when the sample grows is not measuring the
quantity it is named after. The instability has a single source, and the
table shows it.

## Turn 2 is not identified, and the whole headline rests on it

Turn 1 cannot be fit at all -- `sep`, the logistic separates, because
every game sits at the same VP. Turn 2 is the same problem one turn later
and only just barely fittable: its slope is **0.048**, a fifth of turn
3's 0.124, and spread is 1/slope, so a slope that small produces a spread
of 20.76 that towers over every other row.

From turn 3 the curve is well behaved and nearly flat:

    spread(T3) / spread(T10) = 8.07 / 6.63 = 1.22

So the two readings of the same table are **3.13** and **1.22**, and the
entire disagreement is whether turn 2 counts. It should not. At turn 2 the
VP track has barely moved, so regressing the winner on it is regressing on
noise; the fit returns a near-zero slope because there is nothing to fit,
not because a VP is genuinely worth a twentieth of what it is worth later.

## The play measurement agrees with the flat reading

If the true ratio were 3.13, then `vp_swing: 4.0` would be nearer right
than the shipped 2.0 and should have shown something over 256 seeds. It
measured **0.491 +/-0.026** -- no difference. That is weak evidence, since
the term looks close to inert for strength either way, but it points the
same direction as the T3 anchor and away from the headline.

## What follows

- **Anchor the fit at T3, not T2.** The T1 and T2 rows stay in the table
  as diagnostics and come out of the ratio. That is a change to
  `vp_spread.py`, and it is the only way this script stops printing a
  different answer every time it is run.
- **The supported value is about 1.2**, which is much closer to the
  queued `vp_swing: 1.0` experiment than to the shipped 2.0. That
  experiment is now the one worth running of the three that were queued,
  and it should be regression-gated rather than measured: the term is
  close to inert in play, so this is about the model being right, not
  about winning more games.
- **Do not quote 3.13 anywhere.** It is this note's whole point that the
  number is an artifact of the turn it is anchored on.

Two caveats the script states and this note inherits: late spreads are
conditioned on survival -- games that ended before turn `t` do not
contribute, and those are the swingiest -- and `n` falls from 668 at turn
2 to 279 at turn 10, so the right-hand rows are both thinner and
selected. Neither affects the T2 argument, which is about turn 2.
