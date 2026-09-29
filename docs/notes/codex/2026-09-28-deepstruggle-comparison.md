# DeepStruggle comparison: what to borrow

Reviewed 2026-09-28. Static source review; no games, training, native builds, or tests run. No playing-strength ordering established.

## Revisions and scope

- JamesYouL2/struggler main: `0085ba06004fe1e84b2d416c483e91e3048b4756` (remote default branch checked).
- mihaild/DeepStruggle main: `bc6181b366faf3cc8fc88ee8fb125818b75debf3`.
- Historical baseline tag v0.1.0 resolves to `50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9`; not used as a strength baseline here.
- Remote heads inspected. The win-probability fit branch is already incorporated in main. The unmerged `exp/mcts-leaf-scale` tip is `581ba573904254103ad8dfbcff70f4daf4a45ed2`, merge base `6e47bfdcfd8e6b09cff3daa9acd6731725821c29`; its commit message reports a level scale-only experiment, not evidence that calibrated prediction improves play. Event-board-choice work exists separately at `c639a88ee0e7e603187873cce9531b03c464d5a0`.

Read repository guidance, current bot/search code, fit code and result notes, position-pack documentation, and relevant DeepStruggle importer, evaluator, search, training-pool, state-layout and fingerprint sources. This is a borrowing assessment, not a repeat engine audit; earlier correctness findings were not exhaustively rechecked.

## Recommendation

Borrow the external evidence and diagnostics before the neural architecture. No source reviewed establishes DeepStruggle as stronger than the current strategic bot, and the README itself describes an early training baseline. A large neural/RL port is not justified as a prerequisite to freezing or writing up Struggler.

### 1. Human-position corpus and whole-action-round comparisons: highest value

DeepStruggle has `tools/download_ts_replayer.py`, `tools/lib/ts_replayer_parse.py`, `tools/lib/ts_replayer_convert.py`, `tools/lib/ts_replayer_hands.py`, `tools/build_human_dataset.py`, and `ai/eval/round_counterfactual.py`. It imports actual games, checks reconstructed transitions, and can compare a human's completed action round against a model's alternative from the same starting board. This helps distinguish bad event valuation from bad execution of an event.

Struggler already has a parity corpus, an expert position pack, event diagnostics and extensive safety tests. The incremental value is an independent human-game source and reviewed alternatives, not merely another self-play regression file.

Start with 20-50 manually verified positions spanning early/mid/late war, both seats, event-vs-Ops choices, disposal and scoring timing. Preserve the board, mover-entitled observation, historical move and its resulting board. Compare top-ranked candidates and value deltas; have disputed cases reviewed. Human agreement alone is not a strength metric, and a human move is not automatically optimal.

The parser/converter/hand solver total 5,438 lines and depend on DeepStruggle's engine and action vocabulary. This is not a small drop-in port. Borrow parser/data design first; adapt conversion to Struggler only after the small corpus earns its cost.

Hand reconstruction uses whole-game constraints plus soft preferences when evidence is incomplete. Those assignments are hypotheses, not known original hands. Keep uncertain positions separate, prevent future reveals/opponent hands from reaching the bot, and deduplicate games before splitting datasets. Completed outcomes and truncated logs need distinct treatment.

### 2. Targeted behavioral diagnostics: inexpensive concept port

Relevant DeepStruggle modules: `ai/eval/sequencing.py`, `event_vs_ops.py`, `round_counterfactual.py`, `critic_usefulness.py`, `critic_calibration.py`, and `dominance.py`.

Useful questions: is a scarce disposal route reserved for the card with no other exit; does an event's free placement get valued differently from ordinary Ops; does the evaluator reject an expert-reviewed good resulting board, or does the bot simply execute the event badly? Extend the existing position pack and tests instead of creating a parallel framework.

Do not import assertions that strategic preferences hold in every position. In particular, broad card-association dominance and country-targeting claims need contextual exceptions. Treat these as diagnostics unless a controlled fixture establishes the answer. The counterfactual module's claim that disagreement proves the critic wrong also needs human/strategic review.

The critic-vs-trivial-baseline idea is already substantially present in `scripts/fit_winprob.py`. Main includes held-out log-loss/Brier comparisons and a logistic model result; do not propose implementing that from scratch. Better prediction is not proven stronger search. Mid-turn leaf-distribution coverage remains a distinct consideration from the existing turn-start dataset.

### 3. Native engine engineering: borrow when porting

`engine/include/ts/game_state.hpp` enforces trivially copyable state and a <=4 KB size bound. `tools/lib/engine_fingerprint.py` hashes source/build inputs to reject stale compiled extensions. These are useful references for compact Rust state, cheap cloning, deterministic replay, and verification that the loaded binary corresponds to the reviewed source. Extend provenance to compiler/toolchain/build options as needed; do not blindly impose their 4 KB limit or action layout.

