# Codex's MCTS findings (docs/notes/codex/)

1. Leaf evaluation inheriting the last ranking's context: fixed.
   `StrategicPlayer.evaluate(observation, board)` evaluates in the
   observation's own context (its scoring weights, DEFCON, fresh caches)
   and restores the ranking context after; `MCTSPlayer.leaf_return` uses
   it. Regression: `tests/test_mcts.py::test_leaf_value_does_not_depend_on_what_was_ranked_before`.
2. Served placement plans suppressing MCTS targets: fixed. A steered
   placement (`MCTSPlayer.continuation` with a target the side does not
   control) calls `RolloutPolicy.rank_for_target`, a full ranking that
   drops the served plan for the rest of the spend, so the target action
   is findable and the remaining points follow the target. Regression:
   `test_targeted_continuation_places_in_the_target_not_the_served_plan`.
3. Rollout ranking cache not syncing the board: fixed. A cache hit now
   syncs the board to the observation, and the continuation's control
   check reads the observation (`MCTSPlayer._controls`) rather than the
   policy board. Regression: `test_rollout_ranking_cache_hit_syncs_the_board`.
