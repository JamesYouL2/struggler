"""Offline fitting tooling. The bot never imports this package.

`forecast` (one region's expected scoring payout) and `valuation` (the
whole-board scoring potential) were the value-function rebuild's exact
target. They have been off the ranking path since `potential` was deleted
on 2026-09-26, and their one consumer is `scripts/fit_country_weights.py`,
which fits the shipped per-country weights
(`bots/strategic/fitted_country_weights.json`, read by the evaluator at
runtime and so staying in the bot package) against them.

They live here rather than under `struggler.bots` because the bots package
is what a gate's baseline snapshot and the Rust port copy: everything in it
is taken to be something play can reach. Fitting code depends on the bot
(it reads `evaluator` and `schedule`); the bot must not depend on it.
`tests/test_fitting_boundary.py` holds that direction.
"""
