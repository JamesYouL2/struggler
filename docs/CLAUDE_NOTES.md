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
| Blockade, Debt Crisis, traps: discards that fire no event are exits; self-trapping dumps Grain Sales / Voice of America / Colonial Rear Guards (USSR) or Decolonization (US). Red Scare + Blockade or a trap is lethal on the table, and the engine now agrees (modified Ops, FAQ 7.4). | Done in the planner (`trapped` state, pay-or-refuse). The printed-Ops leniency was a defect, not a simplification; fixed 2026-09-09. | Seed 2401 (Blockade paid away the last spare card) regression test. |
| Play around live scoring cards: a card still in the deck or the opponent's hand can score any round. Southeast Asia Scoring reaches only its own countries. Battleground control in an unscored region >>> in a scored one, and Mid War regions grow in value as turn 4 nears. | Done: importance x expected future scorings, discounted per turn away (`scoring_schedule`, `scoring_discount`, `scoring_hand`). | `docs/STRATEGIC_AI.md` "How it plays". |
| The deck schedule is static and public: no "future" uncertainty. | Done: `engine.cards.ENTRY_TURN` is the single source; bots use `bots/public_cards.card_state`. | |
| Influence value is not linear: control scores, uncontrolled influence has option value only, over-protection matters mainly where a coup is cheap. | Recorded as `progress_curve` / `reserve_stability` weights; defaults kept linear because with one action of lookahead the linear term is the option-value stand-in. Convex lost 0.33 ± 0.09. | `docs/STRATEGIC_AI.md`; `logs/game-check/shape-ab-convex-vs-linear-4000-4015.json`. |
| DEFCON is not worth much to either side in the Early War. Turn-1 battleground coups are often right (VP, Military Ops). | Done: no DEFCON charge on early coups. | |
| Battlegrounds >> cheap Southeast Asia countries >> other non-battlegrounds. Battleground Ops score domination/control or deny them; SEA countries non-dominate Asia and score later. | Done: `battleground` / `southeast_asia` / `control` tiers in `StrategicWeights`. A turn-1-only rule was tried first and removed as hacky. Tiers + coup discount vs the old flat tiers: 0.55 ± 0.06 on seeds 4000-4015 (0.72 as USSR, 0.38 as US). | `logs/game-check/3003-*` is the testing ground; `logs/game-check/tiers-ab-4000-4015.json`. |
| Coups/realignments should be valued like placement, generally preferring placement (Ops efficiency: a coup on a 2-stability country is -1 Op). | Done: same `delta` pricing, `coup_discount` 0.9. | |
| 1- and 2-stability countries are more VP per Op while their scoring is live. | Already what the influence search maximises (gain per Op); noted, nothing extra encoded. | |
| Blockade paid with a US/neutral 3-Ops card is great for the USSR; paid with De Gaulle / Socialist Governments / Suez Crisis it is good for the US (event never fires). Discards return at the reshuffle, so dumping Decolonization / De-Stalinization delays them, it does not remove them. | Noted, not priced: the pay choice scores flat minus modified Ops, and the USSR-seat sandbox assumes the US cannot pay (Blockade values 39.7 to the USSR, 0 to the US on the opening board). | `docs/DEFCON_STRATEGY.md` "Hand discard effects". |
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
in `benchmark.acceptance` and are deliberately asymmetric: no more nuclear
losses than chance explains, two samples over disjoint seeds and 150+
finished games, and a pooled score whose one-sided 95% upper bound reaches
0.500. A change is blocked only when the games say it is *worse*. At 32
seeds most real changes are not measurable in either direction, and a rule
that demanded proof of improvement would block all of them.

Mind the exit status when you invoke it: `scripts/gate.sh | tail` gives you
tail's status, not the gate's. Read the printed verdict.

## Early stopping, shadow-validated (2026-09-09)

Codex asked for the gate's early stopping to be checked against completed
gates rather than trusted, and compared with simply playing a fixed number
of games (docs/CODEX_NOTES.md). `scripts/validate_early_stopping.py` does
it offline, so it costs no games; rerun it as gates accumulate.

Only 8 of the 16 recorded gates can serve as references. The other 8
stopped early, and what they stopped is exactly the evidence needed to
check them -- worth knowing before assuming a validation like this can be
done retrospectively at any time.

Over those 8 (all accepts) plus 600 gates resampled from their seeds with
the true score tilted across the line:

| |margin| | predictive f.rej | f.acc | fixed 160 f.rej | f.acc |
| --- | ---: | ---: | ---: | ---: |
| <0.01 | 0.0% | 0.0% | 1.7% | 0.0% |
| 0.01-0.03 | 3.5% | 0.0% | 7.9% | 0.0% |
| 0.03-0.06 | 0.0% | **9.7%** | 0.7% | **26.4%** |
| 0.06-0.10 | 0.0% | 4.8% | 0.0% | 6.1% |
| >=0.10 | 0.0% | 0.0% | 0.0% | 0.0% |

Predictive stopping saves 10.2% of games against the fixed design's 16.7%,
and is better in every bucket -- so the answer to Codex's "retain it only
if its measured tradeoff is better" is yes, keep it.

The finding that matters more is the column both share. Stopping early
accepts gates it should reject, at up to 9.7%, concentrated where the true
score sits 0.03-0.10 below the line. That is not a bug: fewer seeds means a
wider one-sided interval, the rule accepts when the upper bound reaches
0.500, and a run stops when its data happens to look decisive. Raising
`min_games` buys it back about one for one (176 games: 2.0% false accepts
for 4.2% saved), which is not a trade worth making blind.

So the floor stays at 150 and the honest consequence is recorded instead:
**a stopped ACCEPT is weaker evidence than a completed one**, and a gate
landing within 0.06 of 0.500 is worth rerunning with `GATE_DECIDE=0`.
Every gate this session that mattered was inside that band.

The nuclear-loss rule started as "any is a blocker" and was wrong. It
rejected the scoring-horizon commit on one loss, and the recorded gate
games say that is variance: 3 candidate losses in 4226 games, 0.071%, across
three separate commits, two of which landed. At that rate a 192-game gate
sees one about one time in eight, so demanding zero would have rejected a
change in eight on noise, which is the failure the strength rule was written
to avoid. Two is now a fail; one warns and names the seat and seed to replay.

