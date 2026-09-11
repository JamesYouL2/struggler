# MCTS prototype follow-up

Speed and strength, seeds 4000-4015 both seatings, 24 simulations, vs
strategic (`logs/game-check/mcts-vs-strategic-4000-4015.*.json`):

| Rollout policy | Score | Nuclear losses | Search (s, 6-8 concurrent) |
| --- | ---: | ---: | ---: |
| Full strategic policy in rollouts (before `bots/rollout.py`) | 0.656 | 0 | 11.3 |
| Immediate-only survival guard | 0.422 | 2 | 6.0 |
| Hybrid: full search when DEFCON <= 3 and a hazardous card is held | 0.469 | 0 | 4.6 |

The cheap rollouts cost strength: the search is 2.4x faster but the
rollouts are a worse model of play. Ablations (`STRUGGLER_ROLLOUT_OPTIONS`
`full_planner` / `serve_plans`) are the next measurement. The seed 4004
USSR turn-1 review shows the other weakness: 11 root macros over 24
simulations is 2-3 visits each, values within noise, and a targeted macro
forces a card (De-Stalinization, Duck and Cover) to be played for Ops.
Candidates: drop targets we are chasing (opponent present, we absent, no
adjacent control), no Ops macro when the event is worth more than the Ops,
cap macros at ~6 or raise simulations to 48.

An opt-in `mcts` bot now searches own scoring-card turns with UCT over card
plays and targeted BG investments. Rollout returns include banked VP plus
board potential, with terminal results overriding both. Tests cover the
same-final-board/different-scoring-order case, public-only hidden sampling,
safety, and actually investing before scoring. See `docs/STRATEGIC_AI.md`
"Experimental MCTS prototype" for usage and limits. The strategic bot's
urgency-only behavior remains unchanged. Next: measure paired-seat strength
and search cost before promoting this prototype or expanding its scope.

Speed follow-up: profiling the prototype led to exact evaluation caching,
control-aware regional rescoring, deduplicated realignment evaluation, and
cheaper isolated observations/information keys. Three alternating local
runs measured 1.44x strategic and 1.61x MCTS speedups with identical rankings
and root values. See `docs/STRATEGIC_AI.md` for workloads and evidence.

The simplification audit is in `docs/STRATEGIC_SIMPLIFICATION.md`: all 16
weights are used; ten feed the MCTS leaf and six only its strategic policy.
First candidates are fixing the three default-neutral knobs, then testing
neutral coup discount and urgency. The audit includes a 150-position
sensitivity check and a separate-leaf ablation plan. No weights changed.
