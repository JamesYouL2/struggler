# 2026-09-09 — The scoring horizon, and why the old weights were near a ceiling

The user's correction, which changed this fix substantially: **the old
weights are basically a maximum, because good players end the game early.**
Mostly by scoring 20 VP; also Wargames; also DEFCON suicide.

That is right, and it is measurable, because the engine already records why
each game ended and `benchmark --report` keeps it per game.
`scripts/game_endings.py` reads those reports. Over the 192 games of the
`8680865` gate, both seed ranges:

| How it ended | Games | Share |
| --- | ---: | ---: |
| 20 VP auto-victory | 129 | 67.2% |
| final scoring after turn 10 | 47 | 24.5% |
| Wargames | 14 | 7.3% |
| draw | 2 | 1.0% |
| DEFCON 1 | 0 | 0% |

Only **52.6%** of games reach turn 10 at all, and only 24.5% reach final
scoring. Per-turn survival runs about 0.88-0.93 from turn 6 on.

The part I had wrong: I first treated final scoring as guaranteed and
discounted it like a scheduled card scoring, at `0.8 ** (10 - turn)`. Against
the measured odds that is more than double from turn 8 on:

| Turn | P(final scoring \| alive) | `0.8 ** (10 - turn)` |
| ---: | ---: | ---: |
| 1 | 0.245 | 0.134 |
| 5 | 0.270 | 0.328 |
| 8 | 0.367 | 0.640 |
| 9 | 0.416 | 0.800 |
| 10 | 0.465 | 1.000 |

The measured curve is almost flat, which is the interesting part. It does not
climb toward certainty as the game runs on, because a game still alive on
turn 9 is usually alive *because* it is close, and close games still get
decided on VP during turn 10.

So the fix is two things, not one:

- **Cap the horizon.** A reshuffle two turns away on turn 9 predicted a
  scoring on turn 11. That one is unambiguous.
- **Price the end-of-game scoring at its odds**, `scoring_final` times
  `FINAL_SCORING_ODDS`, rather than as a certainty.

Iran's weight goes from a flat 1.800 on every turn to 2.04 rising to 2.22 by
turn 9, then 1.47 on turn 10 where the cap bites. Turn 10 ends up *below* the
old value, which is the user's point arriving in the numbers.

### Caveats on the calibration

- These are bot-vs-bot games, and a generous proxy. Strong human players push
  for 20 VP harder than this bot does, so the real odds of reaching final
  scoring are lower than 24.5%, and the correct `FINAL_SCORING_ODDS` is
  probably below this table. Codex has tournament statistics; replace the
  table when they land, and rerun `scripts/game_endings.py` to check the
  bot's own distribution against them.
- The table is measured from games the *current* bot played, so it moves as
  the bot changes. That is circular, but only weakly: the shape is driven by
  the 20 VP rule, not by this evaluator.
- `scoring_discount` (0.8 per turn) is doing survival duty for the card
  scorings, and the measured per-turn survival is 0.88-0.93, not 0.8. So the
  card terms are discounted harder than survival alone justifies. Leaving that
  alone: it is a tuned weight with its own gate history, and 0.8 also carries
  uncertainty about the board that far out. Worth revisiting as its own
  calibration, with the same script.

### Web search for human tournament data: what is out there

`twilight-struggle.com` is the International Twilight Struggle Community
site, with a competitive database of 30,000+ games since 2006 across 1,500+
players and 100+ tournaments. That is the right source. Its result pages did
not come back to an unauthenticated fetch, so I could not extract the
ending-type distribution from it. BoardGameGeek blocks fetches outright
(HTTP 403). What is easy to find is side win rates (roughly 53/46 to the US
with the +2 handicap among strong players, ~60% USSR without it), not game
length or ending type.