Recounted 2026-09-09, after `4f01bc7` fixed the attribution: the earlier
figure of 4 in 1920 included one game the *opponent* lost to DEFCON 1, and
the recorded corpus has since more than doubled. The rate came down rather
than up, which matters for Codex's proposal to drop the cap entirely
(docs/CODEX_NOTES.md): a FAIL at two fires by chance in under 1% of gates,
so the tripwire is close to free.
Replay it: seed 4014 USSR turn 9 was a real lost position, the planner
having correctly flagged every remaining play as a certain loss several
action rounds earlier, with two US DEFCON-lowering cards stuck in a hand of
two at DEFCON 2.

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

## 2026-09-09 — The scoring horizon, and why the old weights were near a ceiling

The user's correction, which changed this fix substantially: **the old
weights are basically a maximum, because good players end the game early.**
Mostly by scoring 20 VP; also Wargames; also DEFCON suicide.

That is right, and it is measurable, because the engine already records why
each game ended and `benchmark --report` keeps it per game.
`scripts/game_endings.py` reads those reports. Over the 192 games of the
`8680865` gate, both seed ranges:

| How it ended | Games | Share |
| --- | ---: | ---: |
| 20 VP auto-victory | 129 | 67.2% |
| final scoring after turn 10 | 47 | 24.5% |
| Wargames | 14 | 7.3% |
| draw | 2 | 1.0% |
| DEFCON 1 | 0 | 0% |

Only **52.6%** of games reach turn 10 at all, and only 24.5% reach final
scoring. Per-turn survival runs about 0.88-0.93 from turn 6 on.

The part I had wrong: I first treated final scoring as guaranteed and
discounted it like a scheduled card scoring, at `0.8 ** (10 - turn)`. Against
the measured odds that is more than double from turn 8 on:

| Turn | P(final scoring \| alive) | `0.8 ** (10 - turn)` |
| ---: | ---: | ---: |
| 1 | 0.245 | 0.134 |
| 5 | 0.270 | 0.328 |
| 8 | 0.367 | 0.640 |
| 9 | 0.416 | 0.800 |
| 10 | 0.465 | 1.000 |

The measured curve is almost flat, which is the interesting part. It does not
climb toward certainty as the game runs on, because a game still alive on
turn 9 is usually alive *because* it is close, and close games still get
decided on VP during turn 10.

So the fix is two things, not one:

- **Cap the horizon.** A reshuffle two turns away on turn 9 predicted a
  scoring on turn 11. That one is unambiguous.
- **Price the end-of-game scoring at its odds**, `scoring_final` times
  `FINAL_SCORING_ODDS`, rather than as a certainty.

Iran's weight goes from a flat 1.800 on every turn to 2.04 rising to 2.22 by
turn 9, then 1.47 on turn 10 where the cap bites. Turn 10 ends up *below* the
old value, which is the user's point arriving in the numbers.

### Caveats on the calibration

- These are bot-vs-bot games, and a generous proxy. Strong human players push
  for 20 VP harder than this bot does, so the real odds of reaching final
  scoring are lower than 24.5%, and the correct `FINAL_SCORING_ODDS` is
  probably below this table. Codex has tournament statistics; replace the
  table when they land, and rerun `scripts/game_endings.py` to check the
  bot's own distribution against them.
- The table is measured from games the *current* bot played, so it moves as
  the bot changes. That is circular, but only weakly: the shape is driven by
  the 20 VP rule, not by this evaluator.
- `scoring_discount` (0.8 per turn) is doing survival duty for the card
  scorings, and the measured per-turn survival is 0.88-0.93, not 0.8. So the
  card terms are discounted harder than survival alone justifies. Leaving that
  alone: it is a tuned weight with its own gate history, and 0.8 also carries
  uncertainty about the board that far out. Worth revisiting as its own
  calibration, with the same script.

### Web search for human tournament data: what is out there

`twilight-struggle.com` is the International Twilight Struggle Community
site, with a competitive database of 30,000+ games since 2006 across 1,500+
players and 100+ tournaments. That is the right source. Its result pages did
not come back to an unauthenticated fetch, so I could not extract the
ending-type distribution from it. BoardGameGeek blocks fetches outright
(HTTP 403). What is easy to find is side win rates (roughly 53/46 to the US
with the +2 handicap among strong players, ~60% USSR without it), not game
length or ending type.

## 2026-09-09 — The rest of Codex's list, and what the gate said

Done in the order that makes later changes cheapest, not in the order of
severity. Every behaviour change below was gated on both seed ranges.

| Commit | Change | Pooled score, 96 seeds |
| --- | --- | ---: |
| `7750aff` | the gate's exit status is the verdict | infrastructure |
| `b5466cc` | say when an event value is a broken estimate | no value change |
| `8680865` | simulate the two dice-contest events | 0.495 +/- 0.014 |
| `e9cd991` | cap the scoring horizon, price the game's end | 0.503 +/- 0.028 |
| `56f793d` | nuclear losses judged against their rate | infrastructure |
| `40726d0` | one Ops estimate, not two | 0.542 +/- 0.034 |

The last is the best result of the session and the only one positive on both
samples independently (0.531 tuning, 0.547 held out). It is still not
significant: the lower bound is 0.486. Do not claim it as a strength gain.

### Two things the session got wrong first

**Timing while a gate runs.** These notes already warned about this, and I
did it anyway: the Ops change looked like a 3x slowdown (419 s against 125 s
on the suite) while a 192-game gate had the machine. On a quiet machine it is
12.5 s against 13.6 s, slightly *faster*. Never time anything while a gate
runs; the numbers are worthless, not merely noisy.

**`pytest` and stale bytecode.** Toggling `VALUE_RADIUS` between 2 and 3 with
`sed` changed one character, so the source kept its size, and with the mtime
inside the same second CPython reused the `.pyc` from the previous value. A
test then failed against source that was already correct. If a one-character
edit produces an impossible result, clear `__pycache__` before believing it.

### Still open, from Codex's list

Flag-only events (NATO, NORAD, Warsaw Pact Formed, Nuclear Subs, Quagmire,
Bear Trap) still value 0: the sandbox measures influence and immediate VP,
and a persistent effect is neither. Left alone deliberately, as it needs
expert judgement about what those effects are worth rather than a mechanical
fix. Formosan Resolution and Shuttle Diplomacy came off this list once
scoring took the overrides -- see below -- because what they change is a
number the bot already computes.

