# Strategic evaluator simplification audit

The 16 weights are all used, but they serve two different jobs: valuing a
position at the search horizon and choosing which moves to simulate. Split
those jobs before removing heuristics. The current MCTS still delegates
opponent replies, most future card choices, event decisions, and ordinary
placements to the strategic policy. It searches only our own scoring-card
turns, with a limited shortlist of card/target macros.

## Weight inventory and recommendations

| Weights | Used in MCTS leaf? | Recommendation |
| --- | --- | --- |
| `progress_curve=1`, `reserve_stability=0` | Yes | First configuration simplification: fix these at their default shapes and remove two tuning dimensions. This preserves default behavior, not arbitrary checkpoints. **Done for `progress_curve`, 2026-09-13** (deleted with `ops`, `wipe` and `wipe_backed`; the parity corpus reproduced unchanged). |
| `event=1` | No | Fix at 1 and remove the extra multiplier. It applies only at play-mode selection, while headline/card selection uses the unmultiplied event estimate. Removing this tuning dimension preserves defaults and removes an inconsistent way to tune event preference. |
| `coup_discount=.9` | No | First behavioral ablation: set to 1. Actual dice already encode failed/inefficient coups, and search simulates actual outcomes. The discount additionally expresses a placement preference; it is not an engine rule or an algebraically redundant term. **Deleted 2026-09-13** on branch `delete/coup-discount`, merged only if its gate accepts (see `scripts/queue_coup_discount.sh`). |
| `scoring_hand=1.2`, `scoring_discount=0.8` (replaced the `scoring_live` urgency multiplier) | No | Test neutral multipliers in the search rollout policy. They can compensate for shallow search, particularly for unseen opponent scoring and at the horizon. Keep the standalone strategic defaults until tested. |
| `military=2` | No | A candidate for reducing rollout guidance once search reliably values end-of-turn penalties. It is already absent from the MCTS leaf, so removing it cannot eliminate duplicate leaf credit. |
| `ops=2` | No | Keep for cheap move proposals/rollouts until card/mode alternatives are actually searched. It is a generic estimate of a card's utility, not a value of the resulting position. **Superseded:** the estimate moved onto `ops_value`, the weight was read nowhere, and it was deleted 2026-09-13. |
| `control=0`, `battleground=5` (`southeast_asia` and `leverage` removed Sept 2026) | Yes | Investigate replacing direct country tier bonuses with future regional VP in a separate leaf evaluator. These weights also scale progress and reserves; zeroing them is not just removing the control bonus. |
| `progress=2.8` | Yes | Reduce only in an independently configurable leaf ablation first. It bridges investments the shallow search cannot finish and still drives move proposals. |
| `reserve=.35`, `access=.65` | Yes | Possible consolidation into a smaller position-potential term, but both represent consequences beyond the one-turn horizon: surviving later attacks and reaching future targets. |
| `region=1.3`, `vp=3` | Yes | Preserve banked VP and future regional potential. Eventually express heuristic values in VP units; simply setting `vp=1` changes tradeoffs with every other weight, hardcoded bonus, and the bounded search utility. |

There are ten weights in the current leaf path (including the two shape
parameters), and six that only affect strategic decisions. Neither urgency
multiplier, nor `ops`, `military`, `event`, or `coup_discount`, appears in
`MCTSPlayer.leaf_return`. They affect search indirectly through its policy.

Fixing the three default-neutral knobs (`event`, `progress_curve`,
`reserve_stability`) would reduce the tuning surface from 16 to 13 without
changing the default formulas. This is a compatibility change for nondefault
models and the trainer, not permission to silently ignore checkpoint fields.
Keep a legacy loader or explicitly reject unsupported nondefault values.

## Simplifications beyond named weights

