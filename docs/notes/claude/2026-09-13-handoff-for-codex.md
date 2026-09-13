# Handoff, 2026-09-13 — written for Codex, for a second viewpoint

The maintainer wants a different reading of today's work, not a
continuation of it. So this is organised around **what is uncertain**
rather than what got done, and the four open questions in section 4 are
the actual ask.

Tree is clean at `3f9166b`, pushed. Read `docs/notes/claude/README.md` for
the topic index. The morning's handoff (`2026-09-12-handoff.md`) covers
the state before any of this.

## 1. Live right now

- **CI gate run 34731449614** — both jobs **ACCEPTED**, which means *not
  measurably worse* and never *better*:

  | base | pooled | vs base | vs held | signed VP | nuclear |
  | --- | ---: | ---: | ---: | ---: | --- |
  | `f492dc3` (the change alone) | 0.500 +/-0.027, 84 seeds | 0.488 | 0.512 | -0.36 | 23/168 |
  | `c7ed9f5` (wider window) | 0.492 +/-0.025, 91 seeds | 0.478 | 0.506 | -0.51 | 24/182 |

  Both curtailed early (`--decide`) at 84 and 91 of a possible 128.
- Nothing running locally. `scripts/gate_running.py` says "not running".

## 2. The one behavioural change today

`7a1ac6c` — **the redundant-route discount in `access` became a function
of the target's stability** instead of one constant.

Measured over 96 seeds and 3888 resolved opportunities
(`scripts/measure_access_conversion.py`), where `p` is "we reach it now,
do we control it by the time its region next scores":

    stability   1      2      3      4      pooled
    p           0.406  0.303  0.304  0.154  0.287
    n           409    1199   1586   694    3888

Binomial errors 0.024 / 0.013 / 0.012 / 0.014. Stability 2 and 3 are one
number; stability 4 is a cliff. **No smooth one-parameter form fits** —
linear chi2/dof 13.2, exponential 16.7, hyperbolic 25.6, all against those
errors — so the measurement is used directly rather than fitted through.
`evaluator.route_decay(stability, base)` rescales the shape around the
pooled level so `access_decay` stays the single A/B lever and this change
moves shape only.

Corpus delta, measured on the frozen corpus **before** re-capture: 2 top
actions (0.6%) and 79 orderings (23.0%) of 344 records, 75 of the 79 in
`place_influence`.

**And the part that needs a second opinion is not the delta.** The
re-capture's turn distribution moved:

    turn      1     3     5     7     9    total
    before  127   104    66    47     0      344
    after   127   101    83    58    32      401

The corpus samples fixed turns, so the games are LASTING LONGER, and
before this change they were not reaching turn 9 at all. Fewer early
losses and merely-less-decisive play look identical in a ranking delta.

**The gate leans toward the second, and this is a reading rather than a
result.** Strength is a dead heat (0.500 +/-0.027) and the gate calls the
nuclear-loss count "the usual rate" both times. Longer games, unchanged
strength, and an unchanged explosion rate is what postponing the same
result looks like; fewer early losses should have moved at least one of
those. Two reasons not to take it as settled: the turn distribution comes
from strategic-vs-strategic self-play on seeds 4000-4003, while the gate
is candidate-vs-base on 4000-4063 plus held-out; and the nuclear count
pools both arms, so it cannot attribute an explosion to a side. Someone
should check the candidate's own game lengths directly -- `benchmark.py`
already records `vp_by_turn` and the terminal turn per game, so this is a
read of an existing report, not a new measurement.

## 3. What else landed

- `1aa122e` — `cards.json` said Ask Not may discard only "non-scoring"
  cards; `events.py` deliberately allows scoring cards, quoting FAQ 5.0,
  and `docs/CARDS.md` and `docs/RULES_SOURCES.md` both already had it
  right. Only the summary disagreed, and it feeds the LLM prompt. Shape 4.
- `f492dc3` — **retention is stability, not contest.** 3262 held-country
  observations: pooled over stability, uncontested 0.828 (n=1469) against
  contested 0.822 (n=1793). The contest hypothesis is dead. Stability
  predicts retention monotonically, 0.48 at stability 1 to 0.92 at 4.
- `fd713f1` — an advisory step could end the gate. `advisory_count` ended
  on its grep pipeline, so grep's "nothing matched" exit 1 became the
  function's return value and `set -euo pipefail` killed the run 0.3s into
  step 1c, before any game. Introduced by `f496450` this afternoon and
  never run on a runner until tonight. Gated by a test that reconstructs
  it.
- `93a78d3` — what a random legal move costs, and the card harvest.
- `3f9166b` — the maintainer's read on `twilightstrategy.com`.