`FINAL_SCORING_ODDS` is measured from this bot's own games and is a generous
proxy for expert play. Codex has tournament statistics; replacing the table
is one line, and `scripts/game_endings.py` recomputes the bot's own
distribution to compare against them.

## 2026-09-09 — The gate compared a change against itself

`gate.sh` snapshotted the baseline's `strategic.py` and `evaluator.py`, and
`load_module` bound that sibling evaluator while the baseline loaded. The very
next change was to `public_cards.py`, which is not either of those, so the
baseline imported the *candidate's* table. Both sides played the same bot.
The gate returned:

    full-vs-base: 32 seeds, score 0.500, signed VP 0.0
    full-vs-held: 64 seeds, score 0.500, signed VP 0.0
    pooled score 0.500 +/- 0.000 over 96 seeds
    ACCEPTED

A standard error of exactly zero over 96 seeds is the tell. Proven directly:
the baseline's `final_scoring_odds` and the candidate's resolved to the same
module object.

Two fixes. The snapshot is now the revision's whole `struggler/bots` package
(`git archive`), and `load_module` resolves every `struggler.bots.*` import to
it through a `sys.meta_path` finder installed only while the baseline loads.
A finder rather than pre-executing the files, because the snapshot's modules
import each other and no execution order is right in general. `struggler.engine`
is deliberately not snapshotted: it is the shared arbiter both sides are
measured under. A baseline that imports lazily inside a function, after the
load returns, still gets the candidate's module; nothing here fixes that.

And the acceptance rules now warn when every game is a dead heat, since that
is either a change that cannot affect play or a comparison that is not
comparing anything. It cannot fail: `ec99a5f` was a proven behaviour-neutral
refactor and gated at exactly 0.500 legitimately.

The lesson generalises past this instance. Codex flagged incomplete revision
isolation as an open item after the `evaluator.py` fix, and the answer was
"other imported modules come from the candidate environment" -- true, filed,
and then it bit within the hour. A known gap in a measurement tool is a
liability, not a footnote.

## 2026-09-09 — One scoring implementation, and the overrides the bot could not see

Three copies of region scoring existed: `Board.score_region` (fused, fast, no
overrides), `Board.region_tier` plus `Board.region_bonus_vp` (the parts the
engine assembled a score out of), and `evaluator.region_vp` (index space, for
the bot). Only the engine's copy knew about the per-scoring overrides, so with
Formosan Resolution or Shuttle Diplomacy in force the bot and the engine
disagreed about what a region was worth -- and the bot then chose on its own
number and was paid on the engine's.

`score_region` now takes `extra_battlegrounds`/`ignored` and is the only
implementation the engine has; `_score_region_net` adds which events are in
force and the Europe Control victory, and nothing else. `region_bonus_vp` is
deleted. `Board.scoring_overrides` derives the pair as a pure query, and
`Engine._scoring_overrides` keeps only the consumption, which is the part that
is not a query. The bot mirrors the derivation in index space
(`evaluator.scoring_overrides`) and reads the flags from
`observation.game_effects`.

Two things this made me get wrong first, both caught by measurement rather
than by reading:

**Deriving the overrides at `prepare` would have been wrong.** They read
control, and every trial placement moves control. Taking Taiwan is what turns
Formosan Resolution on, so the placement that does it has to see the promotion
in its own delta. They are derived per call; the empty case costs a `bool`
test, so the hot loop does not pay a set lookup for a card that is not in
play.

**Crediting a one-shot in both regions it could apply to is not a rounding
error.** My first version applied Shuttle Diplomacy to the Middle East *and*
Asia, because either could score next. Against the parity corpus one position
moved 5 VP in Asia and 1 in the Middle East from the same single discount -- a
6 VP phantom, five times the 1 VP gap I was fixing. Dropping a Battleground
can cost a whole tier, so "apply it twice, it is only a small overcount" was
never true. It is now spent once, on the region whose scoring is nearer
(`_shuttle_region`), ties to the Middle East. Pricing the actual play of a
scoring card is unaffected: that runs the real engine in the sandbox, which
applies and consumes the effect for real.

The event sandbox reads the flags from the *sandbox* engine after the event
fires, not from the observation. That is the whole reason an event whose only
effect is setting a flag now prices at anything: Shuttle Diplomacy went from
0.0 to -1.3 for a USSR seat on a corpus position (a US event, so a USSR player
handing it over is paying for it).

71 of 464 corpus positions had one of these in force. The corpus was
regenerated; the differences are Middle East and Asia region scores, Shuttle
Diplomacy's own value, and the two events that move influence there (Voice of
America, ABM Treaty) re-scoring those regions under the discount.

**The engine now records that Final Scoring ran** (`Engine.final_scoring_ran`,
serialized only once true, so earlier recorded states compare equal).
`scripts/game_endings.py` counted `reason == 'final_vp'`, which misses a game
that reached Final Scoring and ended partway through it at `vp` or
`europe_control`, and misses draws, which carry no reason at all. Constructed
one of each to check the flag catches them. This matters because that script
produces the calibration table, and it was undercounting the numerator.

The golden replay `full_game_ops_only.json` gained exactly one line, checked
by diffing every checkpoint before rewriting rather than by regenerating the
file: 618 checkpoints, one added key, nothing changed or removed.

## 2026-09-09 — Two claims I got wrong before measuring them

Both were the same mistake: reasoning about impact from the shape of the
code instead of checking whether the thing was live and how much it was
worth.

**Warsaw Pact Formed.** The event sandbox drives an `EVENT_CHOICE` by asking
the helper policy, which scores both branches at exactly 0.0 and so
tie-breaks on option order. On the opening board it takes `remove` (all US
Influence from four Eastern European countries) where the US has none, and
the card prices at 0.00 -- while `add` places five USSR Influence in Eastern
Europe. I reported that as a large mispricing and the top priority. The
user's valuation is 0.5 Ops: the points go where the USSR already holds or
soon will, and playing it hands the US NATO. Against `tolerance_ops` of 0.75
the bot's 0.00 is inside calibration. `models/expert_valuations.json` now
records it. The branch-selection defect is real and still unfixed; what was
wrong was the evidence I offered for it, which was board movement rather
than value.

