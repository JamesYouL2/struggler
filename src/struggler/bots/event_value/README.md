# Event-aware regional VP model

This is an experimental **1,665-parameter neural network** (102 inputs, 16 tanh
units, one scalar output), implemented in Python's standard library. It learns
an event-related correction to the engine's current regional score. Country
values are the change in predicted regional VP after adding influence, so they
can reflect domination thresholds and the rest of the region.

The implementation is deliberately small enough to train on a CPU in seconds.
It does not call an LLM or need NumPy/PyTorch. It is a supervised bootstrap,
not a trained expert opponent or a calibrated predictor of actual future VP.

## Files

- `features.py`: country/event relationships, public card status, timing priors,
  regional statistics, affected countries' influence and neighboring control.
- `scenarios.py`: engine-generated training targets. Covers Fidel, Nasser,
  Sadat, Korean War, Indo-Pakistani War, and Portuguese Empire Crumbles.
- `network.py`: shared regional network, mini-batch SGD, schema-checked JSON
  checkpoints. Learns a residual instead of relearning current scoring.
- `train.py`: small synthetic datasets, fixed train/validation/test splits,
  validation checkpoint selection, and held-out error measurements.
- `player.py`: optional tactical policy integration and country-value inspection.

## Build and use

From the repository root after installing the project:

```sh
python -m struggler.bots.event_value.train \
  --samples 512 --epochs 40 --seed 7 \
  --save-data /tmp/event-value-data.json --output models/event-value-v1.json

# Tune the model without regenerating scenarios or changing dataset splits.
python -m struggler.bots.event_value.train \
  --data /tmp/event-value-data.json --epochs 60 --output /tmp/event-value-next.json

STRUGGLER_EVENT_VALUE_MODEL=models/event-value-v1.json \
  python src/main.py --us event-value --ussr strategic --seed 1 --no-game-log
```

Dataset files store features, priors, and all three splits. Keep evaluation
positions out of training, including their counterfactual variants. When
comparing many configurations, reserve an additional final test set.

```python
from struggler.bots.event_value import EventValuePlayer, ValueNetwork

bot = EventValuePlayer(ValueNetwork.load("models/event-value-v1.json"))
action = bot.choose_action(observation, history)
values = bot.country_values(observation)  # country -> marginal VP of +1 influence
```

`country_values` reports marginal regional VP, before influence placement cost;
these values are not additive shares of the whole board's VP. The playable bot
adds the learned correction to the existing tactical evaluator. It retains that
policy's card choices, immediate VP handling, and direct DEFCON-loss guards.
This is an opt-in experiment; `strategic` remains unchanged.

## What the targets mean

The teacher asks: **what would this region score after plausible event exposure,
without other intervening moves?** It uses the engine's actual event effects,
all six war dice outcomes, and the attacker's best legal war target. Direct war
VP is excluded from regional predictions; the tactical layer prices it already.
For Egypt, it includes no event, either single event, and both Nasser/Sadat
orders. The two orders receive equal conditional weight. Other regions use a
mixture of zero or one covered event, normalizing exposure if necessary.

Event occurrence is an explicit, uncalibrated prior:

- Own-hand cards have known possession; unseen cards use
  `opponent_hand_size / (opponent_hand_size + draw_pile_size)`.
- Default trigger rate is 0.65. Exposure horizon is 0.35 with region scoring in
  hand, 0.75 with scoring unseen, and 1.0 otherwise.
- Removed, discarded, and not-yet-introduced events have zero current exposure.
  Discarded cards become candidates only after an observed reshuffle. This is
  a short-horizon approximation, not a forecast across the next reshuffle.
- If no covered event has exposure, neural correction is exactly zero, even
  with arbitrary learned parameters. Uncovered regions also get zero correction.
  Exclusively hostile exposure cannot produce a positive correction, and
  exclusively friendly exposure cannot produce a negative one. Mixed exposure
  can go either way. These constraints preserve known event directions.

These assumptions live in `TimingPrior` and are saved with the checkpoint.
Possessing an event does not mean it must fire. The initial prior does **not**
model deliberate hold/space choices, hidden revealed cards, or event scheduling.
Scoring in hand shortens exposure but does not force immediate scoring; an
actual scoring-card action still uses the engine's current score.

## Evidence and next step

The checked-in checkpoint and `.report.json` record a 512-position training
run, with 128 validation and 128 test positions, 40 epochs, and seed 7. It took
about 9 seconds here. Test MSE fell from 0.4571 VP² (zero correction) to
0.3811 VP², a 16.6% reduction; test MAE was 0.2951 VP. The report compares held-out synthetic-target error with a baseline that
ignores event exposure (zero residual). A reduction in that error demonstrates
learning the teacher, not improved win rate or the correctness of its priors.

Training positions are random regional stress cases, not realistic expert-game
samples. Small-data predictions can still miss adjustment magnitudes or return zero
for a real threat. The network sees regional aggregates plus detailed influence for the
seven covered-event countries; it does not model all 110 card events. It shares
parameters across regions, without independent country-value tables.

The next useful investment is a small set of real-game positions with paired
counterfactual continuations. Those can replace synthetic targets via the same
`(features, residual_VP)` training interface. First compare action rankings and
held-out errors, then run a small tournament. Full self-play, calibrated event
likelihoods, and a terminal win-probability head are not implemented yet. Avoid
training a win head on invented labels; it needs actual terminal outcomes.

Before training on terminal game outcomes, read the
[DEFCON strategy and engine audit](../../../../docs/DEFCON_STRATEGY.md).
Country-value improvements cannot compensate for incorrect nuclear-loss
attribution or a hand plan that leaves only fatal plays.
