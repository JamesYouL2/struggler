# Step 4: when does a hand stop having an exit?

2026-09-19. The v3 plan's step 4, and the question the audit's G1 rests on.
A hand that is already cornered cannot be saved by playing the cornered
decision better -- the mistake, if there is one, is the play before it. So
the instrument does not ask "how risky is this hand"; it asks **when the
risk reached certainty, and what was played just before**.

`scripts/measure_last_exit.py` plays self-play games and, at every action
round, asks the planner for the whole-hand risk (`planner_for(obs).risk()`,
the same construction the bot uses -- one statement of the rule). It
records, per seat-game: the first round where the risk reaches `--cornered`
(1.0 by default), the play that preceded it, the highest risk ever seen,
and whether the game ended at DEFCON 1.

The denominator is the point. "How often is the bot cornered at all" is
what says whether the rest of the plan is worth building.

## First reading (32 seeds, 64 seat-games, after the hand-safety work)

| seat | ever cornered | max risk >= 0.25 | >= 0.90 | median max |
| --- | ---: | ---: | ---: | ---: |
| US | 0/32 (0.000) | 0.062 | 0.000 | 0.000 |
| USSR | 1/32 (0.031) | 0.344 | 0.031 | 0.000 |

- **Certain corners are rare and fatal.** One seat-game in 64 reached
  "every line loses", and it lost to DEFCON 1. A sample of one, so the rate
  is [0.006, 0.157] and the fatality is [0.21, 1.00]: what this supports is
  "rare", not a number.
- **The median hand is at zero risk.** The distribution is not a gradient
  the bot is walking down; it is flat at 0 with a tail.
- **The tail is the USSR's.** 34% of USSR seat-games touch 0.25 against 6%
  of US ones, which is the same seat asymmetry the nuclear rate shows
  (docs/notes/claude/2026-09-18-drift-located-at-v0.2.1-v0.2.3.md: the USSR
  seat loses to DEFCON 1 far more often in every version).

## The reading that matters (128 seeds, 256 seat-games)

| seat | ever cornered | DEFCON 1 if cornered | DEFCON 1 if not | max risk >= 0.25 | median round |
| --- | ---: | ---: | ---: | ---: | ---: |
| US | 2/128 (0.016) | **2/2** | 6/126 (0.048) | 0.211 | 61 |
| USSR | 5/128 (0.039) | **5/5** | 3/123 (0.024) | 0.336 | 27 |

- **Every cornered seat-game lost to DEFCON 1. Seven for seven.** The
  intervals are wide on five and two cases ([0.57, 1.00] and [0.34, 1.00]),
  but the point estimate is not the interesting part: not one cornered game
  escaped.
- **Corners explain 44% of the nuclear losses.** 16 seat-games ended at
  DEFCON 1 and 7 of them were cornered first, against a 3.6% base rate in
  games that never were. Being cornered is not a symptom of a losing
  position; it is most of the mechanism.
- **The USSR is cornered earlier.** Median round 27 against the US's 61 --
  it walks into the trap in the mid-game, where the US only reaches it at
  the end.
- **The tail is wider than the corner rate.** A fifth of US seat-games and a
  third of the USSR's touch 0.25 without ever closing out.

**What it says about the plan.** Step 6 (joint space/hold allocation) was
motivated by hands with no exit. Those are rare after steps 1-2 -- 2.7% of
seat-games -- but they are *lethal without exception*, and they account for
nearly half of all nuclear losses. So the case for step 6 is not that it
rescues cornered hands; it is that 2.7% of seat-games are lost outright to a
mechanism that a better allocation of exits might avoid entering, and a
further third of USSR games come close enough to be worth measuring.

Run this before and after step 6, and watch two numbers: the corner rate
(should fall) and the tail mass at 0.25 (should thin). The corner count
alone is too small a sample to move visibly at 128 seeds.