**The Coup prohibitions.** `wipe_risk` and `coup_targets` gated on DEFCON
alone, so they priced USSR Coups that NATO, the US/Japan pact and The
Reformer forbid. I described that as the bot over-defending Europe for the
rest of the game. It does not: `wipe` ships at 0.0, "off until calibrated",
so the term never runs. The fix is right and worth having -- calibrating a
term that is systematically wrong across a whole region fits the weight to
the wrong quantity, and this is what would give NATO a value -- but it
changes no game today, and I said it would.

The check that would have caught both takes a minute: for a card value, look
it up in `models/expert_valuations.json` against `tolerance_ops`; for a term,
look at whether its weight is non-zero.

### What did land

`Board.coup_prohibited` and `Board.nato_protects` are the derivation;
`Engine._usable_coup_realign_target` keeps the defender's Influence, DEFCON,
and which events are in force, and the NATO logic exists once rather than
twice. `evaluator.coup_forbidden` mirrors it in index space,
`strategic.coup_bans` reads the flags off the observation, and the event
sandbox reads them off the sandbox engine so an event that turns one on is
worth the risk it removes. Derived per call, because NATO's shield follows
US Control and a trial placement moves control.

`test_coup_forbidden_matches_the_engine_under_every_prohibition` walks every
country under all 32 flag combinations against `Board.coup_prohibited`, and
asserts each prohibition fired at least once rather than trusting that a
board happened to exercise it.

Two things the tests found that reading did not. West Germany cannot be
wiped at all -- stability 4 holding 4 needs roll + Ops >= 12, and the maximum
is 10 -- so the obvious country to write the NATO test around is the one
country in Europe where the term is silent. And under NATO the risk that
remains is divided over fewer targets, so lifting the shield on one country
with De Gaulle does not return it to its unshielded value; it lands harder
than it did before.

## 2026-09-09 (night) — Audit: the gate, the bot's speed, its strength, and what is off those three lists

