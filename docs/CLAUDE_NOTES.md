# Claude working notes (Fable)

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
| Play around live scoring cards: a card still in the deck or the opponent's hand can score any round. Southeast Asia Scoring reaches only its own countries. Battleground control in an unscored region >>> in a scored one, and Mid War regions grow in value as turn 4 nears. | Done: importance x expected future scorings, discounted per turn away (`scoring_schedule`, `scoring_discount`, `scoring_hand`). | `docs/STRATEGIC_AI.md` "How it plays". |
| The deck schedule is static and public: no "future" uncertainty. | Done: `engine.cards.ENTRY_TURN` is the single source; bots use `bots/public_cards.card_state`. | |
| Influence value is not linear: control scores, uncontrolled influence has option value only, over-protection matters mainly where a coup is cheap. | Recorded as `progress_curve` / `reserve_stability` weights; defaults kept linear because with one action of lookahead the linear term is the option-value stand-in. Convex lost 0.33 ± 0.09. | `docs/STRATEGIC_AI.md`; `logs/game-check/shape-ab-convex-vs-linear-4000-4015.json`. |
| DEFCON is not worth much to either side in the Early War. Turn-1 battleground coups are often right (VP, Military Ops). | Done: no DEFCON charge on early coups. | |
| Battlegrounds >> cheap Southeast Asia countries >> other non-battlegrounds. Battleground Ops score domination/control or deny them; SEA countries non-dominate Asia and score later. | Done: `battleground` / `southeast_asia` / `control` tiers in `StrategicWeights`. A turn-1-only rule was tried first and removed as hacky. Tiers + coup discount vs the old flat tiers: 0.55 ± 0.06 on seeds 4000-4015 (0.72 as USSR, 0.38 as US). | `logs/game-check/3003-*` is the testing ground; `logs/game-check/tiers-ab-4000-4015.json`. |
| Coups/realignments should be valued like placement, generally preferring placement (Ops efficiency: a coup on a 2-stability country is -1 Op). | Done: same `delta` pricing, `coup_discount` 0.9. | |
| 1- and 2-stability countries are more VP per Op while their scoring is live. | Already what the influence search maximises (gain per Op); noted, nothing extra encoded. | |
| Blockade paid with a US/neutral 3-Ops card is great for the USSR; paid with De Gaulle / Socialist Governments / Suez Crisis it is good for the US (event never fires). Discards return at the reshuffle, so dumping Decolonization / De-Stalinization delays them, it does not remove them. | Noted, not priced: the pay choice scores flat minus printed Ops, and the USSR-seat sandbox assumes the US cannot pay (Blockade values 39.7 to the USSR, 0 to the US on the opening board). | `docs/DEFCON_STRATEGY.md` "Hand discard effects". |
| The opening: USSR 4 East Germany / 4 Poland / 1 Austria (or Yugoslavia). US old school is 4 West Germany / 4 Italy / Iran to 2 (7 in Western Europe plus the +2 handicap). Preferred: 3 West Germany / 3 France / 2 Italy / Iran to 2. The 3rd Italy point and the 4th France point are worth a lot while Socialist Governments, De Gaulle and Suez Crisis are in the deck. UK to 6 / Canada to 3 is also viable, for NORAD and Special Relationship. The Nordics should never be filled in any game. | Partly: `OPENING_BOOK` in `bots/strategic.py` plays 4 West Germany / 3 Italy, then the handicap to Iran and West Germany (West Germany 5 / Italy 3), which is neither line above. The +2 is `rules.json` "setup_bonus", on in `main.py`, the trainer and the benchmark. The book should move to the preferred line, or the value function should find it on its own. | `docs/STRATEGIC_AI.md` "How it plays". |
| A plain non-battleground is worth nothing of its own: its control only moves the domination tally, which the region score computes. What is left is adjacency, and adjacency to battlegrounds we do not own matters more than adjacency to enemy-controlled ones: it is what lets us place, coup and re-enter after Nasser or Fidel, and realignments are the rare use. Israel next to an empty Egypt is the test case. | In progress (uncommitted): `control` weight 0; `_access` rewritten to pay for every adjacent battleground not ours at its control value over stability (full when this holding alone reaches it, `access_redundant` 0.35 otherwise) plus `access_chain` 0.4 for battlegrounds two steps away through a country not yet held; `access` weight 0.65 -> 1.0. Table: Suez 10.7 -> 14.1, Israel's point 6.8 -> 14.1 (user: still low), De-Stalinization 60.6 -> 79.2, Nasser 40.5 -> 45.6, Marshall 24.8 -> 14.9 (unchanged by this; France and domination denial are the missing pieces), 1 US Op 16.4 -> 18.5. Suez still far below its ~2.5-Op target: UK 5 -> 3 is worth 1.6 because `region_score` is the exact tier score and sees no country-count margin, so "domination replacement" is unpriced. Dice averaging (2a3f12c, reverted, re-landed after the VP fix): following every face of a `*_ROLL` decision on a forked engine halves the wars (Arab-Israeli War 33 -> 16.5, Korean War 26.8 -> 13.4), which is correct in expectation and lost the gate: 0.359 against the access commit, mean total -5.7. Cause, from seeds 4014 and 4006 as the US: at ~15 the wars price under 2 Ops, so the US plays Korean War and Arab-Israeli War for Ops and lets them fire, and a success wipes South Korea or Israel, an unbacked lone point the linear function cannot see as a lockout. The middle roll had been standing in for that tail. Re-landed once VP was priced in Ops: the wars' Ops value was never the problem, their VP was. With both changes the opening fixture reads Korean War -1.07 against the expert's -1.00, Indo-Pakistani War 0.50 against 0.50, Arab-Israeli War -1.26 against -1.78, Olympic Games 0.15 against 0.30; 25 -> 24 misses. MCTS is untouched either way: the tree samples the live engine, the sandbox only ranks cards. | `python -m struggler.bots.benchmark --table`, HEAD vs working tree. |
| Marshall Plan on the opening board is a little over 3 US Ops: seven points is at most 3 battleground points (West Germany and Italy cushions, France's first step) worth at least 2 Ops, plus 4 non-battleground points and NATO enablement together worth about 1 Op, closer to 1 than 2. It denies Europe domination for good (Spain and Turkey are never cheaply reachable afterward) and insures UK/France against Suez and Arab-Israeli War. It does not give immediate domination: France still needs 3. Worth more than US/Japan Mutual Defense Pact at the start. Its strength is conditional on the opening: holding Marshall you spread the 7 + 2 instead of stacking West Germany or Italy to 5, both of which are wastes; the opening book cannot see the hand, so the table's Marshall row is measured on the wrong board. | Table target ~50-55 on the current scale (1 US Op = 16.4). HEAD says 24.8, the leverage draft 15.4. The per-country function is additive, so the collective domination-denial value can only come from the region score; check whether the sandbox's region score sees "presence in seven non-battlegrounds makes USSR domination impossible" or only present domination. | Turn-1 table rows for Marshall Plan, US/Japan, Suez Crisis. |
| Romanian Abdication and Independent Reds are near zero until the USSR holds the Europe battleground lead; Romania is only a domination count. The table's 0.0 for them with `control` at 0 is right, not a bug. | Accepted. | Turn-1 table. |
| Judge a bot at checkpoints, not only by wins: VP scored plus the battleground control difference per region, weighted by how many more times and how soon each region scores (live card: this cycle and after the reshuffle; discarded: after it; Mid War: from turn 4; Southeast Asia once), each turn away discounted. | Done: `python -m struggler.bots.benchmark --stop-turn 1|3|7` (`projection`, `scoring_weights`). Turn 1 MCTS vs strategic is flat: -0.23 total, 8 wins / 9 losses on the 17 seats that searched. | `logs/game-check/*-4000-4015.t1*.json`; per-game logs with `--log-dir`. |

## Turn-1 review (seed 4004, and the opening board)

`logs/game-check/*.t1*.json` and the scratch table of every Early War
event's value on the opening board found, and fixed, in
`bots/strategic.py`: De-Stalinization played for Ops (not simulated: 23 of
101 events were), Nuclear Test Ban's 3 VP over 4 Ops (Ops priced flat at
2), Fidel spaced ahead of Decolonization (both collapsed to the space
value; one space slot now goes to the worst card), Five Year Plan carrying
a 25% "loss" at DEFCON 5 (chain risk now gated on DEFCON 2), and stakes in
already-reachable Eastern Europe earning access. New strategic vs the
previous strategic: 0.84, +11 VP mean, on seeds 4000-4015 both seatings
(`logs/game-check/strategic-new-vs-old-4000-4015.json`;
`python -m struggler.bots.benchmark --bot strategic --opponent strategic@<old strategic.py>`).

