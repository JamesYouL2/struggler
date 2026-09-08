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

An opt-in `mcts` bot now searches own scoring-card turns with UCT over card
plays and targeted BG investments. Rollout returns include banked VP plus
board potential, with terminal results overriding both. Tests cover the
same-final-board/different-scoring-order case, public-only hidden sampling,
safety, and actually investing before scoring. See `docs/STRATEGIC_AI.md`
"Experimental MCTS prototype" for usage and limits. The strategic bot's
urgency-only behavior remains unchanged. Next: measure paired-seat strength
and search cost before promoting this prototype or expanding its scope.