**What a random legal move costs** (`scripts/measure_noise_cost.py`, 32
games per rate, both seats) matters beyond the LLM question:

    q      0.00   0.02   0.05   0.25   1.00
    score  0.500  0.391  0.281  0.031  0.000
    turn    7.7    6.6    6.2    4.2    3.4

A uniformly random player wins **0 of 32**, and games get SHORTER as noise
rises, with `NUCLEAR WAR` in the log. Noise does not play badly, it
detonates the game. `q=0` returning exactly 0.500 is the symmetry check.

## 4. The four questions — this is the ask

**4a. Israel, and whether the revamp is aimed at the right term.**
Israel is stability 4: conversion 0.154, retention 0.913. It is expensive
to ACQUIRE and cheap to KEEP. Every attempt so far has tried to discount
it through flip risk or retention, which is the holding side. Is the
acquisition-side reading right, and if so what should price it — `access`
already sees stability now, so what is left over?

**4b. The non-battleground ratio.** Measured 0.465 against the
maintainer's target of "at most a third, preferably under a quarter"
(`2026-09-12-battleground-revamp-plan.md`). The rules-derived formula in
that note produces the ratio as *derived* rather than tuned, and it does
not land where the maintainer says it should. Either the formula is
missing a term or the target is about something the formula does not
model. A second reading of that note's `swing` decomposition is worth
more than another measurement.

**4c. Blockade is priced by the generic Ops estimate, silently.** 39
`RecursionError` sandbox fallbacks across 77 seeds, plus Che twice.
`policy.py` lines 1772-1775 assert Blockade "survives only because it is
one choice deep" — a prediction written next to the Debt Crisis fix and
never checked. **I could not reproduce it**: a plain strategic-vs-strategic
game at seeds 4000/4001 showed none, and event nesting never exceeded
depth 1 (204 of 1835 calls). I retracted a theory that it was
`_resolve_sandbox` recursing on its own die-roll forks — that was a guess,
not a finding. Fresh eyes on where the recursion actually is.

**4d. Should the turn discount come from `conversion_p`?** `p` is defined
per horizon — "by the time the region next scores" — which is the question
the turn discount asks one scoring further out. Today those are fitted
separately from different data and can disagree with themselves. `p` at
two scorings out is the same script with the horizon moved, and the ratio
between them IS the per-scoring decay rather than a constant chosen to
make early turns feel right. Deliberately not wired: it moves every
turn-discounted term at once.

## 5. Dead ends — do not redo these

- **Contest as a retention predictor.** Answered, section 3.
- **Smooth curves through `p`.** Three forms, all rejected. Section 2.
- **The LLM playing games.** Measured: 269 calls and ~29k input tokens per
  game, ~950M input tokens for 128 games, and `LLMPlayer` falls back to a
  RANDOM legal move after one failed retry (`player.py`, `_MAX_RETRIES`),
  so 2% schema failure costs ~11 points of score. The maintainer's summary
  is that this is a Stockfish-shaped problem and no LLM beats Stockfish.
  Dropped. `scripts/harvest_card_valuations.py` — one offline call per
  card, validated against 19 held-out known valuations first — is written,
  unrun, and deprioritised in favour of a `twilightstrategy.com`
  comparison.
- **`scoring_discount` 0.93 and 0.55.** Both measured worse than the
  shipped 0.8; see the two notes named for them.

## 6. Where I was wrong today, so you can calibrate this note

Six, and they are the reason section 4 is phrased as questions:

1. Diagnosed the Blockade recursion as die-roll forks. Unsupported.
2. Predicted the LLM's context would blow past 128k. It saturates near
   36k — `build_history_entry` already trims, which I had read and then
   contradicted.
3. Claimed `|| true` fixed `advisory_count`. Mutation-checking said
   MISSED; the operative fix is the trailing `printf`.
4. Wrote a provenance audit that reported "0 of 102 disagreements"
   because `EVENTS[cid]` is a dataclass, not a function, so it compared
   nothing. Shape 9, caught by a self-test.
5. Committed a message claiming a CLAUDE.md edit that had failed its
   anchor check. Fixed in `aeb560b`.
6. Reported Gmail/Calendar connectors as "needs auth" from the session
   banner without checking; Gmail and Drive were both connected.

The measurements in sections 2 and 3 were all mutation-checked or
symmetry-checked. The prose around them is where the errors were.

## 7. Running things

- Full suite: `uv run pytest`, **6-7 minutes** on an idle machine,
  `test_parity_corpus.py` is 4:41 of it at 401 records. Do not time it
  while anything else runs — a figure taken under contention has already
  been committed to CLAUDE.md twice today.
- Gate locally: `scripts/gate.sh <base>`, one per machine, exit status is
  the verdict.
- Gate on CI: `gh workflow run gate -f bases='["<sha>"]'` — a matrix, one
  job per base, no lock needed because runners are isolated. Wall-clock
  from a runner is not quotable; the verdict is.