The VP weight against the new Ops scale: 3 / 6 / 10 score 0.81 / 0.88 /
0.88 against the previous strategic bot, and 6 and 10 score 0.45 and 0.50
against the current default (3) in mirror matches on the same seeds
(`logs/game-check/vp-*`). No signal at 32 games; the default stays 3.

### The VP-unit value function: tried, reverted, worth retrying

Commit 2d72916 (reverted by 3f3baad) put every weight in VP: a country =
its tier's VP per scoring x the region's expected remaining scorings; a
stake = control value x conversion ** (Ops still needed); reach = a share
of the option it opens, priced by its cost; the exact region score scaled
the same way; Red Scare/Containment = rounds x marginal Op value; CIA
Created = what the granted Op buys. The turn-1 table then read the way a
strong player reads it (Nasser = two USSR Ops, Nuclear Test Ban 3 against
a 4-Ops card's 12-16, COMECON free, Vietnam Revolts up for Thailand
reach). It lost anyway: 0.31 against its parent (ab50946), 0.125 after
three follow-ups (headline = event - half its action-round use, military
credit 0.5, every future scoring cycle counted), 0.20 with the cycles
off; seven weight ablations at the turn-3 checkpoint (tiers x3/x5/x8,
discount 0.6, region 0.4, access/reserve down) all trailed by 3-6 total.
The turn-3 battleground map showed it ceding Middle East and Asia while
taking Africa and South America. The unmeasured suspects are the stake
form (conversion odds vs the linear fraction), the reserve (0.16 VP vs
0.6 VP a point), and the region score's ten-times larger share. Evidence:
`logs/game-check/vpunits*`. The form is right; the calibration needs the
checkpoint benchmark one structural change at a time, not all at once.

UN Intervention is kept for the opponent's card in hand whose event hurts
most (`un_card`): that card's Ops are valued clean, the space slot skips
it, and UN alone is worth the harm it cancels. Measured neutral against
its parent (0.41 with a De-Stalinization relocation plan, 0.44 for the
plan alone, so the pairing itself is within noise); kept because it is
the stated principle (UN + Marshall Plan is four clean Ops).

