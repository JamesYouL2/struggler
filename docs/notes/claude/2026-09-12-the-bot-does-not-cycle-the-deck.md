# The bot does not cycle the deck, and the third scoring is rarer than it looks

Two corrections from the maintainer, both of which shrink a finding I had
just recorded and point at a larger one behind it.

## The third scoring is rare, and the model prices it as certain

I recorded that `scoring_schedule` returns at most two entries -- `(0,
reshuffle)` -- so it can never price a third cycle, and that this
understates turn-1 urgency by about 9%.

The maintainer: "the third scoring just isn't very common because of the
game ending before late war and the t9 reshuffle."

Right, and the 9% figure is too high for a reason that generalises well
beyond this term. `scoring_schedule` caps its horizon at the end of the
game, but that cap is **hard**: a scoring within the horizon is priced as
certain. It is not. `FINAL_SCORING_ODDS` -- already in this file --
measures how often a game gets there at all, and from turn 1 it is
**0.222**. Games mostly end early on the 20 VP track.

So a third cycle from turn 1 needs the game to reach the second reshuffle
around turn 9, which happens in maybe half of games, and the term should
be weighted accordingly: roughly 4-5%, not 9%.

**The general defect is the inconsistency.** `_scoring_weight_uncached`
applies survival odds to exactly one term:

    total += w.scoring_final * final_scoring_odds(obs)

Every *other* future scoring in the same function is priced as certain if
it falls within the horizon. The machinery to do it right is already
imported and used one line away.

## Humans reshuffle at turn 7; the bot reshuffles at turn 9

The maintainer: humans get the second reshuffle at turn 7 almost always.
Measured here earlier, the bot's second reshuffle lands at turn 9 in 15 of
16 games.

The arithmetic behind that split was already worked out: at zero cards
leaving the game the pile after the turn-7 deal is **one card**, and any
removal rate of 1-3 a turn brings the reshuffle forward to turn 7. It is a
knife edge, and what tips it is how many cards leave the game entirely.

**Cards leave the game by being evented.** `remove_after_event` is true
for **70 of 110** cards, and **21 of the 35 Early War cards that can be
evented away at all -- 60%** (39 cards are Early War; the three scoring
cards and the China Card are not removals of this kind). A card spent for
its Operations is discarded and comes back; the same card evented is gone
for good.

And the bot spends for Operations. From the 2026-09-11 gate's card table,
across 78 seeds:

| mode | plays |
| --- | ---: |
| operations | 4943 |
| event | 993 |
| headline | 984 |
| space race | 195 |
| UN intervention | 106 |

Events plus headlines are **27%** of chosen plays; Operations are 68%. A
player who events more removes more, drains the pile faster, and reaches
the second reshuffle sooner.

So the chain is: **the bot events less -> fewer cards leave the game ->
the draw pile lasts longer -> the second reshuffle slips from turn 7 to
turn 9 -> fewer cards are cycled in a game.** Every step is measured
except the human event rate, which is the maintainer's observation rather
than a number in this repo.

### Why it matters beyond tidiness

- **It compounds with the third-scoring point above.** A bot that
  reshuffles at turn 9 instead of turn 7 gets *fewer* third cycles than a
  human does, so the term is rarer for this bot specifically than the
  general estimate suggests.
- **It is a plausible partial explanation for the ending-turn gap.** The
  bot's games run 8.00 turns against a human field's 6.81 and reach the
  Late War in 70% against 48%. A player who cycles the deck less sees
  fewer scoring cards per turn, and fewer scorings is a slower race to 20
  VP.
- **It may be a symptom rather than a cause.** The bot events 27% of the
  time because its event valuations say so. The card table already shows
  `The_Voice_Of_America` evented 38 of 38 times and `Pershing_II_Deployed`
  never spent for Ops -- so the bot does not lack the capacity to prefer an
  event. Whether 27% is too low is exactly the question the expert
  valuations exist to answer, and the cleanest test is not a gate but a
  comparison of the bot's event rate against a human field's.

**What to measure next, in order:** the bot's second-reshuffle turn and its
removal count per game are both one line of instrumentation in
`benchmark.play_game`, and neither costs a gate. Get those before touching
any valuation.
