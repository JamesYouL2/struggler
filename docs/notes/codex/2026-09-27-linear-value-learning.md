# Linear value learning before MCTS self-training — 2026-09-27

Status: proposed experiment, not implemented or measured. User preference: start with a linear model, not a neural network. Follow-up to [the correctness and Rust-readiness audit](2026-09-27-correctness-rust-readiness.md).

Source context: audit of main `5ab9eab4417080d167359f06a381eab8865891f0`, placement-memo review, and publication base main `9a8f6c5d476b76b137f97f30199bcdd12df26e3f`. This note extends notes commit `221df44599508fca21e889bb5bae4c04dedf081f`; it is not a new source audit. Main remained at `9a8f6c5` when checked for this follow-up.

## Decision

Build a small regularized linear value model first. Generate its initial labels from completed games by the corrected strategic bot; MCTS is not required to produce those labels. Test prediction quality before integrating it into bounded search, then test playing strength separately. Do not start a neural-network or full AlphaZero-style training pipeline yet.

This is an optional research track, not a prerequisite for a faithful Rust evaluator port. Python is sufficient for the prototype. Rust becomes useful if data generation and search throughput prove to be the limiting costs.

## Two different kinds of backpropagation

MCTS backup sends a simulation result back through visited nodes, updating visit counts and action-value estimates. Those statistics guide that search; they do not automatically train an evaluator that persists between games.

