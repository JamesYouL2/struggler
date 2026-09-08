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
  battlegrounds. A principle from strong play, recorded here because the
  evaluator does not yet honour it: influence value is **not linear** in
  the margin. Control is what scores VP; influence short of control has
  only option value (it can lead to VP); points beyond control are worth
  little, and what little they are worth is for low-stability countries
  where a cheap coup undoes them. Two shape weights exist for this,
  `progress_curve` (exponent on `margin/stability`) and
  `reserve_stability` (divides the reserve term by `stability ** that`),
  but the defaults stay at the linear, flat shape (1 and 0). Measured:
  `progress_curve=2, reserve_stability=1` scored 0.33 ± 0.09 against the
  linear shape on seeds 4000-4015, and left turn 1 of
  `logs/game-check/3003-strategic-event_value.info.log` unchanged (two
  Africa coups, no Asia). With one action of lookahead the linear progress
  term is what stands in for option value; making it convex just stops
  the bot starting countries it cannot finish this round, while coup gains
  are unchanged. Honouring the principle needs either lookahead across
  the turn's remaining Ops or a coup evaluator that prices DEFCON and
  tempo, not a steeper curve. A region's score is weighted by where its scoring card is:
  `scoring_hand` when we hold it, `scoring_live` when it is still in the
  draw pile or the opponent's hand (it can be played against us any round,
  so the region has to be played around), and the 1.0 baseline when it is
  dead until the reshuffle (discarded, removed, or not yet in the deck;
  the period schedule is static and public, `engine.cards.ENTRY_TURN`).
  Southeast Asia Scoring adds urgency only to the countries it scores
  (the `SOUTHEAST_ASIA` subregion), not to all of Asia.
- Country importance is tiered: battlegrounds (`battleground`) >>
  Southeast Asia non-battlegrounds (`southeast_asia`) >> other
  non-battlegrounds (`control`). Battleground Ops are what score
  domination and control, or deny them to the opponent; the cheap
  Southeast Asia countries keep Asia from being dominated and score
  later; everything else is worth little. There is no turn-specific rule:
  a turn-1 rule that zeroed non-battleground Ops was tried, flipped
  `logs/game-check/3003-strategic-event_value.turn1-rule.info.log` to a
  US win, and measured 0.47 ± 0.09 on the 16-seed A/B; the tiering is
  meant to produce the same opening from the value function itself.
- Coups and realignments are priced on the same board change as placing
  influence (`delta`), then multiplied by `coup_discount` (0.9): they are
  the less Ops-efficient route to the same result (a coup on a
  2-stability country gives up a point of margin to the roll) and random
  where placement is certain, so placement is generally preferred.
  Military Ops are still credited to a coup.
- VP per Op is the quantity the influence search maximises (`influence`
  returns gain per Op spent, including the doubled cost under enemy
  control), so 1- and 2-stability countries, which reach control for the
  fewest Ops, are automatically the best value while their scoring card
  is live; nothing extra encodes that.
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

python -m struggler.bots.train train --seed 200 --pairs 8 \
  --generations 4 --population 4 --workers 8 \
  --fields scoring_live,scoring_hand --output my-model.json
python -m struggler.bots.train evaluate --opponent strategic --pairs 16 \
  --seed 4000 --model my-model.json --workers 8
```

Training mutates the positive evaluation weights using seeded log-normal
noise and selects by terminal game score, evaluating the incumbent and each
mutation on the same paired seeds. The opponent is a frozen **anchor**: by
default the initial weights playing as the strategic bot, so every
generation's score means the same thing and the search cannot drift toward
a moving target. `--anchor greedy` keeps the older, weaker opponent; since
the DEFCON survival planner the strategic bot scores 1.00 against greedy on
a 16-seed baseline, so greedy no longer discriminates between candidates.
`--fields` restricts mutation to named weights (for example the two
scoring-card urgencies). Ties retain the incumbent. Each generation saves
its checkpoint and a trace with the selected weights. `--model` can
initialize a new run from an existing checkpoint; it does not restore an
earlier optimizer RNG.

Cost is `2 * pairs * population * generations` complete games, spread over
`--workers` processes. Use evaluation seeds outside the entire training
range (`seed` through `seed + pairs * generations - 1`). Increasing training
volume does not guarantee improved performance against people or unseen
policies. Compare checkpoints against several opponents before adopting
them. The `strategic` evaluation opponent uses handcrafted defaults unless
`--rival` names a checkpoint.

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
those bots' habits, so retrain it when the bots change. In particular the
checked-in checkpoint's hand-attack head is a base rate below 1% because
these bots almost never event Grain Sales, Aldrich Ames, or Terrorism;
strong humans always event the first two and event Terrorism whenever
behind or holding Iranian Hostage Crisis
([DEFCON_STRATEGY.md](DEFCON_STRATEGY.md#hand-discard-effects-traps-and-modifiers)).
Against humans prefer the flat prior, or a model trained on human logs.

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

## Experimental MCTS prototype

`mcts` searches at an ordinary action-round card pick when its own hand
contains a scoring card; other decisions use the strategic policy. It is
opt-in and does not change the `strategic` default.

```sh
STRUGGLER_MCTS_SIMULATIONS=24 \
  python src/main.py --us mcts --ussr strategic --seed 3003 --no-game-log \
  --log-level INFO --log-file mcts.log
