# Strategic AI

`strategic` is a local tactical AI with a linear evaluation function and an
optional evolutionary training pipeline. It needs no API key, GPU, or ML
framework. Its default weights are handcrafted; `models/strategic-v1.json`
is a small training-run checkpoint, not a large-scale pretrained model.

## Play

```sh
python src/main.py --us strategic --ussr greedy --seed 1 --no-game-log
python src/main.py --us human --ussr strategic

# Load a trained checkpoint (applies to every strategic seat).
STRUGGLER_STRATEGIC_MODEL=models/strategic-v1.json \
  python src/main.py --us strategic --ussr greedy --seed 1
```

The same player works through the existing physical-board and replay/resume
interfaces. It has no private conversation or RNG state to restore.

```python
from struggler.bots.strategic import StrategicPlayer, StrategicWeights

bot = StrategicPlayer(StrategicWeights.load("models/strategic-v1.json"))
action = bot.choose_action(observation, history)
```

## How it plays

- Values battleground control, regional scoring, partial progress toward
  control, small defensive reserves, and influence that opens nearby
  battlegrounds. Regions with scoring cards in hand receive extra attention.
- Searches affordable multi-point investments into each candidate country,
  accounting for the end of doubled placement costs when enemy control breaks.
- Enumerates all six coup rolls and all 36 realignment roll pairs. These are
  exact expectations of its local board evaluator, not a simulation at an
  average roll. Prices military-operations deficits and avoids directly fatal
  coups, including Cuban Missile Crisis.
- Evaluates selected deterministic public-board events using the engine's
  event implementation, resolving influence choices for each beneficiary.
  Handles friendly versus enemy card allegiance when comparing ops, events,
  and spacing, and detects selected dangerous DEFCON cards.
- Handles event influence removal/placement, war targets, scoring cards,
  discards, and selected event choices such as Blockade and Wargames.

All decisions use only `Observation`; history is currently ignored. The event
sandbox is constructed from public fields with an independent fixed RNG and
empty unknown hands/deck. Only an explicit whitelist of deterministic
public-board events is simulated. The live engine, its private decision stack,
its RNG state, and the opponent's hidden cards are never copied or inspected.
The actual action always comes from the offered legal options.

## Evaluate and train

Evaluation plays both seats on every seed, with events enabled. Identical seeds
pair the initial shuffle; later dice consumption can diverge with the policies.
The report includes per-game records, scores by side, and a standard error
computed over seed pairs. A draw counts as half a point.

```sh
python -m struggler.bots.train evaluate --pairs 20 --seed 1000 \
  --model models/strategic-v1.json --report evaluation.json
python -m struggler.bots.train evaluate --opponent random --pairs 20 --seed 1000
python -m struggler.bots.train evaluate --opponent strategic --pairs 20 --seed 1000

python -m struggler.bots.train train --seed 200 --pairs 10 \
  --generations 5 --population 5 --output my-model.json
```

Training mutates the positive evaluation weights using seeded log-normal noise
and selects by terminal game score. It alternates a fixed greedy opponent with
a frozen copy of the incumbent, evaluating the incumbent and each mutation on
the same paired seeds. Ties retain the incumbent. Each generation saves its
checkpoint and selection trace. `--model` can initialize a new training run
from an existing checkpoint; it does not restore an earlier optimizer RNG.

Cost is `2 * pairs * population * generations` complete games. Start small;
this implementation runs serially. Use evaluation seeds outside the entire
training range (`seed` through `seed + pairs * generations - 1`). Increasing
training volume does not guarantee improved performance against people or
unseen policies. Compare checkpoints against several opponents before adopting
them. The `strategic` evaluation opponent always uses handcrafted defaults.

## Measured results

The supplied policy won **34 of 40 games (85%)** against `GreedyPlayer` on
held-out seeds 1000–1019, each played from both seats, with events enabled:

| Seat | Wins | Games |
| --- | ---: | ---: |
| US | 14 | 20 |
| USSR | 20 | 20 |

The paired-seed standard error is about 5.3 percentage points; this is a small
benchmark against one relatively weak opponent. Full game outcomes are in
[`models/strategic-default-evaluation.json`](../models/strategic-default-evaluation.json).
The greedy baseline includes the Europe-control scoring crash fix supplied
with this change.

The included checkpoint was produced with `--seed 200 --pairs 4
--generations 2 --population 3` (48 games). Neither generation found a strict
improvement, so it **retains the handcrafted weights**; its training trace is
stored in the checkpoint. Therefore the benchmark above also describes the
checkpoint's identical policy. This run validates the training pipeline; it
does not demonstrate that learning improved playing strength.

Validation: 392 tests passed, 3 skipped, including tactical regressions,
observation non-mutation, deterministic paired games, and model serialization.

## Limits

This is a bounded tactical policy, not full-game minimax, MCTS, or deep RL.
Influence search invests in one country at a time and uses average value per
operation; it does not search every allocation across multiple countries.
Operations-type evaluation estimates future placements from current
reachability; the engine's offered actions remain authoritative for each
actual placement. Its regional evaluator approximates special scoring modifiers,
although scoring-card and Wargames decisions use the engine's scoring code.

Events outside the whitelist use rough allegiance/ops-based estimates, and
unhandled event branches tie-break to the first legal option. Long-term event
flags are only partially valued. It does not reason about all forced DEFCON
traps, hidden-hand probabilities, card tracking, or the opponent's future
responses. Its safety heuristics are not a guarantee against every nuclear
loss. Strength against the supplied baselines is evidence of an improvement,
not evidence of expert human-level play.
