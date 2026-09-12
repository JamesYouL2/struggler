# Tournament-shaped stats, and where the bot field differs from a human one

The maintainer asked for the statistics a tournament reports: win rate by
side, when games end, and how. The harness already recorded every one of
them per game and aggregated none, so `summarize` now carries them and
every report and gate step prints them.

## What a tournament reports, and what we now report

| statistic | where it was | where it is now |
| --- | --- | --- |
| win rate by side | `game['winner']`, unaggregated | `wins_by_side`, `us_win_rate`, `draws` |
| how the game ended | `game['reason']`, read only by `scripts/game_endings.py` | `endings`, a count per reason |
| when it ended | `game['turn']` | `mean_end_turn`, `reached_late_war` |
| nuclear-war rate | counted, but only as a pass/fail input | in `endings` as `defcon_1` |
| score | printed bare | now with its interval, `score_halfwidth` |

Win rate is by **seat**, not by bot. This harness plays the same bot on
both sides, so a seat imbalance is a property of the game or of the bot's
grasp of one side -- and it hides completely inside a score of 0.500,
which is what the gate looks at.

## The first reading, 64 games, against the human reference in this repo

The human numbers are the ones already cited in
`bots/strategic/public_cards.py` (twstourney round 4, 27 games) and in
`benchmark.ACCEPTANCE` (WBC nuclear rates). Both are small and selected;
the 27-game sample is explicitly flagged in the source as needing broader
validation.

| | human field | this bot |
| --- | ---: | ---: |
| mean ending turn | 6.81 | **8.00** |
| reached the Late War (T8+) | 0.481 | **0.703** |
| ended at final scoring | 0.222 | 0.266 |
| ended by nuclear war | 0.054-0.117 | **0.156** |
| ended by Wargames | -- | **0.172** |
| US win rate | -- | 0.547 (35-27-2) |

Four things worth chasing, none of them yet explained:

**The bot's games run a turn longer than a human field's.** 8.00 against
6.81, and it reaches the Late War in 70% of games against 48%. Strong
players end games earlier, on the 20 VP track. This is the same shape as
the maintainer's reading of the nuclear rate -- that humans are *under*
tolerant of risk -- but pointed the other way: a bot that takes longer to
win is a bot that is not pressing.

**Wargames ends 17% of games.** That is one game in six ending on a card
that hands the opponent VP, and there is no human figure here to compare
it against. It may be correct -- Wargames at the right moment is a win --
or it may be the bot reaching for it because the value function prices
the ending and not the concession.

**The nuclear rate is above the human band**, 15.6% against 5.4-11.7%.
The maintainer's reading is that this is insufficient hand planning plus
humans being too risk-averse, and they have judged the rate solid; the
veto now sits at 25%. Recorded here because "blessed" is not "explained".

**The US wins 54.7%** with the +2 handicap that exists because the US is
considered the weaker seat. Either the handicap overcorrects in this
engine, or the bot plays the US side better. Both matter, because every
gate result averages the two seats and assumes they are symmetric.

## What this does not measure

All of the above is bot-against-bot. A tournament field is humans
against humans, so these are two different distributions and the
comparison is a sanity check, not a calibration. The one number that
would make it a calibration -- this bot's result against a human -- has
never been measured, and is why the version tags stay below 1.0.
