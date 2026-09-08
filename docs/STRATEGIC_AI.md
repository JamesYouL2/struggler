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

## Hand survival

`bots/defcon.py`'s `DefconPlanner` is the tactical guard in front of every
VP score. `StrategicPlayer.safety_key` ranks each legal option by a tuple:
certain immediate defeat first, then the planner's turn-loss risk, then the
trainable score. So a card play, play mode, headline, event choice, or trap
discard that leaves the hand unable to survive the turn loses to any option
that can, regardless of country value.

The planner is a memoised search over the observation only, never hidden
state: the state is (hand, rounds left, DEFCON, Space Race box and
attempts, China Card, trapped). Each of our rounds tries every card and
mode the engine would offer (Ops, event, Space Race, UN Intervention),
firing an opponent card's event on Ops exactly as the engine does. Between
our rounds a chance node applies `SurvivalPrior`:

- `opponent_lowers_defcon` (flat default 0.75) while DEFCON is above 2;
- `opponent_hand_attack` (flat default 0.10) that an Aldrich Ames,
  Terrorism, Grain Sales, or Missile Envy removes one of our safe cards,
  chosen adversarially so a plan with no spare safe card is charged for it;
- `unknown_chain_loss` and `replacement_hazard` for cards the search
  cannot see (Five Year Plan's random target from the US side, Missile
  Envy, Ask Not's replacements).

Those two probabilities are learned, not hand-set, when a checkpoint is
configured. `bots/opponent_model.py`'s `OpponentModel` is a two-head
network (one tanh hidden layer, sigmoid outputs, standard library only)
over public `Observation` features: turn, round, rounds left, DEFCON, hand
sizes, the unseen-card share, each side's military-ops deficit, whether
the opponent is trapped or Red-Scared, Iranian Hostage Crisis, and the
public status (hand / unseen / discard / removed / not yet in the deck) of
each attack card. Its labels are real: replaying a recorded game, each
headline or action-round pick becomes a row labelled with whether a card
held then was gone from the hand at that side's next pick (removals by the
side's own decisions do not count) and whether DEFCON fell on an
opponent-attributed step in between. Whole games stay in one of the
train/validation/test splits. Train it from the checked-in logs and use
it with `STRUGGLER_OPPONENT_MODEL`:

```sh
python -m struggler.bots.opponent_model --logs 'logs/game-check/*.json' \
  --output models/opponent-model-v1.json
STRUGGLER_OPPONENT_MODEL=models/opponent-model-v1.json \
  python src/main.py --us strategic --ussr strategic --seed 1
```

`DefconPlanner` swaps the two flat prior values for the model's
predictions per observation (`StrategicPlayer(opponent_model=...)`, also
accepted by `EventValuePlayer`); the report next to the checkpoint gives
log-loss and Brier score per head against the base-rate predictor and a
calibration table on held-out games. The flat defaults remain the
fallback without a checkpoint. A model trained on bot-vs-bot logs learns
those bots' habits, so retrain it when the bots change.

Two decisions outside the card play itself are also priced. A
battleground coup (`coup_survival_risk`, used for the Ops-type choice and
the coup target) is evaluated by the hand's survival at the lowered DEFCON
with our influence added to the target, because a won coup hands the
opponent's CIA Created or Lone Gunman a place to coup back; a non-
battleground coup costs nothing. A headline pick (`headline_pick_risk`)
weighs the chance the opponent's higher-Ops headline resolves first and
lowers DEFCON before ours fires, so a 1-Ops suicide card is not a "safe"
headline at DEFCON 3. Our own revealed, still-pending headline
(`Observation.headline_pending`) is a forced event ahead of the action
rounds in every evaluation made during the opponent's headline.

Card-specific transitions cover DEFCON raisers, Ask Not, Aldrich Ames,
Five Year Plan, Salt Negotiations' retrieval, Blockade and Latin American
Debt Crisis (pay a 3+ Ops card with no event, or refuse), and self-trapping
with Quagmire/Bear Trap, after which each round discards a 2+ Ops card
without an event and rolls 1-4 to escape. `discard_risk` prices a mid-play
discard (Blockade's choice, a trap step) with the current round already
spent; `event_risk` prices a single event firing now, including the
opponent-granted coups of CIA Created, Lone Gunman, Grain Sales, Tear Down
This Wall, and Ortega. A hand with no hazardous card short-circuits to zero
risk; a search over `max_states` states falls back to a conservative count
of safe cards versus rounds and is reported in the diagnostic log.

The strategy behind these rules is [DEFCON_STRATEGY.md](DEFCON_STRATEGY.md);
`tests/test_defcon_planner.py` pins each transition and the seed 2400
(headline), 2401 (Blockade), and 2402 (coup target) regressions from
`logs/game-check`; all four of the 2400-2403 strategic-vs-strategic games
that ended in nuclear war now end on VP or final scoring.

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
flags are only partially valued. Hand survival is a bounded search with
fixed priors: it does not track which attack cards the opponent actually
holds, model the opponent's regional play, or value the board damage a
refused Blockade costs against the risk it avoids. Its safety heuristics
are not a guarantee against every nuclear loss. Strength against the supplied baselines is evidence of an improvement,
not evidence of expert human-level play.