Asked for: how to speed up the gate, how to speed up the strategic bot, how
to make it stronger, and anything important that is none of those. Written
against `df29bf8`, with `c15a603` (Codex's audit of the same revision) read
afterwards; the two are compared at the end.

What is *not* behind this section: no fresh profile of my own. A gate held
the machine for the whole audit (load 17 on 8 cores), and this file's own
rule is that a timing taken next to a gate is worthless. The step budget
below is from the gate's own records, which are wall-clock-honest about
themselves whatever else was running; the cProfile numbers quoted are
Codex's.

### The gate is not slow where either of us guessed

`gate-df29bf8`, 8 workers, 151 finished games, from the directory's mtimes
and the reports' own per-game seconds:

| Step | Wall | Share |
| --- | ---: | ---: |
| 1 + 1b, turn-1 table and the expert diff | 2 s | 0.1 % |
| 2, turn-3 checkpoint (64 games) | 67 s | 4 % |
| 3, full games (151 games, 12,282 CPU-seconds) | 1,595 s | 96 % |

The pool is not starved: 12,282 CPU-seconds over 8 workers is 1,535 s ideal
against 1,595 s actual, 96 % efficiency, and that is *with* one 551-second
game in the tail. So three of the speedups that suggest themselves from
reading `gate.sh` are worth nothing measurable. Running steps 1 and 1b
concurrently with step 3 saves two seconds. Folding the turn-3 checkpoint
into the full-game workers -- which I proposed before measuring, and which
`c15a603` calls "the next cheap speedup" -- saves 4 %. Worth doing as
tidiness, not as a speed programme.

The gate is 151 games of this bot and essentially nothing else. **Bot speed
is gate speed**; they are one item on the list, not two.

### Per-game seconds have drifted 2-3x in two days, and nobody attributed it

`mean_game_seconds` from each gate's `full-vs-base`, in commit order:
~13-15 s across the Sept 8 morning gates (`f123625` 13.2, `50e8bff` 13.4,
`873d9d9` 14.0, `c5446e0` 14.8, `1a03954` 15.5), then 25-36 s for every gate
of Sept 9 (`7cb9fbe` 31.9, `ec48dfa` 36.4, `b375ae5` 33.1), and 82.5 s for
`df29bf8` under contention.

Two candidate steps, neither attributed: `6ec71d4` (VP priced in Ops, which
puts an `ops_value` call underneath every VP price) with `4e67bf0` (sandbox
dice averaging, which forks the engine per die face) at the first jump, and
`7cb9fbe` (the two stale memos removed -- correctly; that commit bought
correctness and paid for it in time) at the second. Codex's cProfile at
`df29bf8` independently puts `ops_value` at ~31 s cumulative of 107.8 s,
which fits the first candidate. `ops_value` *is* cached per decision
(`_ops_values`), so this is cache misses across decisions and sandboxes, not
naive recomputation -- do not "fix" it by adding a cache that is already
there.

Attribute it with `scripts/profile_baseline.py` on a quiet machine before
optimising anything. A 2x recovery here is a 2x gate, which is worth more
than every structural change to `gate.sh` combined.

### What the gate can see -- and the arithmetic I got wrong first

I first computed the gate's standard error over individual games and got
0.041 at 150 games. That is wrong, in the direction that flatters the
gate: both seats of one seed play the same deal, so a seed is one
observation and not two, which is exactly what `benchmark.seed_scores`
already does and what the docstring there already says. Over the 2,315 seed
pairs in the recorded reports the seed-score SD is 0.24.

| Seed pairs | Games | SE | Regression blocked at 80 % power |
| ---: | ---: | ---: | ---: |
| 32 | 64 | 0.042 | 0.105 |
| 96 | 192 | 0.024 | 0.061 |
| 150 | 300 | 0.020 | 0.049 |
| 500 | 1,000 | 0.011 | 0.027 |

So the full 96-seed gate blocks a 6-point regression four times in five, and
is blind to 3 points in either direction. `df29bf8`'s own gate reported
+/- 0.009 because that change left most seeds identical: the error bar adapts
to how much the candidate actually moves play, which means it is tightest
exactly when the answer matters least.

The consequence for how this project spends its day: 49 commits landed on
Sept 9, most separately gated at ~28 minutes each. That bought *attribution*,
not evidence -- at 32-64 seeds nearly every one of them was unmeasurable by
construction. Batching related changes into one 300-game gate and bisecting
only on a failure costs less wall time and sees more. Keep per-commit gating
for changes expected to be large, and for anything touching the DEFCON
planner.

`gate-df29bf8` verdict, for the record: **ACCEPTED**, pooled 0.500 +/- 0.009
over 76 seeds, stopped early at 76 of 96. One candidate nuclear loss (seed
4003 USSR T6) to replay, and one *opponent* nuclear loss at seed 4003 US T6,
correctly not counted.

### Strength: the expert table's misses are mostly one missing quantity

23 misses at `df29bf8`. The large ones are not independent: France ranks
below Egypt, Pakistan and Iraq in the US placement order; Vietnam Revolts
-1.17 against -4.00; De-Stalinization -4.94 against -7.00; De Gaulle -0.80
against -2.00; Suez -1.23 against -2.50. Adjacency into *empty* countries,
the liability of a lone point, and what a coup takes back are one quantity,
and the term for it (`wipe`, `wipe_backed`) is coded and ships at 0. Plan
step 2 is still the highest-value strength work in the file, and it is the
one the expert table is already instrumented to score.

After it, in order:

1. **The 32-seed MCTS run.** Scoring-turn MCTS scored 0.75 against the plain
   policy on 8 games after the three semantic fixes. That is the only large
   unconfirmed number in this file, it is ~25 minutes, and it decides
   whether a native port is worth considering at all. Do it before any
   further Rust discussion.
2. **Scoring-card timing** (plan step 5): an urgency multiplier is not a
   plan, and seed 3003's Asia Scoring at -6 with no Asia presence is the
   standing reference failure.
3. **Fit weights to the expert table, not to games.** The trainer has never
   found a strict improvement, and the reason is arithmetic: its fitness has
   an SE of 0.04-0.06 against effects of 0.02-0.05. It cannot see what it is
   selecting for. The expert table is a one-second fitness function that
   can, and the gate then checks the result rather than searching with it.

### Three things off those three lists

**Every strong opponent is this bot.** Greedy scores 1.00 against it,
`event_value` and MCTS are strategic underneath, and the gate asks only
"does it beat yesterday's self". Nothing in the loop would notice the whole
line drifting away from strong human play; the expert table is the sole
external reference and it is ~30 rows on one board. The cheapest fix is to
extend it to annotated positions drawn from the parity corpus -- a tactics
suite scored the way the opening table is -- which doubles as the fitness
function item 3 above needs.

**Rules churn is invisible to the gate by construction, and 16 cards are
untested.** About a dozen rules fixes landed on Sept 9. `gate.sh` snapshots
only `src/struggler/bots`, so a rules change puts identical players on both
sides and returns exactly 0.500; the tests are the only thing standing under
those commits. These 16 of 110 cards are named nowhere under `tests/`:
Romanian Abdication, Nuclear Subs, Kitchen Debates, Cultural Revolution,
Flower Power, Colonial Rear Guards, Latin American Death Squads, OAS
Founded, Shuttle Diplomacy, Liberation Theology, Alliance for Progress,
Iranian Hostage Crisis, The Iron Lady, Reagan Bombs Libya, Iran-Contra
Scandal, Iran-Iraq War. A per-card pass against `docs/RULES_SOURCES.md`
belongs before more value tuning is stacked on top of them.

**The parity corpus is red and stale, and it is the oracle for what comes
next.** Every caching or indexing change is verified by it. Regenerate it in
its own reviewed commit (the ranking changes behind the failure are measured
and intended) before touching the evaluator again, or the next memo bug --
there have been three -- lands without a detector.

A fourth, smaller: these notes are 337 KB across two files and the open list
now lives in four separate sections. Whoever picks this up next pays an hour
to find out what is open. One short state-and-open-list page, rewritten
rather than appended, would pay for itself immediately.

### Where this differs from Codex's `c15a603`

Agreement on the substance: the risk and sentinel fixes are good, the corpus
should be regenerated separately rather than treated as evidence against
them, `LOSS` wants an explicit terminal-outcome type rather than sentinel
plumbing, `StrategicWeights` should separate its active tuning set from
compatibility and disabled fields, and no native port before the repeated
work is measured against a frozen Python reference.

Three differences, all of them measurement rather than opinion:

- Codex calls folding the turn-3 checkpoint into the full-game workers "the
  next cheap speedup". Measured, it is 4 % of the gate, and steps 1 and 1b
  are 0.1 %. The gate's cost is per-game CPU times 151, and nothing else.
- Codex proposes caching the repeated `discard_risk` / coup-target / `delta`
  work with full state keys. Right in principle, and this file's history
  says the risk is real (three memos have shipped keyed on less state than
  they read). But the corpus that would catch a fourth is currently red, so
  the order is corpus first, cache second.
- This section of Codex's notes does not raise an external strength
  reference, the untested cards, or the gate's statistical power. (It has
  asked for varied opponents before, under "benchmark reuse", so the first
  is a difference of emphasis rather than of view.) I think the power
  arithmetic changes how the day should be spent -- batch the gates, buy
  seeds with the savings -- more than any single item on either list.

Codex also covers ground I did not, and it is worth keeping rather than
merging away: the `LOSS` sentinel wants a real terminal-outcome type, the
26 weight fields want their active tuning set separated from the
compatibility and disabled ones, `coup_discount=1` is a clean isolated
ablation, and the MCTS leaf parameters should be split from the rollout and
proposal parameters before anything tunes them together. Those belong with
`docs/STRATEGIC_SIMPLIFICATION.md`, which is where the weight-by-weight
argument already lives.

Neither audit found a new correctness defect in the risk fixes.

### Codex reviewed the section above, and corrected two of its claims

`CODEX_NOTES.md` "Review of Claude's night plan", written against the
uncommitted section above. Broad agreement, and it accepts the 4 % finding
that demotes the checkpoint fold. Two of my claims do not survive, and both
corrections are confirmed here rather than taken on trust:

- **"96 % pool efficiency" is close to a tautology, and is withdrawn.**
  `benchmark.play` times a game with `time.time()` (`benchmark.py:203,227`),
  so the per-game seconds are elapsed worker occupancy, not CPU. Summing
  them and dividing by the worker count measures how busy the workers were,
  which under contention inflates with the contention and returns ~1 by
  construction. What survives is the step budget itself, which comes from
  directory mtimes and is real wall clock: 2 s, 67 s, 1,595 s. Step 3
  dominates and the checkpoint fold is worth 4 %; the pool efficiency claim
  and the "2-3x code slowdown" both need controlled, quiet-machine
  comparisons before anyone believes them.
- **"16 cards are untested" overstates it.** Codex names behaviour tests for
  Nuclear Subs, Flower Power and Shuttle Diplomacy that my grep missed
  because it searched for literal card IDs and the tests spell them
  differently or drive them through effect flags. Checked: those three are
  mentioned in 4, 2 and 4 test files respectively. Iran-Iraq War, OAS
  Founded and Kitchen Debates appear in one file each, which may be an
  incidental mention rather than a behaviour test. The real question is
  coverage of activation, resolution, interaction and expiration separately,
  and no grep answers it. Treat 16 as an upper bound on a number nobody has
  measured yet.

Codex's other three qualifications stand and are adopted: the wipe term is
a hypothesis rather than the proven cause of the clustered expert-table
misses (empty-country access, event vulnerability and coup vulnerability
overlap but are not the same mechanism); batching gates should keep
distinct strategic hypotheses independently measurable, since a failed
batch of interacting changes does not bisect cleanly; and the MCTS run
should record root visits and truncation and compare equal wall-time
budgets as well as equal simulation counts.

Its revised sequence -- green baseline, controlled profiling, the 32-seed
MCTS run, tactics suite and a real coverage audit, then optimisation with
wipe and coup-discount tested independently -- supersedes the order I gave
above. The one thing I would keep from mine is that the gate's power is a
reason to batch *validation*, not a reason to stop attributing changes.

## 2026-09-09 (overnight) — Green baseline, and the slowdown is real but not attributed

Work done unsupervised, following Codex's revised sequence. Nothing was
committed and no weights changed.

### Baseline restored

`5a2f3bb` regenerated the parity corpus (427 records, captured clean at
`c15a603`, no dirty paths). The suite at that revision: **588 passed, 3
skipped, 0 failed**, including `test_parity_corpus.py`. The single expected
red test recorded in earlier sessions is therefore closed; treat a parity
failure from here on as a real one.

Housekeeping worth knowing: four leftover watcher shells from an earlier
session were deadlocked, each polling `ps` for a pattern that its own
command line contained, so each was waiting for itself. They had been idle
25 minutes on a quiet machine. If a background wait never fires, check
whether its own command line matches its own predicate.

### The bot really did get slower, normalised for game length

The obvious confound first, and it is dead: **games are not running
longer.** Mean end turn is flat at 8.4 across every gate from `b18b7a9` to
`ec48dfa`. Game seconds do scale hard with how far a game goes (median 3.6 s
at end-turn 3, 28.8 s at end-turn 10, over 4,636 games), so per-turn cost is
the number to compare, not per-game.

Seconds per turn of play, in git commit order, one row per gate:

| Period | s/turn |
| --- | ---: |
| `b18b7a9` .. `1a03954` (Sept 8, before the corpus commit) | 1.07 - 2.21 |
| `2a3f12c`, dice averaging's first landing, later reverted | 2.73 |
| `8ba89db` .. `ec48dfa` (Sept 8 evening onward), 24 gates | 2.80 - 4.42 |
| `df29bf8`, measured under load 17 | 10.17 |

So roughly **1.9x on per-turn cost**, it never came back down, and the step
sits at the `8ba89db` / `6ec71d4` / `4e67bf0` cluster. The natural
experiment inside it: dice averaging spiked its first landing to 2.73
against neighbours at 1.07-1.90, was reverted, and every gate after it
re-landed in `4e67bf0` is at or above 2.80.

**This is suggestive, not attribution.** Every row is a separate gate run
under uncontrolled machine load, which is exactly the confound this file
keeps warning about. Codex's controlled experiment -- the same positions,
the same machine, revisions compared back to back -- is still the thing that
would settle it. What this does establish is that the question is worth the
experiment, and that "the games just got longer" is not the answer.

### Frozen positions: two hot paths, not one

Four corpus positions, three unprofiled repetitions each, fresh player per
repetition (a warm player carries per-decision caches and would time the
second call), on a quiet machine at `5a2f3bb`:

| Position | Decision | Options | Min elapsed |
| --- | --- | ---: | ---: |
| Opening placement, T1 AR1 US | `place_influence` | 38 | 0.007 s |
| Scoring-card choice, T1 AR1 US | `action_round_play` | 7 | 0.034 s |
| Ordinary mid-war hand, T5 AR1 USSR | `action_round_play` | 9 | 0.191 s |
| Hazardous late hand, T7 AR1 US (whole-hand risk 0.469) | `action_round_play` | 8 | 0.336 s |

Elapsed and CPU agree to the millisecond, so none of this is waiting on
anything. A decision costs **48x more late than at the opening**, which is
why per-turn cost is the right unit and why a hazardous hand is the
workload to optimise.

The profiles say the cost is in two different places depending on which:

- **Ordinary mid-war hand:** `event_value` is 0.340 s of 0.486 s profiled,
  about 70 %.
- **Hazardous late hand:** `action_risk` into `defcon.risk` is 0.410 s of
  0.612 s, about 67 %, and `event_value` is not the story at all.

That refines Codex's single-game profile, which showed `action_risk` ~49 s,
`delta` ~37 s and `ops_value` ~31 s as overlapping cumulative paths: they
overlap because they are the same two paths sampled over positions of both
kinds. **Optimising either one alone wins about half the workload.** It also
gives the slowdown a plausible mechanism, since both suspected commits
(`6ec71d4` pricing VP in Ops, `4e67bf0` averaging the sandbox dice) add work
inside event valuation, which is the dominant path in ordinary hands.

Harness: `frozen_bench.py` in the session scratchpad, selection deterministic
by corpus order so the same four positions return on every run. It is not
committed; it should be, next to `profile_baseline.py`, if this becomes the
standard measurement.

### The bot declines free Coups: six event branches decided by option order