1. The scoring-card bonus `2 * action_round` is an explicit timing crutch.
   Search can compare banked VP from scoring now versus later, and the engine
   already enforces the scoring deadline. Test removing this bonus from the
   rollout policy alongside neutral urgency. A weak rollout can still score
   too early even when the root search would prefer to build first.
2. The headline Ops charge (`0.5 * ops`), China Card penalty (`4`), and Space
   Race adjustments (`0.4 * ops`, plus `1` in mode selection) are further
   policy assumptions. Headline search is absent, and China's future-turn
   value is outside this horizon; these are not all safe deletions yet.
3. `event_value` runs nested board-event simulations inside MCTS rollouts,
   which already simulate the event afterward. This is a promising speed
   simplification: use a cheaper event proposal policy and let the outer
   search evaluate consequences. But the current tree does not independently
   branch over every event/ops/space choice, so deleting event evaluation
   before adding those alternatives can hide the best move entirely.
4. Do not remove the DEFCON planner or legal-action checks. Sampled rollouts
   are not a substitute for the existing whole-hand safety ranking. Search
   retains uncertainty about unseen attacks and has a finite budget.

## Position value deserves its own experiment

At default weights, a just-controlled BG contributes `5 * (1 + 2.8) = 19`
heuristic units from control and progress alone, before access, reserves,
and regional scoring. A banked VP contributes 3. That is about 6.3 banked
VP worth of country potential. Multiple future scorings can justify a
substantial value, but this is a large implicit forecast for a one-turn
search and should be evaluated explicitly.

A useful alternative leaf is banked VP plus discounted future regional VP
plus a small unfinished-position term. Keep the current rollout/candidate
policy fixed for that experiment. This separates a simpler assessment of
where a simulation ends from the heuristics needed to generate that
simulation, and avoids hiding the same assumptions as unnamed constants.

## Cheap sensitivity check (not a strength result)

On 150 saved strategic decisions from seed 3003, changing one group at a
time changed the chosen action as follows:

| Change | Decisions changed |
| --- | ---: |
| Neutral urgency (`scoring_hand=scoring_live=1`, before the schedule weighting) | 6 / 150 |
| Neutral coup discount (`coup_discount=1`) | 2 / 150 |
| No progress (`progress=0`) | 31 / 150 |
| No reserves (`reserve=0`) | 6 / 150 |
| No access (`access=0`) | 8 / 150 |
| No country tiers (all three tier weights zero, also suppressing progress/reserves) | 58 / 150 |
| No regional potential (`region=0`) | 18 / 150 |
| No military-Ops guidance (`military=0`) | 1 / 150 |
| No generic Ops value (`ops=0`) | 24 / 150 |

This only measures policy sensitivity on a fixed trajectory; it neither
establishes redundancy nor says whether the changed moves are better.
The inputs came from the first 150 player decisions of the strategic vs
strategic game. Evidence: `logs/game-check/strategic-weight-audit.json`
(gitignored). No playing weights were changed by this audit.

## Suggested implementation order

1. Separate leaf evaluation configuration from strategic proposal/rollout
   configuration; preserve the existing defaults as the reference.
2. Remove the three default-neutral tuning dimensions with explicit model
   compatibility handling. Keep the historical trained/experimental models
   usable or fail clearly rather than silently reinterpret them.
3. Test neutral coup discount, then neutral urgency and no round bonus, as
   separate rollout-policy ablations. Measure macro coverage as well as VP
   at scoring; a search cannot recover a move removed from its shortlist.
4. Compare the simpler leaf while leaving candidates and rollouts unchanged.
5. Only afterward replace expensive event proposal evaluation and broaden
   card-mode search. Use fixed simulation counts to check strength per
   sample, and equal wall-time budgets to check the value of speedups.

Use paired seats against frozen strategic and current MCTS policies, with
held-out seeds in addition to 4000-4015. Record scoring VP, completed BG
investments, nuclear losses, truncated rollouts, and decision time. Do not
promote a deletion based solely on the 150-position sensitivity check.