Still wrong on that board, by human judgement: Marshall Plan at 13.6 (one
Op) is far too low, COMECON at 5.4 slightly high. Both are the same gap:
a stake is valued by its fraction of the way to control, not by its odds
of converting to control by scoring time and what that control would do
to domination. Flag events value 0. The VP weight (3) has not been
recalibrated to the new Ops scale.

## US opening setups: the math (opening board, seed 4000)

Seven setups (final influence; the US has 7 in Western Europe plus the +2
handicap, Iran starts at 1). "Value" is the value function from the US
seat. The threat columns are the US Ops needed to regain control of every
Western Europe battleground it held, after the USSR's best choice (1 per
point, 2 while the USSR controls it). "Coup4" is a 4-Ops USSR coup on
Italy at DEFCON 5, expected Ops to restore and the chance control is
lost. "WG break" is the USSR Ops from East Germany to end US control of
West Germany.

| Setup | Value | Soc. Gov. | De Gaulle | Suez | Coup4 E[Ops] | P(lose) | WG break |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 4 WG / 4 Italy / Iran 2 (classic) | 53.2 | 2 | 0 | 0 | 2.33 | 0.67 | 2 |
| B 3 WG / 3 France / 2 Italy / Iran 2 | 58.3 | 3 | 3 | 2 | 6.00 | 1.00 | 0 |
| C 5 WG / 2 Italy / Iran 3 | 53.2 | 2 | 0 | 0 | 6.00 | 1.00 | 4 |
| D 5 WG / 3 Italy / Iran 2 (book) | 53.2 | 1 | 0 | 0 | 4.00 | 0.83 | 4 |
| E 4 WG / 2 France / 2 Italy / Iran 2 | 63.5 | 3 | 0 | 0 | 6.00 | 1.00 | 2 |
| F 4 WG / 3 France / 2 Italy / Iran 1 | 53.3 | 3 | 3 | 2 | 6.00 | 1.00 | 2 |
| G 4 WG / 3 Italy / Iran 3 | 53.2 | 2 | 0 | 0 | 4.00 | 0.83 | 2 |

Two findings. The value function cannot tell A, C, D and G apart: the
reserve term is linear in excess points, so two spare points are worth
the same wherever they sit, and it has no notion of coup protection
(Italy at 2 is a certain loss to a 4-Ops coup, at 4 it holds a third of
the time). And it prefers E by 10 for two uncontrolled France points,
the progress term paying linearly for lone points: the "lone points"
item below. On the exposure math the classic 4/4/2 is the safest line
(De Gaulle and Suez cost nothing, the coup costs least); the 3 WG lines
leave West Germany open at 1 Op per USSR point, which is the strongest
single argument against them. What the table does not price: tempo
(France control before the USSR can enter it), NATO, and the +1 to
Iran's Middle East reach.

## What is still open, roughly in order

The value-function programme (Sept 2026), each step gated by
`scripts/gate.sh` against the previous one, one structural change per
branch:

1. Done. (a) e56aecb `control` 0 and the `_access` rewrite: gate 0.469
   against c89629e (mean total -0.7, within the 0.06 standard error),
   0.906 against the pre-session bot; turn-3 checkpoint -1.8, Asia
   battlegrounds -0.41 per game, and seed 4009 as the USSR shows why:
   Socialist Governments for Ops into Pakistan 2 / South Korea 1, footholds
   the access term likes and the linear progress term does not punish.
   Landed as within noise; watch Asia. (b) 2a3f12c dice averaging: 0.359,
   reverted, see the dice row above; re-land after step 2.
2. Backing and wipe risk (in progress: coded, weights 0). First-mover
   tempo per stability and contested-reach discount landed first (clean
   commit). Calibration anchors from the expert: a controlled Thailand
   backed from Malaysia is worth ~2x the unbacked one while the USSR can
   coup there; a USSR point in Israel is ~3/5 of a Saudi Arabia point;
   Iraq is the USSR's best first Op because two cheap Ops there swing
   Middle East battleground domination, which is plan step 3's term, not
   this one. Two framings tried: risk x importance (weight 8) orders the
   USSR list but prices a lone controlled Thailand negative; risk x stake
   (weight 1.5) is bounded but makes a second Iraq point look worse
   (more at stake, less wipe chance). The expert's formula, now coded:
   an unbacked wipe where the couper gets there first flips the
   battleground (stake = our position + the country's control value); a
   backed one they still have to flip to control (stake = our position x
   `wipe_backed`). Thailand is special (the China counter-coup), so the 2x
   anchor is an upper bound, not the target. Weights still 0. A holding is backed when a neighbour holds our
   influence (or home adjacency). Price every held country by the chance
   the opponent's best coup wipes it (roll + Ops - 2 x stability >= our
   points, gated by the DEFCON coup rule), times a lockout multiplier
   when unbacked and a repair cost when backed. Replaces the linear
   `reserve` term (which cannot tell 4 WG/4 Italy from 5 WG/2 Italy),
   gives lone points their real value (a liability unbacked, an asset when
   they back a battleground), and makes the attacker's coup evaluator see
   an Italy coup on an unbacked board as a lockout and an Iran coup as a
   normal wipe. Test cases: the opening-setup table above, Italy after De
   Gaulle + Suez, Israel's point at ~1 Op.