Learning updates model parameters using saved examples. In an AlphaZero-style loop, search visit distributions provide policy targets and completed games provide value targets. The model is trained separately; the engine and search need not be differentiable. See [OpenSpiel's AlphaZero implementation notes](https://github.com/google-deepmind/open_spiel/blob/master/docs/alpha_zero.md).

The first version here learns only a value function. Keep the existing candidate generator and policy guidance. No learned policy head, search-policy imitation, or gradients through the game engine are needed.

## Smallest useful model

Use an L2-regularized linear score with a logistic link:

`p(o, seat) = sigmoid(b + w · features(o, seat))`

Train against final game score for the observing seat: win = 1, draw = 0.5, loss = 0. With draws, this predicts expected game score, not strictly the probability of winning. Use a fitting objective/tool that actually supports fractional targets; do not silently pass 0.5 as a third class to a binary-classification API.

A sigmoid link does not make this a neural network: it is a linear feature model with a bounded output. It can be fitted with an ordinary optimizer. Standardize numeric features using training-set statistics only and choose regularization using validation games.

Start with a compact, versioned feature vector built from entitled observations:

- Public VP from the observing seat's perspective; seat identity; turn, action round, phase, actor and phasing side.
- Regional control/presence/battleground summaries, influence or control features by country, and existing public board-value components where practical.
- DEFCON, military-Operations deficits, Space Race positions, China ownership/availability and relevant public persistent effects.
- Own hand: scoring cards by region, Ops distribution and a small set of clearly defined risk/hold constraints.
- Public hand/deck counts and public card history summaries; never the actual hidden opponent hand or future draw order.

Reuse the existing feature/evaluation and fitting infrastructure where appropriate; inspect `struggler/fitting` and existing training code before adding a parallel framework. Existing country-value fits are not automatically outcome-trained leaf evaluators.

Avoid a large feature expansion initially. A linear model misses interactions; a small, explicit turn-by-VP or phase-by-scoring feature can be tested later if residual errors justify it. Do not interpret correlated fitted coefficients as causal card or country values.

## Data and information contract

1. Fix the audited rules/cache defects and pin engine, policy, configuration and feature-schema versions before collecting the training batch. Record seeds and game termination reasons.
2. Capture features at a consistent search-compatible decision boundary. Begin with one observation per card-play decision to avoid giving influence-placement substeps disproportionate weight.
3. Label completed games from their actual terminal outcome. Exclude crashes, aborted games and timeouts from outcome labels; report them separately instead of calling them draws.
4. Split by seed family/game before fitting: both seats of a paired seed, all positions of a game and any related replay variants stay together. Use separate train, validation and untouched test groups. Equalize total game weight or use a fixed sampling scheme so long games do not dominate.
5. Test observation privacy by changing inaccessible hidden state while holding the entitled observation fixed: features and predictions must remain unchanged. Do not use the known nonacting-seat analysis observation without filtering/repairing its private-option exposure.
6. Save dataset provenance, model coefficients, feature ordering, scaling and split manifests together. Inspect existing replay artifacts for reuse, but only if they support correct observation reconstruction and compatible rules.

A model trained on strategic self-play estimates outcomes under that behavior distribution. It does not learn optimal play merely because labels are real outcomes. Search will visit different states; distribution shift must be measured.

Hidden-hand sampling alone is not a complete information-set search solution. Simulated decisions must respect each actor's knowledge; otherwise search can choose different actions depending on hidden cards the real actor cannot distinguish. Retain this as an explicit search-design constraint, not something the linear learner is assumed to solve.

## Staged experiment and acceptance criteria

| Stage | Compare | Proceed only if |
|---|---|---|
| Offline prediction | Linear feature model versus a constant predictor, a VP/turn/seat baseline, and a validation-calibrated current evaluator | Held-out log loss/Brier score and calibration show useful improvement beyond the simple baselines; report results by seat and game phase, with uncertainty grouped by game/seed |
| Search integration | Same candidate set, safety constraints and search budget; change only the leaf evaluator | Terminal values and seat signs are correct; no hidden-information leak; a fixed position set produces explainable legal choices |
| Strength experiment | Learned-leaf search versus current-leaf search, plus the plain strategic bot as a practical reference | Paired-seed/both-seat evidence supports improved game score at acceptable latency; fresh confirmation seeds survive selection effects |
| Optional iteration | Collect new games under an accepted candidate and refit with retained older data | Improvement survives held-out opponents/checkpoints and does not simply overfit the latest self-play distribution |

For search, use `2*p - 1` if its return convention is [-1, 1], with exact terminal returns overriding predictions. Convert perspective explicitly at backups; do not blindly flip signs at every engine subdecision because actors do not always alternate. Predictions from different seats' private information are not necessarily exact complements.

Do not add predicted win probability directly to existing VP-unit heuristic deltas. Initially replace only the search leaf value, with a documented return scale; leave live event/placement pricing intact. That isolates the experiment and avoids double-counting.

Keep fixed-work comparisons separate from equal-time comparisons. Record visits to the selected root action, root coverage, search disagreement, wall time and nuclear-loss rates alongside game score. Better calibration is not proof of better moves.

Before dispatch, consult/update `models/experiment_ledger.json`, register exact candidate/baseline revisions and seed blocks, and set a sample budget, stopping rule and practically meaningful effect target. No tournament or training job is dispatched by this note.

## Why not train directly from today's MCTS choices?

The historical [32-seed MCTS result](../claude/archive/2026-09-10-mcts-does-not-replicate-and-military-ops-needed-a-discount.md) reported game score 0.547 with a 95% interval [0.425, 0.668], and only four visits to the selected root move at the median. This is historical evidence about that configuration, not a fresh measurement of current main. It does not establish a reliable search teacher.

Start with completed-game outcomes, then establish whether bounded search improves decisions with the learned leaf. Search-policy targets and an iterative MCTS training loop become reasonable only after search quality and information handling are credible. Even then, a stronger learner is an experiment rather than an automatic upgrade.

## Deliverable and stopping point

The first implementation should produce a reproducible dataset manifest, one small fitted model, a held-out prediction report and an optional leaf-evaluator adapter. Keep it opt-in. If it cannot beat a VP/turn baseline offline, investigate features/data before spending on tournaments. If prediction improves but playing strength does not, do not ship it based on prediction metrics alone.

Documentation-only follow-up: no model trained, implementation changed, new benchmark run or new performance claim made.