`score()`'s `EVENT_CHOICE` arm has twelve per-event rules and two
choice-shaped ones (`choice in CARDS`, `choice == 'boycott'`), and then
`return 0.0` (`strategic.py:1898`). Anything with no rule scores 0.0 on
every branch, and `sorted(..., reverse=True)` is stable, so the **first
option offered wins**. The notes recorded this as the Warsaw Pact
branch-selection defect. It is much wider than one card.

Reproduced directly against the engine, not inferred from reading:

| Event | Options | Bot picks | All tied at 0.0 |
| --- | ---: | --- | --- |
| Tear Down This Wall | none / coup / realign | **none** | yes |
| Junta | none / coup / realign | **none** | yes |
| Ortega Elected in Nicaragua | none / coup | **none** | yes |
| Warsaw Pact Formed | remove / add | remove | yes |
| Chernobyl | six regions | EUROPE | yes |
| South African Unrest | south_africa_only / and_adjacent | south_africa_only | yes |

The first three are the serious ones: `push_free_coup_or_realign` puts
`"none"` first in the option tuple, so **the bot declines the free
Coup or Realignment that is the entire point of those three cards, every
time.** This is not a cautious refusal -- the DEFCON planner is not
consulted on this decision at all, and the engine has already filtered the
options to legal ones. It is a tie broken by tuple order.

Chernobyl always blocks Europe and South African Unrest always takes the
smaller option, both unconditionally.

Two reasons this went unseen. It is **invisible to the gate by
construction**: both sides are strategic, both decline, so the games are
symmetric and score 0.500, the same blind spot as a rules change. And the
expert table prices whole cards on the opening board, where none of these
six can fire.

The fix is not new machinery. A free Coup/Realignment type choice is
already valuable to this bot in other decision kinds, so route it through
the existing coup and realignment valuation instead of returning 0.0;
Chernobyl's region choice is the region score it already computes. What it
must not become is a per-branch sandbox simulation, which would land in
the middle of the hottest path (event valuation is ~70 % of an ordinary
mid-war decision, above), so the speed finding and this one pull against
each other and should be designed together.

Reproduction: resolve the event on a fresh `Engine.new_game(seed=7)`, take
the pushed `EVENT_CHOICE`, and compare `rank_actions` keys. Probe kept in
the session scratchpad; it belongs in `tests/` as a regression that asserts
no `EVENT_CHOICE` presents an all-tied ranking.

### Two of Codex's open items are already closed

Checked rather than assumed, since both were on the "what still applies"
list:

- **`_event_helper` stale weights: fixed.** `strategic.py:1014` rebuilds the
  helper whenever `helper.weights is not self.weights`, with a comment
  naming the training case. The finding is stale.
- **Silent sandbox fallback: addressed.** `_event_value_uncached`
  distinguishes `SandboxUnsupported` (debug, expected) from any other
  exception (warning, recorded in `sandbox_failures` where a caller can see
  the value is an estimate). Landed as `b5466cc`.

## 2026-09-10 — MCTS does not replicate, and Military Ops needed a discount

### The 32-seed MCTS run: 0.75 does not replicate, and the search is too thin to be one

Codex and I both wanted this before any native-port discussion, because the
port's whole case rested on one 8-game reading of 0.75. Run at `5a2f3bb`,
24 simulations, seeds 4000-4031, both seats, against the plain policy:

| | |
| --- | ---: |
| score | 0.547 +/- 0.062 (32 seed pairs) |
| 95% CI | [0.425, 0.668] |
| mean total | **-0.58** |
| nuclear losses | 0 |
| seconds a game | 650, of which 93% is search |

**The interval contains 0.5 and the mean total is slightly negative.** The
0.75 was 8 games; it is gone. And the diagnostics say why, which is the
part worth keeping:

| | |
| --- | ---: |
| simulations completed | 24 (always) |
| tree nodes | median 15 |
| root moves that got any visit | median 8, max 12 |
| **visits to the move it chose** | **median 4, min 3** |
| searches choosing on fewer than 5 visits | 526 of 900, **58%** |
| truncated rollouts | 0 |

Twenty-four simulations spread over eight to twelve root macros is three or
four visits each. A UCT root that picks the highest mean over three samples
is not searching, it is sampling noise, and 58% of decisions are decided
that way. The honest description of the current prototype is a very
expensive random tie-break among survival-safe cards.

So the two ways forward are arithmetic, not engineering taste. Either the
root gets far fewer macros (three or four, not twelve), which is free, or
the simulation count goes up by an order of magnitude, which at 650 s a
game is impossible in Python and is the case a native port would have to
make. **Nothing here supports starting the port.** Narrow the root first
and re-measure; that experiment costs nothing and would tell us whether
the leaf and the rollout are any good at all, which this run cannot.

Evidence: `logs/game-check/mcts-32seed-5a2f3bb/`, per-game INFO logs with
every search dict, summarised by `mcts_report.py` in the session
scratchpad.

### Military Operations: rule-exact value, and why a flat one VP an Op is wrong

The only model was a credit inside `coup()` of `weights.military * min(ops,
deficit)`, a flat 2.0 raw against a VP worth ~16 raw on the opening board:
the requirement was priced at about an eighth of its value. Rule 6.3.5
leaves nothing to estimate -- a side below the DEFCON level at the end of
the turn hands the difference over as VP -- so an Op that closes the
deficit is worth exactly one VP and an Op past it is worth nothing.

Pricing it at a full VP an Op made the fixture **worse**, 23 misses to 26:

| Card | Expert | Flat credit | Discounted |
| --- | ---: | ---: | ---: |
| Korean War | -1.00 | -2.07 | -1.10 |
| Indo-Pakistani War | +0.50 | +1.59 | +0.67 |
| Arab-Israeli War | -1.78 | -2.33 | -1.42 |

The reason is that early in a turn the credit is not real: some *later*
card would very likely have covered the requirement anyway, and only the
Ops that end up uncovered are worth a VP. Spreading the credit over the
action rounds still to play fixes it, uses the shape the Containment and
Red Scare riders already use, and introduces no free parameter -- full
value in the last round, a sixth of it in the first.

Discounted, the three war rows move to 24 misses, and the sum of their
absolute error is 0.63 against the baseline's 0.64. **So the fixture calls
this neutral, not an improvement.** The extra "miss" is an ordering check,
not a value: Arab-Israeli War moving toward its target overtook Suez
Crisis, which is itself underpriced by 1.27 and already flagged. Keep the
change because it is rule-exact and the old number was arbitrary, not
because the table endorses it; the gate decides.