3. Region margin. First fit (presence 3.0 everywhere, battleground 0.5)
   went 31 -> 26 misses and lost its clean gate 0.375: a presence weight
   of 3 makes a first point in any empty region worth three battleground
   units of progress, so the bot scatters footholds that die (the lone
   points failure again; the fixture only sees the opening board). Retry:
   presence credit only in live regions (scoring weight >= `margin_live`
   1.0), presence 1.0, battleground margin 0.25 with progress toward an
   uncontrolled battleground counting fractionally (stepwise linear:
   progress, the control step, then `reserve` for over-protection), and
   `control` 1.5 (a plain country a quarter to a third of a battleground,
   per Op between a 4- and a 3-stability battleground). 25 misses. Clean
   gate (1a03954 vs c5446e0, 32 seeds): 0.672, mean total +6.4, the
   session's first clear gain. Landed. The
   first version on the region score's VP scale (1.3 raw per VP) could not
   move anything. Original item: country-count margin toward domination in `region_score`: the exact
   tier score sees nothing until a tier flips, so UK 5 -> 3 is worth 1.6,
   Marshall's seven countries are worth nothing collectively, and Suez's
   "domination replacement" cost is unpriced. Price the margin in
   countries and battlegrounds toward the next tier, weighted by the
   region's scoring weight. Targets: Suez ~2.5 US Ops, Marshall ~3.
4. Opening from the hand: the book cannot see Marshall Plan, De Gaulle or
   Suez in hand; with 2 and 3 in place, evaluate setups (the table above)
   with the value function plus the held events, and either let the
   function choose or key the book on the hand. Then the Marshall row is
   measured on the right board.
5. Scoring-card timing: the US in seed 3003 plays Asia Scoring at -6 on
   turn 1 AR6 with no Asia presence. The bot only has an urgency
   multiplier; it does not plan "build the region, then score".

Behind those: Grain Sales, Aldrich Ames, Terrorism in the strategic
event whitelist and a retrain of `bots/opponent_model.py`; the generic
event-exposure design for `bots/event_value/` (0.53 +/- 0.06 vs strategic,
indistinguishable); the trainer's dead greedy opponent and its 32-game
standard error of 0.06.

## The value function's terms, and which to keep

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

## Architecture, as of Sept 2026

What the strategic bot is: a one-action-lookahead policy over a
hand-crafted value function (per-country terms summed, plus the exact
region score), events priced by firing them in a public-information
sandbox driven by the same policy, a separate whole-hand DEFCON survival
planner that ranks cards before value does, and an opt-in MCTS that
searches scoring turns with the same value at the leaves. Games run in
1-3 seconds; the gate at 16 seeds both seatings has a standard error of
0.06 and cannot see a 5-point gain.

Is it the right shape? For the compute here (8 cores, no GPU worth
speaking of) and an expert in the loop, yes: every principle the expert
states becomes a term whose effect is visible in the turn-1 table within
a second, and the learned alternative (`bots/event_value/`) reached
0.53 +/- 0.06, indistinguishable. The costs are the ones this session
hit: the value is additive per country, so every interaction (backing,
domination margins, hand-conditional openings) is a new term, and each
term is a weight the games cannot tune.

Three things to do about that, cheapest first:

- Done: `models/expert_valuations.json` holds the expert's prices in US
  Ops on the opening board; `benchmark --expert` diffs them (5 misses at
  e56aecb: Marshall 0.7 vs 3.2, Suez -0.85 vs -2.5, three orderings).
  Containment and Red Scare were the flat `rounds x ops` formula (0.48 Ops each); now priced from the hands they touch, capped at the action rounds left (b18b7a9, 73a52bd: 3.5 and 5.8 Ops at the turn-1 headline, falling linearly by round). Gate at 16 seeds: 0.547 vs base, 0.719 vs the pre-session bot (down from 0.906); at 64 seeds (SE 0.03): 0.582 vs base (+4.7 mean total), 0.789 vs pre-session. Landed: a clear gain against its base; the anchor sits ~0.1 under the earlier 16-seed readings, real but small, cause not yet found (losses are Mid War, turns 9-10; seed 4006 as the US is the one to narrate). Most rows are still unpriced. Next: fit weights to it.
- Spend the compute on seeds, not on runs: the anchor game set every
  third commit, and the base set at 64 seeds (SE 0.03) instead of 16.
  Full games cost about a minute per 16 seeds per seating on 4 workers.
- Fold terms as the structural ones arrive: the backing/wipe term
  replaces `reserve`; `leverage` (realignment next to enemy
  battlegrounds) is now marginal and can fold into `_access` as a
  control-only bonus; `southeast_asia` is a tier that the region score
  and access should make redundant. The simplification audit in
  `docs/STRATEGIC_SIMPLIFICATION.md` has the sensitivity numbers.

## Resolved: the two "nuclear losses" were the gate measuring the working tree

Gates on 873d9d9 and c5446e0 each reported one nuclear loss as the USSR.
Neither reproduces: the same commit, seeds and opponent, run from a
clean checkout, gives 0.867 and 0 nuclear losses. The gate ran each
benchmark as a fresh process importing the live `src/`, and the working
tree was being edited (the margin term, at its wrong VP scale, among
other drafts) while the later steps ran. Every gate from 50e8bff to
c5446e0 is therefore suspect, including 873d9d9's 0.328 failure.
`scripts/gate.sh` now checks HEAD out into a temporary worktree and runs
from it; the anchor run is off unless GATE_ANCHOR=1; defaults are 32
seeds, 8 workers, base HEAD~1. The chain was re-gated cleanly after.