# Optional soft wall-time limit, checked between complete simulations:
STRUGGLER_MCTS_SIMULATIONS=100 STRUGGLER_MCTS_SECONDS=1 \
  python src/main.py --us mcts --ussr strategic --seed 3003
```

`MCTSPlayer(seed=0, simulations=24, max_steps=256, time_limit=None)` runs
UCT over our card-play macros, with strategic opponent responses. A macro
is a card with either strategic continuation or an instruction to invest
in one reachable, uncontrolled BG in a region we hold scoring for. It
considers the top three survival-safe cards, additional safe scoring cards,
and up to two BG targets per non-scoring card. Targeted continuations prefer
Ops, influence, then that country until controlled; every atomic action
must still be legal and tie the best strategic survival ranking. The same
continuation is used when executing a selected macro in the real game.
Events and the opponent's moves resolve through the strategic policy.

Each simulation samples the unknown hand and deck from public inventory
counts, with its own RNG, and advances to turn end (including military-Ops
penalties), terminal game state, or the atomic-step cap. The engine is
constructed from `Observation` at a card boundary, never cloned from the
live game. Tree nodes are keyed by our observation, excluding decision IDs;
no opponent-hand or deck identities enter that key. Each actor's rollout
policy receives only its own observation. This is a small information-set
UCT prototype against a fixed opponent policy, not full adversarial ISMCTS.
Hidden-card sampling is uniform and does not condition on behavioral history.

The leaf return is explicitly **banked VP plus remaining board potential**:
`weights.vp * signed_engine_vp + strategic.value(board, side)`, transformed
with `tanh(value / 100)` and clipped to ±0.99. Actual terminal wins/losses
return ±1, draws 0. Regional board potential is a heuristic for future
scoring, not a replacement for points already scored. A regression holds
the final board identical while changing scoring order and checks that the
banked-VP difference changes the search return.

`last_search` and INFO logs report simulations, node count, elapsed seconds,
truncated simulations, and each root macro's visits and mean return. Fixed
simulation counts are reproducible for a given bot seed and observation;
time-limited results depend on machine speed. Very small budgets can leave
some root macros unexplored. The time limit is soft: one simulation can
overrun it. Search trees are discarded after each card decision.

Scope: standard events-enabled games, including optional cards when their
presence can be inferred from the inventory. Unsupported/inconsistent
inventories or ambiguous extra-round cursors fall back to strategic with an
INFO message. Mid-event and headline search, Ops-only simulations, learned
rollout policies, opponent search, and general multi-country allocation are
not implemented. A bounded rollout can stop before scoring; the diagnostic
`truncated` count exposes this. Passing tactical regressions establishes
correct plumbing, not an improvement in tournament strength.

Initial validation: 465 tests passed, 3 skipped. A seed-3003 game with US
`mcts` at 24 simulations against USSR `strategic` completed with a USSR win.
The 12 searched card decisions took a median 5.00 seconds and maximum 11.43
seconds on this workspace (other validation work ran concurrently); none
of the rollouts hit the step cap. The US selected Pakistan investment
macros on turn 1 AR3 and AR4 and scored Asia at -5 on AR5. This is a smoke
measurement, not a paired comparison or evidence of a strength gain.

### Profile-guided speed improvements

Strategic evaluation now caches country values (including event sandboxes)
and map access terms for one decision, reuses region membership, and skips
regional rescoring when a hypothetical influence change leaves control
unchanged. Realignment evaluates each distinct dice margin once while
retaining the original summation order. Influence observations copy both
mapping levels directly; their integer leaves need no recursive deepcopy.
MCTS information keys freeze public fields directly instead of deep-copying
a dataclass and encoding JSON. Simulation count, safety policy, rollout
horizon, and VP-inclusive returns are unchanged.

Three alternating before/after runs on saved seed-3003 positions measured:

| Workload | Before (median) | After (median) | Speedup |
| --- | ---: | ---: | ---: |
| Rank 150 strategic decisions | 0.900 s | 0.627 s | 1.44x |
| First US card pick, 24 MCTS simulations | 4.472 s | 2.772 s | 1.61x |

All legal-action rankings and root MCTS move values matched exactly across
these comparisons. These are local microbenchmarks, not a full-game timing
or playing-strength claim. Measurements are saved in
`logs/game-check/mcts-speed-comparison.json` (gitignored evidence).
