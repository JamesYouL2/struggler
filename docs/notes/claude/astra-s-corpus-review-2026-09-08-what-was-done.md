# Astra's corpus review (2026-09-08): what was done

- Checker repaired: replays the planner probes as an ordered list (the
  budget is shared, so order is the contract), restores the recorded
  weights and prior, checks event risks, node counts and truncation, and
  fails on missing required fields (schema test).
- Corpus v3 records: provenance captured before games run (HEAD, dirty
  paths including the generator, generator SHA-256); event values in hand
  order; per-point `delta` and `_investment` for every placement
  candidate; a budget-limited planner (`max_states` 200) with its own
  ranking and ordered probes, so truncation is pinned; the rollout
  policy's ranking (its `(value, country)` tie rule) on Ops decisions.
  506 positions. Still missing from Astra's list: dedicated MCTS rollout
  and event-sandbox records, generated boundary cases, non-default
  learned-prior context.
- `profile_baseline.py`: several unprofiled timings before one profiled
  run, a JSON report with revision/platform, the MCTS cases require a
  completed search (the opening case now uses the seed-4000 T1 AR1 US
  record with a scoring card in hand), and the engine row is labelled
  cumulative. The table above was exploratory (a gate ran concurrently);
  the baseline for the first slice is re-run on a snapshot.
- Astra agrees with evaluator-first (region margin as the first slice)
  and that deferring the planner is prioritisation, not proof.