No throughput claim was measured here. Their engine-step rate would not by itself establish speed or strength gains for Struggler's evaluator/search. Retain the Python engine and parity corpus as port oracles.

### 4. Training diversity: later, if learning becomes the project

`ai/training/start_pool.py` starts some rollouts from mid/late-game states; `opponent_pool.py` retains historical policies. These ideas can improve state/opponent coverage beyond current-policy opening self-play. Struggler already has historical anchor evaluation; a training pool is a different function.

Do not copy their sampling ratios or pool implementation unquestioningly. The opponent-pool documentation explicitly says a game's opponent can change between rollout iterations. Keep opponents fixed per game for interpretable evaluation. Resumed positions need legal state, fresh futures without information leakage, provenance, and full-game evaluation on the real starting distribution.

## Do not port wholesale

- `ai/search/pimcts.py` explicitly searches the true state including the opponent hand. It is a perfect-information diagnostic, not a fair deployed opponent. Struggler's MCTS begins from observation-only hidden-state sampling. Any PUCT implementation would need a separate information-boundary design.
- ColdWarNet/GNN/NashPG: large training and validation commitment with no demonstrated advantage over this bot in the reviewed evidence.
- The differential adapter: DeepStruggle has a Struggler adapter, but its own README/guidance marks the differential suite unfinished, excluded and failing at import. It is reference material, not an existing working head-to-head harness.
- Raw pretrained weights/action IDs: engine and observation contracts differ. For example, the action-encoder prose still says 212 slots while current code uses 220. Read implementation and verify translations.

## Next bounded task

Build a small human-derived position pack and report disagreements grouped into valuation, event execution, sequencing and information uncertainty. Turn only verified mistakes into regression tests or opt-in experiments. Assess any change with paired seeds/both seats, comparable budgets and fresh confirmation seeds. No claim of a five-percentage-point gain is supported yet.

Both repositories are MIT licensed; preserve the relevant copyright/license notices for copied code. Documentation only; no implementation edits. Publication was requested after the review. The publication base is `0085ba06004fe1e84b2d416c483e91e3048b4756`, matching the reviewed main revision. Full-suite verification is delegated to the repository push/PR CI; no local suite or strength experiment was run.

## Follow-up: self-play and software architecture

Further inspection found `ai/search/dmcts.py` and `ai/search/batched_mcts.py`. Correction to any broad reading of the earlier recommendation: only PIMCTS is inherently privileged. DeepStruggle also supplies determinized search and a batched searcher with an optional determinization mode. These still require information-boundary validation; strategy fusion remains acknowledged in the source. No search strength numbers were independently verified.

The useful architecture is native state/transition/rollout work behind a Python experiment layer. `bindings/ts_bindings.cpp` implements `VectorizedBatchRunner` with persistent arrays of game states, observations and legal masks, and parallel native stepping. `batched_mcts.py` batches one leaf from each of multiple independent searches into a model evaluation. This avoids within-tree concurrency machinery and is especially useful for GPU inference; cheap CPU heuristics may benefit more from ordinary whole-game parallelism.

A native rules engine alone does not accelerate Python heuristic ranking, survival planning or rollout orchestration. Measure current complete workloads, then move the expensive simulation boundary, with coarse calls such as ranked candidates, a rollout batch or a bounded search rather than a Python/native crossing per influence point. Keep the authoritative engine distinct from policy and let a native rollout/search layer compose them. Keep observation extraction separate from privileged simulation state.

`bindings/settle.py` is an especially useful design lesson: canonicalize advancement to the next genuine choice, with explicit chance/forced-action semantics, consistent search roots and replay recording. Never skip an opponent choice, and do not consume live RNG inside hypothetical search.

For a future learning loop, use the stronger heuristic as initial teacher and fixed evaluation opponent. Collect legal observation/action/outcome tuples; optionally distill a cheap rollout policy, and evaluate both imitation loss and actual strength/latency. Candidate rankings may supply priors without hard-pruning every non-top move. Add search-policy training targets only once search beats its base policy at a useful budget. Preserve full-game outcome labels, seed/game split isolation, actor perspective, immutable checkpoint identity and historical opponents. These are proposed applications, not measured improvements.

Recommended order: stable snapshot/observe/step contracts and parity; fresh profiling; native hot path plus cheap cloning; parallel self-play and replay provenance; optional policy distillation; batched learned evaluation only if inference becomes material. C++ versus Rust is secondary to boundary design and correctness. Replacing the engine with DeepStruggle's engine requires expensive rule/action/replay parity and is not justified merely by its existence.