## Codex's MCTS findings (docs/CODEX_NOTES.md)

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

## Option C, step 1: the parity corpus

`scripts/capture_corpus.py` plays strategic-vs-strategic on seeds
4000-4003 and records, at headline, action-round, play-mode, Ops-type,
placement and coup decisions on turns 1/3/5/7/9 (rounds 1/3/6), the
serialized engine plus the current outputs: the full ranking with safety
keys, every country value, region scores and margins, the Ops scale, and
the planner's whole-hand, per-card and event risks. 455 positions,
`tests/corpus/positions.json.gz` (250 KB). `tests/test_parity_corpus.py`
rebuilds each position with a fresh bot and requires exact rankings,
values within 1e-9 (absolute and relative) and identical risks; it runs
in ~15 s. Regenerate only by an explicit commit.

Capturing it found a leak: `_event_basis` (the sandbox's per-country and
per-region values for the current board) was keyed on influence alone and
survived across decisions, so a headline's basis, computed with the
headline's scoring weights, priced the events of the following action
round when the board had not changed. Reset per `rank_actions` now; the
corpus was captured after the fix. Fresh baseline on the gate snapshot:
see the gate report for the commit (`mean_game_seconds`).

## Option C, step 1: baseline profiles (8ba89db, gate running concurrently)

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

## For Astra: handoff, 2026-09-08 evening

What changed since your Option C decision, what to check, and what I am
asking you.

**Your three MCTS findings are fixed and pinned** (98cdc1f, 95deb39):
`StrategicPlayer.evaluate(observation, board)` gives leaves their own
context; `RolloutPolicy.rank_for_target` re-ranks a steered placement and
drops the served plan for the rest of the spend; cache hits sync the
board and `MCTSPlayer._controls` reads the observation. Regressions are
your three probes, in `tests/test_mcts.py`. Please re-audit the fixes
rather than the tests: in particular whether dropping the served plan
after a steered point is the semantics you intended (the alternative,
re-planning around the target, keeps the plan's other countries).

**Option C step 1 is done** (8ba89db, 9ebf082). Corpus:
`tests/corpus/positions.json.gz`, 455 positions from seeds 4000-4003,
turns 1/3/5/7/9, rounds 1/3/6 plus headlines, both seats, six decision
kinds; each record is the serialized engine plus the ranking with safety
keys, all country values, region scores and margins, the Ops scale, and
the planner's whole-hand, per-card and event risks, `hazardous` flags
and node count. `tests/test_parity_corpus.py` rebuilds every position
with a fresh bot: exact rankings, values within 1e-9 abs+rel, identical
risks. Not yet in the corpus, from your list: rollout and event-sandbox
positions, generated boundary cases (cost transitions, tier thresholds,
Europe control, near-ties, bonus Ops, effects, influence extremes,
planner truncation), learned-prior context. Please say which of these
you want before the evaluator slices start, and which can follow.

**The corpus found a leak on its first run**: `_event_basis` survived
across decisions keyed on influence alone (a headline's basis priced
action round 1's events with the headline's scoring weights). Reset per
`rank_actions`; the corpus was captured after. Gate 0.469, neutral.

**Baseline profiles** are in the section above and in
`scripts/profile_baseline.py`. The morning's "planner 60 %" was
cumulative and mostly evaluator time; exclusive the planner is 10 % of a
game and ~0 % of a search, while `delta` is 53-73 % of both and the
region-margin term alone 10-14 %. By your rule I propose deferring step
2 (planner memoisation, ceiling 1.1x) and starting step 3 with the two
cheapest evaluator slices, `region_margin` and `_access`, each measured
alone. Please confirm or object. Note the "MCTS opening" profile is
empty: MCTS searches only turns with a scoring card in hand, so the
opening position fell back to the policy. If you want a search profile
on turn 1, name a position with a scoring card or I will construct one.

**MCTS on every turn, measured** (`search_all`, `STRUGGLER_MCTS_SEARCH_ALL=1`;
seeds 4000-4003 both seatings, 24 simulations, vs the plain policy, 8
games each so +/-0.15):

| MCTS mode | score | mean total | s / game |
| --- | ---: | ---: | ---: |
| scoring-card turns only (current) | 0.75 | +8.7 | 164 |
| every action-round play | 0.50 | +1.5 | 714 |

Searching every turn is 4.4x slower and no stronger, worse on this
sample. The option stays off. The more interesting number is the control
row: with the three semantic fixes in, scoring-turn MCTS beat the plain
policy 0.75 on 8 games where the pre-fix baseline was 0.53 +/- 0.06 on
64. That wants a 32-seed run before anyone believes it (about 25 min).

**Plan**: `docs/RUST_PORT_PLAN.md` revision 3 carries your order and the
consolidated leftovers. `scripts/gate.sh` now snapshots HEAD into a
worktree (your point about the shared venv stands for a native
extension and is recorded in the plan).

## VP in Ops (the largest miscalibration found so far)

The flat `vp` weight of 3.0 raw priced a VP at 0.14 Ops on the opening
board and 0.08-0.23 Ops in the Mid War. The expert's rule: 1 Op = 2 VP in
the Early War (a VP is 0.5 Op), 1 Op = 1 VP in the Mid War, 2 Ops = 1 VP
in the Late War: Ops are worth most while the board is empty, VP most
when few turns remain to convert Ops. `StrategicPlayer.vp_value(obs)` =
era rate x `ops_value(obs, 1)`, so VP and Ops stay on one scale as the
board's Ops value moves (`vp_early` 0.5, `vp_mid` 1.0, `vp_late` 2.0; a
per-turn table is the refinement if tuning wants it). Used by the event
sandbox, scoring cards, wars, the space race, Yuri and Samantha, the
neural correction and the MCTS leaf. A reentrancy guard prices a VP at a
flat 20 raw per Op while the one-Op value is itself being computed
(coups and placements can price VP). The expert first stated the rule
inverted (2 Ops per VP early); the opening fixture (Olympic Games 0.3,
Korean War -1) showed ~0.5 and the corrected rule agrees. Opening fixture
unchanged at 25 misses; corpus regenerated (506 positions) as an
intentional semantic change.

