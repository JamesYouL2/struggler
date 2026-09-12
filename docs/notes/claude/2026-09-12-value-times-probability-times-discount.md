# Board value is three variables per battleground

The maintainer, settling the battleground pricing:

> "The battleground VP value formula needs to be reworked... Need to have 3
> total variables for calculating total value... This was value *
> probability * turn discount... For each bg... And sigma over all possible
> scorings in the future. That is the total value."

So the whole of board value is one double sum:

    total_value = SUM over battlegrounds
                    SUM over every future scoring that can still happen
                      value  x  probability  x  turn_discount

Three factors, each with one job, summed over every (battleground,
scoring) pair the rest of the game can still produce. Each factor is
currently in a different state of repair.

**The outer shape already exists.** `_scoring_weight_uncached` is exactly
that double sum:

    for card in scoring_cards_for(country):
        for turns in scoring_schedule(obs, card):
            total += w.scoring_discount ** turns * (...)

It iterates the scoring cards that count a country and, for each, the
turns at which it can still score. What it accumulates is
`turn_discount` alone. Multiply each term by factor 1 and factor 2 and
this loop *is* the maintainer's formula -- the structure is right and two
of the three factors are missing or guessed.

## The two factors are cleanly separable, and both change meaning

The maintainer, sharpening it:

> "Importance is really vp value for one scoring."

So factor 1 is **per scoring event**, not an aggregate. That splits the
contribution exactly:

    contribution(bg) = importance(bg)          x   urgency(bg)
                       VP for ONE scoring          SUM over buckets of
                       (derived from the rules)    P(bucket) x discount(bucket)

Both halves change meaning from what they are today. `importance` stops
being a guessed board-unit tier and becomes a VP amount the rules fix.
`urgency` stops being a bare sum of discounts and becomes an expected
number of *discounted, probability-weighted* scorings -- dimensionless, so
the product is in VP.

## The five buckets, and which exist

> "You need to have terms for scoring this turn, scoring before reshuffle
> not this turn, scoring after reshuffle, scoring after reshuffle 2, and
> final scoring."

| # | bucket | expressible today? |
| --- | --- | --- |
| 1 | scores **this turn** | no -- conflated with 2 |
| 2 | before the reshuffle, **not** this turn | no -- conflated with 1 |
| 3 | after reshuffle 1 | yes, `turns_to_reshuffle` |
| 4 | after reshuffle 2 | **no -- cannot be expressed at all** |
| 5 | final scoring | yes, but outside the sum |

`scoring_schedule` returns at most two entries:

    schedule = (0,) if once else (0, reshuffle)

- **1 and 2 are the same entry.** `turns = 0` means "this cycle", which
  merges "must be played this turn" with "may come later before the
  reshuffle". The distinction is real and sharp, not a refinement: scoring
  cards cannot be held past the end of a turn, so a scoring card *in hand*
  has P(scores this turn) = 1, while one still in the pile does not.
  `2026-09-12-the-reshuffle-is-where-the-information-is.md` found the same
  edge from the other side -- a scoring card in the turn-2 remnant is dealt
  on turn 3 and must be played that turn, so its true "scores this turn"
  probability is near 1 against the 22.9% the uniform model assigns it.
- **Bucket 4 does not exist.** Two entries is the maximum, so the second
  reshuffle is unreachable, and the measured bucket masses say a third
  cycle carries a full 1.0 of expected scorings at turn 1.
- **Bucket 5 is computed but lives outside the sum**, as
  `w.scoring_final * final_scoring_odds(obs)` -- and it is the only bucket
  that currently carries a probability at all. It is also the only one
  whose mass rises monotonically across the game (0.222 -> 0.750 -> 1.0),
  which is what makes it the only term able to make board value rise late.

So the five-bucket structure is not a re-parameterisation of what is
there. Two buckets are fused, one is unreachable, and one is outside the
sum.

## Factor 1: value -- the VP it pays. Derived, not guessed.

Today this is `w.battleground = 5.0`, inside
`evaluator.importance()`, in board units:

    importance(i) = (w.battleground if battleground else w.control) * urgency[i]

It is the only one of the 31 weights `models/provenance.json` rates
**known-wrong**, with three recorded symptoms: a battleground swings ~1 VP
of board value where the maintainer puts the floor at 4, the whole map
spans 0.49 VP against a stated 2-3, and the region order is inverted at the
top (Europe 5th of 6).

