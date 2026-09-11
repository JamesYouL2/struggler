# The value function's terms, and which to keep

On the board a position is worth one of three things: what it scores,
progress toward scoring, or the right to fight for a country at all
(reach and first-mover advantage: whoever fills an empty country first
wins the Ops-efficiency battle, or is the only one who gets to fight it).
Every term should be one of those. As of Sept 2026:

| Term | Weight(s) | Kind | Keep? |
| --- | --- | --- | --- |
| Battleground control x what the region still scores | `battleground`, scoring weights (`scoring_hand`, `scoring_discount`) | scoring | Keep: the core. |
| Exact region score, plus the region margin | `region`, `margin_*` | scoring | Keep. |
| Linear progress toward control | `progress` | progress | Keep. `progress_curve` stays 1 (convexity lost 0.33 without lookahead). |
| Wipe risk / backing | `wipe`, `wipe_backed` | progress (what a coup takes back) | Keep once calibrated; off now. Replaces `reserve`. |
| Reserve (flat per spare point) | `reserve` | progress | Keep until wipe is on: removing it with wipe at 0 lost the gate (0.328, one nuclear loss). |
| Access: reach into unowned battlegrounds, redundant, chained, contested | `access`, `access_redundant`, `access_chain`, `access_contested` | reach | Keep. This is what non-battlegrounds are for. |
| First mover per stability | `first_mover` | reach | Keep. |
| Non-battleground control tier | `control` | scoring | Removed (0): domination is the region score's job. |
| Southeast Asia tier, realignment leverage | `southeast_asia`, `leverage` | scoring / reach | Removed Sept 2026. |
| VP, Ops scale, military Ops, coup discount | `vp`, `ops`, `military`, `coup_discount` | conversions, not board terms | Keep: they put VP, Ops and dice on one scale. `event` (1.0, a no-op multiplier) removed Sept 2026. |

So the board evaluator to port is seven terms over arrays: battleground x
scoring weight, region score, progress, wipe, access, first mover, and
the region-margin term to come. Everything else is a conversion or a
card-level estimate that stays in Python.