## Astra's corpus review (2026-09-08): what was done

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

## Where this stands: one failing test, one uncommitted slice

### The failing test

`tests/test_parity_corpus.py::test_evaluator_and_planner_reproduce_the_corpus`
**passes on its own (2 tests, 120 s) and fails inside the full suite**
(`1 failed, 489 passed, 3 skipped`). Same six records every time: indices
121, 122, 130, 131, 135, 136, all reported as `ranking order`, all seed
4000 turn 9 placement decisions with a cluster of candidates whose value
is 2.4668 to fourteen significant figures.

Verified facts:

- pytest 9.1.1 with no random-ordering plugin, so collection order is
  deterministic and this is a real state leak from an earlier test file,
  not flakiness.
- The reordering is confined to candidates whose values agree to ~1e-14;
  no value moves by more than that.
- Run alone, those six records reproduce the corpus exactly.

Not yet established: which test leaks. `Board.__init__` copies the
country mapping (`dict(countries)`) and `CountryInfo` is frozen, so a
per-board battleground promotion cannot leak, but `_adjacency` is the
shared dict from the `lru_cache`d `_static_map()` and is only shallow
referenced, so a test that assigns `board._adjacency['US'] = ...` would
leak globally. `RULES` and the module-level `CARDS` are the other shared
mutables worth checking.

Next diagnostic, cheapest first:

1. `pytest tests/<file>.py tests/test_parity_corpus.py` bisected over the
   test files that run before it alphabetically, to name the leaking file.
2. In that file, look for assignment to anything reached through
   `_static_map()`, `RULES`, or `CARDS`.
3. Fix the leak in the test (or make the shared structure defensively
   copied), rather than loosening the parity assertion.

Do not weaken the checker to make this pass. It is reporting a real
cross-test dependency.

### The uncommitted region-margin slice

Working tree (uncommitted): `src/struggler/bots/strategic.py`,
`scripts/capture_corpus.py`, `tests/test_parity_corpus.py`,
`tests/test_strategic.py`, `tests/corpus/positions.json.gz`.

This is Option C step 3's first evaluator slice (Astra's recommendation:
region-margin work before a broad indexing rewrite). What it does:

- `_margin_basis(board, region)` caches the region margin's aggregates
  per region for the life of one ranking, under the same contract as
  `_base_regions` (cleared wherever that is cleared, including both
  commit points inside `ops_value`). The hot path no longer builds an
  influence-keyed cache entry per trial placement.
- `_margin_swapped(basis, ...)` swaps one country's contribution into
  those aggregates. The fractional battleground total is rebuilt by
  re-summing the per-member fractions **in member order**, which is
  bitwise identical to the full walk because `x + 0.0 == x`. The old
  `a[1] - o[1] + n[1]` was only close, and that was enough to reorder
  near-ties and flip `_investment`'s strict `>`.
- `region_margin_after` is kept for callers that hold no basis.

Measured on an idle machine, best of three (rankings) and best of two
(game):

| | old | new |
| --- | ---: | ---: |
| 40 placement rankings | 0.34 s | 0.30 s |
| strategic full game, seed 4000 | 7.4 s | 6.3 s |

About 15 % on both. Note the full game is 6-7 s here, not the 13.4 s in
the baseline table above: that earlier figure was taken with a gate
running concurrently, exactly as Astra warned.

The existing incremental-vs-full test now asserts **bitwise** equality
rather than a 1e-9 tolerance.

Not committed because the suite is not green. Commit it only once the
leak above is fixed and the parity test passes in the full suite, then
gate it: it is a behaviour change (it removes six near-tie reorderings
and changes some `_investment` point counts), not a no-op.

### Finding worth telling Astra: `delta` is not a pure function of the board

Chasing the last parity mismatch turned up something more important than
the mismatch. `StrategicPlayer.delta` returns values that differ in the
last bit depending on what was computed before it on the same instance,
because it reads per-decision caches (`_base_regions`, `_base_margins`,
`_country_cache`, `_region_cache`). Concretely, on corpus record 381
(seed 4002 T5 AR6 USSR), `delta(France, own=1)` is 3.6977777777777776
during the generator's delta pass and 3.697777777777777 when called
after a different warm-up. `_investment` compares gains with a strict
`>`, so a one-ulp difference silently flips the chosen point count
between 1 and 2.

Consequences:

