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

**What it says about the plan.** Step 6 (joint space/hold allocation) was
motivated by hands with no exit. After steps 1-2 those are rare, so step 6
should be justified by what it wins in the 34% tail rather than by rescuing
the 3%. The instrument is the way to tell: run it before and after, and
watch the tail mass move, not the corner count.
