# What a random move costs

`LLMPlayer` retries once on an invalid response and then falls back to a
RANDOM LEGAL MOVE (`bots/llm/player.py`, `_MAX_RETRIES = 1`). So a model's
schema-failure rate is not a nuisance rate -- it is a rate of random moves,
and "is this cheap model good enough" is partly a question with no model in
it at all.

`scripts/measure_noise_cost.py` plays the strategic bot against a copy of
itself whose decisions are replaced, with probability `q`, by a uniform
choice among the legal options. 32 games per rate, both seats, seeds
4000-4015, 2026-09-12:

| q | score | +/- | mean turn reached |
| ---: | ---: | ---: | ---: |
| 0.00 | 0.500 | 0.173 | 7.7 |
| 0.02 | 0.391 | 0.166 | 6.6 |
| 0.05 | 0.281 | 0.156 | 6.2 |
| 0.25 | 0.031 | 0.060 | 4.2 |
| 1.00 | **0.000** | 0.000 | 3.4 |

`q = 0` returning exactly 0.500 is the sanity check, not a result: it is
self-play across both seats, so anything else would mean a seat bias.

**A uniformly random player never wins.** Not rarely -- 0 of 32. The floor
under any model's score is zero, not a coin flip.

**And the games get SHORTER, which is the mechanism.** 7.7 turns at q=0
against 3.4 at q=1, with `NUCLEAR WAR` in the log. A random move does not
merely play badly, it detonates the game: it coups at DEFCON 2, it walks
into the Middle East at the wrong moment. That is why the curve falls as
steeply as it does, and it is a property of Twilight Struggle rather than
of this bot.

## What it says about a model

2% invalid costs about 11 points of score, 5% costs 22. So the bar for a
model that plays this game is about **1% schema failure**, far tighter
than a bare per-call error rate suggests, and a model above it cannot be
distinguished from a broken harness: you would be measuring the damage
rather than the play.

Combined with 269 calls per game and ~29k input tokens each
(`docs/notes/claude/` handoff, measured the same day), this is most of why
the play-a-game line was dropped and the offline card-valuation harvest
(`scripts/harvest_card_valuations.py`) kept. The harvest asks one call per
card, scores the model against 19 held-out known valuations first, and
cannot damage a game because there is no game.

## What it does NOT say

Nothing about how strong any LLM is at this game. No LLM has played it
here. It says what the HARNESS costs when a model fails, which is a
different and more useful thing to know first.

It also does not say the strategic bot is fragile. Uniform-random over
legal options is a much harsher failure than a confused player: it is the
worst move available with the same probability as the best.