- The corpus now records the per-point gains alongside the chosen point
  count, and the checker enforces the point count only where the best two
  gains differ by more than 1e-12. Where they do not, either answer
  reproduces the same value per Op.
- This is a direct argument for the plan's pure-function evaluator step:
  a kernel that reads no caches cannot have this property, and until it
  exists, "identical rankings" is only reproducible for a fixed call
  sequence. Astra's insistence on recording query order was right for the
  planner and turns out to apply to the evaluator too.

### Next steps, in order

1. Find and fix the cross-test state leak; get the suite green.
2. Gate the region-margin slice (behaviour change, 15 % faster).
3. Report the slice on its own, per Astra: isolated snapshot, repeated
   unprofiled timings, fixed ranking statistics, no other work running.
4. Then either the next evaluator slice (`_access`, 11-16 % of profiled
   time) or the pure-function extraction, which the finding above makes
   more valuable than it looked.

Steps 1-3 are done. Step 4 was settled by measurement in favour of the
extraction; see the 2026-09-09 section at the end of this file.

## How to look at things

The gate for any value-function change is `scripts/gate.sh [base-ref]`
(runs from a snapshot of HEAD; base defaults to HEAD~1; the anchor run
needs GATE_ANCHOR=1 and is parked until the Rust speed-up lands).

**Its exit status is the verdict.** It used to print numbers and exit 0
whatever they said, so "the gate passed" only ever meant "the gate ran",
and these notes have used the word wrongly more than once. The rules are
in `benchmark.acceptance` and are deliberately asymmetric: no nuclear
losses, two samples over disjoint seeds and 150+ finished games, and a
pooled score whose one-sided 95% upper bound reaches 0.500. A change is
blocked only when the games say it is *worse*. At 32 seeds most real
changes are not measurable in either direction, and a rule that demanded
proof of improvement would block all of them.

A seed counts once, not once per seat: both seats play the same deal from
the same shuffle, so counting them separately understates the spread and
makes noise look like a result.

The held-out range (5000-5063 by default) exists because selecting change
after change on 4000-4031 is how a bot overfits its own benchmark. It
earned its place immediately: the event-basis fix scored 0.469 on the
tuning seeds and 0.555 held out.

The rest of the gate is diagnostics to read, not rules: the turn-1
event-value table (`python -m struggler.bots.benchmark --table`, read by
eye against your own judgement), the expert valuation diff (`--expert
models/expert_valuations.json`: the expert's prices in US Ops on the
opening board, the bot's values converted on its own Ops scale, misses
over 0.5 Ops flagged, ordering constraints checked, unpriced rows listed
as a to-do), and the turn-3 checkpoint. The expert check is deliberately
not a rule: it is a handful of hand-priced rows whose miss count moves by
one or two on changes that are otherwise clearly fine. One structural
change per branch. When a check fails, bisect, do not tune.

The Rust plan is `docs/RUST_PORT_PLAN.md`.

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

## 2026-09-09 — The pure-function extraction, and the bug that forced it

Two commits. The first is a behaviour change and the second is provably
not, which is the only reason the second is safe to review by its diff.

### What the choice actually turned on

The overnight handoff offered `_access` precomputation or the pure-function
extraction and said to revert the former if it did not pay. Measured on its
own workload (the first 40 placement corpus records, five unprofiled
passes), the uncommitted precompute slice was inside run-to-run noise:
medians 0.418 s and 0.366 s at HEAD against 0.422 s and 0.421 s with it.
`_access` was also 7% of cumulative time on that workload, not the 10-16%
the handoff carried forward. So it was reverted, per the handoff's own rule.

The profile said the cost was elsewhere: `Board.control` at 398,622 calls
in one pass of 40 rankings, 20% of self time, with `region_tier` and its
`controller` closure another 35% cumulative on top of it. No `_access`
micro-slice touches that. A snapshot that derives control once and updates
it incrementally does.

### `_access` was returning stale numbers, and it changed moves

Bypassing the `_access` memo reordered **39 of the previous corpus's 598
rankings** and moved the values of 85 more. Not last-bit drift: a different
chosen move in 6.5% of captured positions, decided by what the player had
evaluated first. The memo was keyed `(board, cid, side)` while the function
reads influence two hops out, so a trial placement made and unmade inside
`_investment` left it describing a board that no longer existed.
`country_value` had a weaker version of the same defect (keyed on the
country's own `(own, opp)` while its access, wipe-backing and first-mover
terms read neighbours), and `_coup_targets` a third, keyed on
`(board, holder, defcon)` while counting influence.

This is the same finding as "`delta` is not a pure function of the board"
above, with the mechanism identified. It is not fixable with a better key:
a sound key covers the whole two-hop neighbourhood, which costs about what
the walk costs.

`7cb9fbe` deletes all three memos. It costs 26% (median 0.361 s to 0.454 s)
and regenerates the corpus, which drops from 598 to 514 records because the
games now diverge. Its 32-seed gate is a wash, as a correctness fix in
near-ties should be: turn-3 checkpoint mean signed VP +0.22, full games
score 0.484 with mean signed VP +0.38, no nuclear losses. The expert check
moved 24 -> 26 misses. **Completing is not passing** (Codex is right about
that): read this as neutral within the noise of 64 games, not as a win.

### The extraction