**The rules already determine this number and the code already computes
it.** `evaluator.region_vp` reproduces `Board.score_region` exactly -- there
is a test, `test_region_vp_matches_the_engine_region_scoring` -- and its
per-country term is

    bonus = is_bg + (i in home[1 - holder])

which is rule 10.1.2: **1 VP for each controlled battleground, plus 1 VP
for each controlled country adjacent to the enemy superpower**, on top of
the presence/domination/control tier.

So `w.battleground` is a second, guessed pricing of a quantity the model
computes exactly twenty lines away. That is shape 4 -- two implementations
of one rule -- at the level of the value model rather than the code. The
rework is to take factor 1 from the rules: 1 VP for the battleground, 1
more if it is adjacent to the enemy superpower, plus the tier VP its
control actually swings.

And `region_vp` enters `board_value` multiplied by `w.region = 1.3`. An
exactly-known VP quantity scaled by a guess. At par that coefficient is
1.0.

## Factor 2: probability -- currently missing

This is the factor with no implementation at all, and it is the one the
handoff already ranked first among open items.

`_scoring_weight_uncached` applies survival odds to **exactly one term**:

    total += w.scoring_final * final_scoring_odds(obs)

Every other future scoring inside the horizon is priced as **certain**.
`scoring_schedule` caps at the end of the game, but the cap is hard: a
scoring one turn inside the horizon counts at full weight, and
`FINAL_SCORING_ODDS` says a turn-1 game reaches final scoring **22%** of
the time. Games mostly end early on the 20 VP track.

There are two probabilities here and the model has neither in general:

- **P(the scoring happens)** -- that the card is played, and the game
  reaches that turn at all. `FINAL_SCORING_ODDS` is this quantity measured,
  for one scoring.
- **P(we still hold it then)** -- the position is not static between now
  and the scoring. `wipe_risk` is a one-round version of this and is not
  connected to the schedule.

## Factor 3: turn discount -- present, and being calibrated now

`scoring_discount ** turns`, from `scoring_schedule`. This is the one
factor that exists and behaves. `scoring_discount = 0.8` is
guess/underdetermined, and the 0.55 arm is in the morning queue as this is
written.

Worth noting: factors 2 and 3 have been doing each other's work. A
discount raised to a power is not a probability, and pushing the discount
steeper has been the only available way to express "that scoring may never
happen". Once factor 2 exists, factor 3 should be calibrated again -- the
value that fits today is fitting two effects at once.

## What this reorganises

Three things that were being tracked as separate problems are one problem:

| tracked as | is really |
| --- | --- |
| `battleground` is known-wrong | factor 1 is a guess where the rules are exact |
| `scoring_schedule` prices scorings as certain (handoff open #1) | factor 2 does not exist |
| `scoring_discount` is underdetermined | factor 3 is absorbing factor 2's job |

And it explains why `vp_base` could not fix the battleground level
(`2026-09-11-vp-base-cannot-fix-the-battleground-level.md`): `vp_base` is a
constant factor, so it scales all three at once, and the defect is in one
of them.

## Order to build it

1. **Widen `scoring_schedule` to the five buckets.** Nothing else can be
   built until the sum can name its terms: today two of them are fused,
   one is unreachable and one is outside the sum. This step is pure
   plumbing and can be made behaviour-preserving -- bucket 1 + bucket 2 at
   equal probability and the old discount reproduces today's numbers
   exactly, which makes it checkable against the parity corpus before any
   pricing changes.
2. **Factor 1**, because it is derivable and needs no measurement: take the
   battleground's VP-per-scoring from `region_vp`'s own accounting rather
   than from `w.battleground`, and put `region` at par. This is where the
   known-wrong reading gets fixed.
3. **Factor 2**, the probabilities, one bucket at a time. Bucket 1 is the
   sharpest and the cheapest: a scoring card in hand scores this turn with
   probability 1, because scoring cards cannot be held. Bucket 5 already
   has its measured odds. Buckets 2, 3 and 4 need the deck model that
   `public_cards.py` now has the inputs for.
4. **Factor 3 last, recalibrated**, once it is no longer standing in for
   factor 2. The 0.55 arm running now is measuring the *current* meaning of
   the parameter and should be read as a reading of the old model.

Every step changes every ranking, so each one re-captures the parity
corpus. The corpus is the exactness oracle and re-capturing it is an
explicit, reviewed commit: measure the delta before overwriting the
baseline. That cost is why this is staged rather than done at once -- and
it is also why the `vp_swing` deletion, which is waiting for the next
regen, should ride along with step 1.