Both call sites -- `coup()` and the event sandbox -- now go through one
`military_credit`, so they cannot drift. The sandbox half is new: a war
grants Military Ops to whoever the *event* belongs to, which is not always
the side playing the card (the US playing Korean War for Ops credits the
USSR), and the sandbox valued events by board influence and VP alone, so
that was worth nothing at all before.

Two process notes. The first version read `side` inside `_resolve_sandbox`,
which is an evaluator index there and not a `Side`; every sandboxed event
fell back to its estimate. It was loud rather than silent only because
`b5466cc` made an unexpected sandbox failure a warning -- exactly the case
that commit was written for. And `coup()` now calls `vp_value`, so it needs
the per-decision Ops cache that `rank_actions` builds and `prepare` does
not; every production caller is already inside a ranking, but a test that
called `prepare` alone crashed, which is worth knowing before someone
evaluates a coup outside one.

### The free-Coup gate: accepted, and no gain to show for it

`bbebbd8` against `b9f5370`, 76 seeds over both samples (the gate ran as
`gate-6d33d91`, HEAD having moved on to the docs commits, which touch no
bot file):

| Sample | Seeds | Score |
| --- | ---: | ---: |
| tuning 4000-4031 | 32 | 0.484 |
| held out 5000-5063 | 44 | 0.500 |
| pooled | 76 | **0.493 +/- 0.026** |

**ACCEPTED** on the rule that only a measurable regression blocks: the
one-sided 95% upper bound is 0.536. But read it plainly -- the point
estimate is a hair *below* even, and the fix bought nothing the games can
see. Two honest reasons and one thing to check:

- The three cards are Mid War, so they only fire in a subset of games, and
  the gate's half-width here is 0.05. A change confined to three cards
  cannot clear that bar even if it is worth something.
- Taking a free Coup is not free: it degrades DEFCON on a Battleground.
  The bot now takes Coups it used to decline, so some of the value is
  spent on DEFCON.
- One candidate nuclear loss, seed 4015 US T8, and the evidence says look
  at it rather than shrug. **That seat has appeared in 34 recorded gates
  and never once ended at DEFCON 1**; it ends on VP, Wargames or final
  scoring. It is a seat the bot loses every single time (result 0.0 in all
  34), so this costs nothing in score, but the mechanism is new and the
  change is the obvious suspect.

  Against that suspicion: `coup()` already returns the sentinel for a
  Battleground Coup at DEFCON 2 and `none` scores 0, so the free-Coup
  branch should refuse exactly the suicidal ones. The likelier story is
  DEFCON 3 to 2 on a Battleground the *geography* rule would normally have
  forbidden -- a free Coup is exempt from 8.1.5 -- with something else
  taking the last step. **Not resolved: replay it at `bbebbd8` in a
  worktree and read the DEFCON transitions.** Deferred only because the
  working tree carries the uncommitted Military Ops change, and stashing
  it while the corpus generator is reading `src/` would corrupt the
  capture.

The fix stays regardless. Choosing by tuple order is not a strategy, and
"the games cannot measure it" is not "it was fine". This is what the
gate's asymmetric rule is for.

### Seed 4015 replayed: the whole-hand planner did not see a trap seven rounds away

The gate's flagged nuclear loss, run down properly. My guess in the section
above was **wrong** -- no free Coup is involved anywhere in the fatal
sequence. What actually happened is worse, and it is the most valuable
thing found tonight.

Reproduced by replaying `bbebbd8` against the gate's own base snapshot
(mirror self-play at the same commit does *not* reproduce it: the loss
needs the pre-fix opponent, so it is a trajectory difference, not a new
suicidal move).

Turn 8, DEFCON 2 from action round 1 onward. The US hand at AR1:

    Lone_Gunman, Sadat_Expels_Soviets, Willy_Brandt, Iran_Contra_Scandal,
    Portuguese_Empire_Crumbles, Reagan_Bombs_Libya, The_Reformer, Star_Wars

Lone Gunman is a USSR event: playing it for Ops still hands the USSR the
Operations, and at DEFCON 2 the USSR spends them on a Battleground Coup,
which is DEFCON 1 and a loss for the phasing player. So **that one card was
a certain loss from AR1, with seven rounds of warning.** The bot played
every other card first and arrived at AR7 holding it alone:

| Round | Played |
| --- | --- |
| AR1 | Star Wars, event |
| AR2 | Reagan Bombs Libya, event |
| AR3-5 | Willy Brandt, Iran-Contra, Portuguese Empire -- all *USSR* events, for Ops |
| AR6 | Sadat Expels Soviets, Ops |
| AR7 | **Lone Gunman, forced.** "EVERY option is a certain loss" |

Two separate defects, and the planner's own log settles which is which.

**1. The planner reported `risk=0.000` on every option at AR1.** Not a
truncated conservative estimate -- zero. It does see this card: the corpus
notes record Lone Gunman at DEFCON 2 as `risk` 1.0 *once it is forced*. It
simply never propagates that back to the round where it could still be
avoided. `docs/CLAUDE_NOTES.md` opens by claiming the planner will "plan
the whole hand, not the current card"; on this evidence the claim is
overstated. It survives the current round and defers the problem, every
round, until deferring is the losing move. **A card whose forced play is a
certain loss should dominate the whole turn's plan from the moment the hand
is dealt.**

**2. The Space Race slot went unused while a lethal card sat in hand.**
The US did not space at all on turn 8, though it had spaced twice on turn
6, so the option was live. `space_card` picks "the opponent's card whose
Ops-plus-event is worst" *by value*. Lethality does not enter. Spacing Lone
Gunman at any point in seven rounds saves the game outright. This one is
small and self-contained: a card that is a certain loss when forced should
take the space slot ahead of any value comparison.

Worth being precise about blame. The free-Coup fix did not cause this and
the gate did not really "find" it either -- the seat loses in all 34
recorded gates and the change only altered *how*. What the gate did was
put a nuclear loss on a seed whose history made it worth opening, which is
exactly what the warn-and-name rule is for.

This is the strongest argument yet for the hand planner (tier 2), and it
also gives it a test case that does not need a strength gate to score:
seed 4015 US, turn 8, must not arrive at AR7 holding Lone Gunman.