`bots/evaluator.py` holds the country, access, wipe, region-score and
margin terms as functions of `(Terrain, Position, weights, urgency,
defcon)`. `Terrain` is the static map indexed by country, built once per
process. `Position` is one board's influence plus derived control,
reachability, and the neighbour counts reachability needs, with
`place` updating all three in time proportional to one country's
neighbours. Scoring urgency became a vector computed once per decision,
which is what let `_scoring_weights` go.

Bitwise identical, and checked three ways before landing:

- Every term against the method it replaced, on all 514 corpus records:
  `country_value`, `_access`, `region_score`, `region_margin` and `value`
  for every country and region. The only mismatch found was `board_value`,
  by one ulp, because CPython compensates float summation inside `sum()`
  and an accumulator loop does not. The pure version now uses `sum()`.
- The parity corpus, the hash-seed regression and the full suite.
- Fixed 24-simulation MCTS searches on the opening, scoring and hazardous
  corpus records: identical chosen action, node count, and every root
  edge's visits and value.

Speed, same workload, against the corrected baseline: medians 0.471 s and
0.514 s at `7cb9fbe` against 0.285 s and 0.303 s after. About 40% faster
than the fix, and about 20% faster than the stale-memo code it replaces.
The full suite went 93 s -> 70 s, the parity test 129 s -> 59 s.

### The invariant this buys, and its price

The board and the snapshot must describe the same position, so every write
goes through `_set_influence`, `_add_influence` or `prepare`. That is a
real obligation with about ten write sites, so it is machine-checked rather
than trusted: `CHECK_SNAPSHOT` rebuilds the snapshot from the board on
every `delta` inside a ranking and compares. Two tests turn it on, and both
were confirmed to fail when a write site is deliberately broken.

Codex's concurrent audit caught one I had missed:
`RolloutPolicy._placement_plan` writes influence directly *and* sets
`_base_regions` itself, so the "outside a ranking, re-read the board"
fallback did not cover it. Fixed, with the rollout test that pins it.
`EventValuePlayer` had two more. That audit point was correct and worth the
interruption: a pure kernel does not make its stateful wrapper correct.

### Gate isolation, which this change broke and then fixed

`gate.sh` used to extract only the baseline's `strategic.py`. Once that file
imports `struggler.bots.evaluator`, a standalone load binds the
**candidate's** evaluator and the gate reports the candidate playing itself.
`benchmark.load_module` now binds an `evaluator.py` sitting beside the
baseline file for the duration of that load, and `gate.sh` snapshots both
files per revision into `$OUT/base/` and `$OUT/old/`. Two tests cover it.
This does not bite gates whose baseline predates the split, including the
one run for `7cb9fbe`.

### The event basis, the third instance of the same defect

Codex's audit was right and the reproduction is exact: `_resolve_sandbox`
re-valued only the countries whose own influence the event changed, while
`country_value` reads its neighbourhood. Nasser priced at -67.8296875
against -65.8890625 for a full pass, the whole 1.940625 being Israel.

`9d9890f` fixes it. The first attempt used a radius of two hops and still
mispriced Brush War and The Voice of America: `access` walks a neighbour's
neighbours and then asks whether *those* are reachable, which is a third
hop. `evaluator.VALUE_RADIUS` now lives beside the terms that set it, and a
test moves one country and checks that nothing outside the claimed set
moved with it. It fails at two.

This is a real pricing change: 408 of the previous corpus's 514 records
moved. It costs nothing measurable -- 87 events on a fixed position, 0.066 s
-> 0.059 s, because one snapshot per sandbox beats one per recomputed
country.

Its gate needed a second sample to read at all:

| Seeds | Games | Score | Mean signed VP | Nuclear losses |
| --- | ---: | ---: | ---: | ---: |
| 4000-4031 (gate) | 64 | 0.469 | -2.55 | 0 |
| 5000-5063 (held out) | 128 | 0.555 | +1.13 | 0 |
| combined | 192 | 0.526 | | 0 |

The gate seeds alone read as a strength loss. The held-out seeds read as a
gain of similar size, which is what noise looks like at 64 games; expert
misses went 26 -> 25. Kept on the strength of being correct, not on the
strength of that table. Codex's warning about selecting successive changes
on the same seeds is the reason the second sample was run at all, and it
should be routine, not exceptional.

### Next steps, in order

Codex reassessed the audit through `9d9890f` (see `docs/CODEX_NOTES.md`) and
confirmed the three concrete findings this session addressed are closed.
What it still lists, in its order:

1. `_event_helper` keeps the weights it was built with when the parent's
   are replaced; `event_value` swallows every exception into a
   plausible-looking estimate, so a defect reads as an approximation.
2. Explicit gate acceptance thresholds. "Exited 0" is not "passed", these
   notes have used the wrong word before, and the table above is exactly
   the case where a threshold would have decided instead of judgement.
   Held-out seeds belong in the same rule.
3. Scoring horizon: `scoring_schedule` has no turn-10 cap and no final
   scoring, so late-game investments are priced against scorings that never
   happen. This is the largest remaining valuation error and it is
   systematic, not a tie-break.
4. Flag-only events (NATO, Formosan Resolution, Shuttle Diplomacy) still
   value 0 because the sandbox measures influence and immediate VP.
5. Align the two Ops estimates: `ops_value` plans a greedy multi-country
   spend, the `OPS_TYPE` influence branch extrapolates one country.
6. Only then the indexing measurement (C step 3). The evaluator is already
   the data layout a native kernel would receive, so that measurement is
   about whether the boundary pays, not about restructuring.
