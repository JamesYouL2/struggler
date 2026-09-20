# The VP curve's peak, on one block: 3.0 stays, and 4.0 is not better

2026-09-20. Run 35539441015, 4 arms x 1024 seeds (60000-61023) against
`07d553a`, all paired against the shipped setting, 32 shards, none stalled.

The grid that put `vp_swing` at 3.0 was stitched from two blocks: 1.5/2.0/3.0
on 46000-47023 and 4.0/6.0 on 52000-53023, each against *its own* base. So
3.0 and 4.0 -- the two candidates -- had never been compared with each other.
This asks that one question.

| arm | score | one-sided 95% | US seat | USSR seat | signed VP | nuked US/USSR |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `base` (3.0, as shipped) | **0.534** | [0.517, 0.551] | 0.588 | 0.479 | -1.12 | 27/17 |
| `vp2` (2.0) | 0.529 | [0.512, 0.546] | 0.585 | 0.472 | -1.02 | 30/22 |
| `vp4` (4.0) | 0.519 | [0.502, 0.536] | 0.588 | 0.450 | -1.46 | 19/21 |
| `vp5` (5.0) | 0.521 | [0.504, 0.538] | 0.590 | 0.451 | -1.77 | 25/27 |

| arm | minus base | one-sided 95% |
| --- | ---: | --- |
| `vp2` | -0.005 | [-0.022, +0.011] |
| `vp4` | **-0.015** | [-0.031, **+0.001**] |
| `vp5` | -0.013 | [-0.031, +0.004] |

## What it settles

**3.0 is the best of the four, and nothing here beats it.** All three
alternatives read negative against it. None is a measurable loss at the
gate's convention -- but `vp4` misses by a thousandth: its upper bound is
+0.001, which is as close to "measurably worse" as a reading gets without
being it.

So the answer to the question the arm was built for is **no**: 4.0 is not
better than 3.0, and the earlier appearance that it might be was the two
blocks, not the setting. `vp_swing` stays at 3.0, now for a reason that does
not depend on stitching.

**The peak is flat on the low side and falls on the high.** 2.0 costs
0.005 and 4.0 costs 0.015, three times as much, for the same distance from
3.0. Whatever the curve is doing, overshooting is worse than undershooting.
5.0 is not worse than 4.0 (-0.013 against -0.015), so the fall is not
monotone past the peak either; at these interval widths that difference is
noise and should not be read as a second peak.

## The part worth keeping: it is all in the USSR seat

| | US | USSR |
| --- | ---: | ---: |
| spread across the four arms | 0.585 - 0.590 | 0.450 - 0.479 |

**The US seat does not move at all** -- five thousandths across a setting
that ranges from 2.0 to 5.0 -- and the USSR seat moves by 0.029, six times
as much. Every bit of the VP curve's effect on strength is in the USSR
seat.

That is the same seat asymmetry that shows up in the nuclear-loss rate
(2026-09-18, drift), in the corner rate (2026-09-19, last-exit: USSR
cornered at median round 27 against the US's 61), and in the fitted-weight
intransitivity (2026-09-18: the whole -0.031 was USSR). Four independent
measurements now say the USSR seat is where this bot's remaining strength
lives. Any next weight question should be read per seat, and a term that
only moves the US seat is probably not the term to tune.

## A block check, for free

`base` reads **0.534 [0.517, 0.551]** here. The drift canary read main
against the same anchor at **0.534 [0.518, 0.550]** the same evening, on a
completely different block (6000-7023).

Two independent 1024-seed blocks agreeing to the thousandth is what the
level readings are supposed to look like. It also isolates which block was
the odd one: `sandbox-base`'s 0.559 on 54000-55023, not the 0.534s. That
strengthens rather than weakens
[the block caution](2026-09-20-status-and-what-to-run-next.md) -- one block
in five sitting 0.025 high is exactly the failure mode, and it is now
identifiable rather than merely suspected.

## What this does not say

Nothing here is a gain. The best arm is the one already shipped, so the run
bought a *negative* result: it closed a question rather than opening a
setting. The four arms all sit between 0.519 and 0.534 against `07d553a`,
which is where main already was.

And it says nothing about the curve's *shape*. `vp_swing` is one scalar on
a fixed curve; that 2.0 and 4.0 both lose to 3.0 bounds the scalar, not the
functional form.
