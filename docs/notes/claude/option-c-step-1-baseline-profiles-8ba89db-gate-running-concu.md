# Option C, step 1: baseline profiles (8ba89db, gate running concurrently)

`scripts/profile_baseline.py`. Shares are of profiled time; `delta`,
`country_value`, `_access`, `region_margin`, `rank_actions` are
cumulative (they nest), the planner, engine and enum rows exclusive.

| Workload | wall (profiled) | planner excl. | `delta` cum. | `country_value` | `_access` | `region_margin` | engine | enum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Strategic full game, seed 4000 | 37.8 s | 10 % | 53 % | 19 % | 11 % | 10 % | 2 % | 6 % |
| MCTS 24 sims, scoring hand (4000 T3 AR1 US) | 41.3 s | 0 % | 73 % | 26 % | 16 % | 13 % | 3 % | 4 % |
| MCTS 24 sims, hazardous hand (4000 T5 AR3 USSR) | 18.4 s | 2 % | 71 % | 26 % | 15 % | 14 % | 3 % | 5 % |

(The "MCTS opening" position has no scoring card in hand, so MCTS falls
back to the plain policy in 0.1 s; not a search profile.)

What changed since the morning's profile: the planner's 60 % was its
*cumulative* time, most of it inside the evaluator it calls
(`coup_survival_risk` -> `delta`); its own exclusive time is 10 % of a
full game and ~0 % of a search. The evaluator's `delta` path is 53-73 %
of both workloads, and the new region-margin term is 10-14 % of it on
its own. By Astra's rule (memoise the planner first "unless the fresh
profiles favor an equally small indexing change"), step 2 is deferred:
its ceiling is 1.1x on a full game and nothing on search. Step 3, the
evaluator, comes first, starting with `_access` and `region_margin`.
