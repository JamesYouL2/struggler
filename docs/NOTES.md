# Working notes for the next model

A scratchpad for whoever picks this up (Astra, or another model): the
strategy principles the maintainer has stated, what the bots do about
each, and what is still open. Principles are quoted as given; evidence is
linked. Update this file when a principle is implemented or refuted.

## The point of the game

Score VP cheaply and keep maximum pressure on the opponent, while never
committing DEFCON suicide. Everything below is an instance of that.

## Principles from strong play

| Principle | Status in the bots | Evidence |
| --- | --- | --- |
| Never play a suicide card or hand the opponent a fatal coup; plan the whole hand, not the current card. | Done: `bots/defcon.py` whole-hand survival search ranks every card, mode, event choice, discard, coup target and headline before VP. | `docs/DEFCON_STRATEGY.md`; seeds 2400-2403 in `logs/game-check`, all once nuclear losses, now end on VP. 0 nuclear losses in 64 strategic/event-value games. |
| Strong humans always event Grain Sales and Aldrich Ames, and event Terrorism when behind or with Iranian Hostage Crisis. | Noted, not implemented. The bots play these for Ops or space them. The learned hand-attack prior (`bots/opponent_model.py`) is therefore a bot base rate (<1%), not a human one. | `docs/DEFCON_STRATEGY.md` "How strong humans use the attack cards"; `models/opponent-model-v1.json.report.json`. |
| Blockade, Debt Crisis, traps: discards that fire no event are exits; self-trapping dumps Grain Sales / Voice of America / Colonial Rear Guards (USSR) or Decolonization (US). Red Scare + Blockade or a trap is lethal on the table (engine uses printed Ops). | Done in the planner (`trapped` state, pay-or-refuse). Printed-Ops leniency recorded in `docs/LIMITATIONS.md`. | Seed 2401 (Blockade paid away the last spare card) regression test. |
| Play around live scoring cards: a card still in the deck or the opponent's hand can score any round. Southeast Asia Scoring reaches only its own countries. | Done: `scoring_hand`, `scoring_live` weights, per country. Untrained; a 4-generation run found no signal at 8 pairs/generation. | `docs/STRATEGIC_AI.md` "How it plays"; trace in the session log. |
| The deck schedule is static and public: no "future" uncertainty. | Done: `engine.cards.ENTRY_TURN` is the single source; bots use `bots/public_cards.card_state`. | |
| Influence value is not linear: control scores, uncontrolled influence has option value only, over-protection matters mainly where a coup is cheap. | Recorded as `progress_curve` / `reserve_stability` weights; defaults kept linear because with one action of lookahead the linear term is the option-value stand-in. Convex lost 0.33 ± 0.09. | `docs/STRATEGIC_AI.md`; `logs/game-check/shape-ab-convex-vs-linear-4000-4015.json`. |
| DEFCON is not worth much to either side in the Early War. Turn-1 battleground coups are often right (VP, Military Ops). | Done: no DEFCON charge on early coups. | |
| Battlegrounds >> cheap Southeast Asia countries >> other non-battlegrounds. Battleground Ops score domination/control or deny them; SEA countries non-dominate Asia and score later. | Done: `battleground` / `southeast_asia` / `control` tiers in `StrategicWeights`. A turn-1-only rule was tried first and removed as hacky. Tiers + coup discount vs the old flat tiers: 0.55 ± 0.06 on seeds 4000-4015 (0.72 as USSR, 0.38 as US). | `logs/game-check/3003-*` is the testing ground; `logs/game-check/tiers-ab-4000-4015.json`. |
| Coups/realignments should be valued like placement, generally preferring placement (Ops efficiency: a coup on a 2-stability country is -1 Op). | Done: same `delta` pricing, `coup_discount` 0.9. | |
| 1- and 2-stability countries are more VP per Op while their scoring is live. | Already what the influence search maximises (gain per Op); noted, nothing extra encoded. | |
| The opening is known: USSR 4 East Germany / 4 Poland / 1 Austria (or Yugoslavia); US 4 West Germany / 3 Italy, then the +2 handicap to Iran and West Germany. | Done: `OPENING_BOOK` in `bots/strategic.py`; the +2 is `rules.json` "setup_bonus", on in `main.py`, the trainer and the benchmark. The US 4/3 split is an assumption to confirm. | `docs/STRATEGIC_AI.md` "How it plays". |
| Judge a bot at checkpoints, not only by wins: VP scored plus the battleground control difference per region, weighted by how many more times and how soon each region scores (live card: this cycle and after the reshuffle; discarded: after it; Mid War: from turn 4; Southeast Asia once), each turn away discounted. | Done: `python -m struggler.bots.benchmark --stop-turn 1|3|7` (`projection`, `scoring_weights`). Turn 1 MCTS vs strategic is flat: -0.23 total, 8 wins / 9 losses on the 17 seats that searched. | `logs/game-check/*-4000-4015.t1*.json`; per-game logs with `--log-dir`. |

## What is still open, roughly in order

1. Event Grain Sales, Aldrich Ames, Terrorism (with the Hostage doubling)
   in the strategic bot's event whitelist, then retrain
   `bots/opponent_model.py` on new logs so the hand-attack prior means
   something.
2. Scoring-card timing: the US in seed 3003 plays Asia Scoring at -6 on
   turn 1 AR6 with no Asia presence. The bot only has an urgency
   multiplier; it does not plan "build the region, then score".
3. Lone points: the bot places single points that die to 1-Op coups next
   turn (3003, turns 2-3: Colombia, Guatemala, Nigeria). Needs a rule for
   when a single point in an uncontrolled battleground is a liability.
4. The neural bot (`bots/event_value/`) covers 6 events; 59 deck cards can
   move a region's score. The scalable design is generic: fire every live
   card in a sandbox, drive choices with the strategic policy, aggregate
   exposure x swing per region. Not started. Head-to-head it is 0.53 ±
   0.06 against the strategic bot, i.e. indistinguishable.
5. Greedy is a dead opponent (0.00 against strategic). The trainer now
   anchors on frozen strategic weights; 32 games per candidate gives a
   standard error of 0.06, so detecting a 5-point gain needs ~4x that.

## How to look at things

```sh
# narrate a game: plays, events, influence moves, coups, DEFCON, scoring
STRUGGLER_OPPONENT_MODEL=models/opponent-model-v1.json \
  python src/main.py --us strategic --ussr strategic --seed 3003 \
  --log-level INFO --log-file game.log
# WARNING level prints only nuclear risk; DEBUG adds every action and the planner's numbers
# 16-seed paired A/B of a weight change against a rival checkpoint (8 workers, ~3 min)
python -m struggler.bots.train evaluate --opponent strategic --pairs 16 --seed 4000 \
  --rival rival.json --workers 8
```

`logs/game-check/` holds the evidence games (gitignored): `*-after-fix`,
`*-learned-priors`, `3003-*`, and the A/B reports. The baseline that every
change is measured against is seeds 4000-4015, both seatings.

## MCTS prototype follow-up

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
