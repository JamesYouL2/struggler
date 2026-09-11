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

### The Military Ops gate: the first measured improvement in this project's history

`da721fe` against `6d33d91`:

| Sample | Seeds | Score | Signed VP |
| --- | ---: | ---: | ---: |
| tuning 4000-4031 | 32 | 0.547 | +1.08 |
| held out 5000-5063 | 45 | **0.639** | +5.07 |
| pooled | 77 | **0.601 +/- 0.036** | +3.39 |

**ACCEPTED**, and for once that undersells it. Recomputed over the 75
complete seed pairs the score is 0.617 with a one-sided 95% *lower* bound
of 0.559. Every other gate on record sits below 0.500 on that bound:

| Gate | Seeds | Score | 95% lower |
| --- | ---: | ---: | ---: |
| **da721fe** | 75 | **0.617** | **0.559** |
| 40726d0 | 96 | 0.542 | 0.486 |
| fe6ddb0 | 75 | 0.540 | 0.489 |
| cddb7a0 | 96 | 0.510 | 0.489 |

So this is the first change the games can actually say is *better*, rather
than merely not worse. The held-out sample scores higher than the tuning
sample, which is the wrong direction for overfitting and is the strongest
part of the result.

**The fixture and the games disagree, and the games are right.** The
expert table called this neutral: 23 misses to 24, war-row error 0.64 to
0.63. The games call it a ten-point gain. That divergence is the most
useful thing here after the result itself. `models/expert_valuations.json`
is ~30 rows on the *opening board*, and the Military Ops requirement is
worth least on turn 1 -- the discount makes it a sixth of full value there
-- and most in the Mid and Late War, where the fixture has no rows at all.
A fixture that cannot see the change it is asked to judge will call any
such change neutral. This is the concrete argument for the Late War table
and the annotated position suite, and it is now evidence rather than
opinion.

What it cost: 2 candidate nuclear losses against 0-1 in recent gates, both
flagged (seed 4010 USSR T8, seed 5028 USSR T8), inside the rate cap. The
bot Coups more, so it spends more DEFCON. Set against that, it forced the
*opponent* into DEFCON 1 in five games where recent gates saw one or two,
which the acceptance rules correctly score as wins rather than penalties.

One thing not established: the flat, undiscounted version was never gated.
It was rejected on the fixture alone (23 misses to 26). So the evidence
says the discounted form works; it does not prove the discount is *why*.
If that matters later, gate the flat form as an ablation.

### Correction: most of the seed 4015 write-up above is wrong

The maintainer's correction, and it holds up against the log. Read the
section above with this one; I got the same game wrong twice.

**You cannot Space Lone Gunman.** Every Space Race box requires at least
2 Ops (`rules.json`, boxes 1-4 need 2, 5-7 need 3, box 8 needs 4) and Lone
Gunman is a 1-Ops card, so `_can_space_race` refuses it in every position
the game can reach. `space_card` already filters on exactly that check, so
the "the space slot ignores lethality" defect **does not exist**. I
proposed a fix for a rule I had not read.

**Death on turn 8 holding Lone Gunman, to Terrorism or Aldrich Ames
Remix, is not a bug.** It is hand pressure, which the maintainer says is a
normal way to lose and which Codex's tournament notes already record as a
real cause of DEFCON defeats. The log shows exactly that shape: at AR6 the
US held Lone Gunman and The Reformer and correctly played neither of the
lethal lines -- its ranking marks Lone Gunman `lost=1`, so **the planner
does see the card** -- and then the USSR played Terrorism at AR7, which
discarded The Reformer and left Lone Gunman alone. The escape was taken
away, not thrown away.

So the claim that "the planner never saw a trap seven rounds away" is
wrong twice over: it sees the card, and on turn 8 there was no line that
avoids the loss once Terrorism lands. Turn 8 offered the bot nothing.

**What is left, and it is a question rather than a finding.** Lone Gunman
was in the US hand for the whole of turn 7 at DEFCON 5, then 4, then 3,
where playing it is harmless -- the USSR gets one Op. The bot played five
other cards and carried it into turn 8, where DEFCON 2 made it unplayable
all turn. Whether dumping a low-Ops opponent event early, while DEFCON is
still high, is real discipline or hindsight is a judgement call, and I
have now been wrong about this game twice, so it goes to the maintainer
rather than into a term. The repo already has a name for the shape
("self-trapping dumps", in the principles table).

The general lesson is the cheap one: check the rule before designing
around it. Whether a card *can* take the Space Race slot is a one-line
lookup, and it would have deleted half of the previous section.

### The DEFCON prior gate, and a speed claim that was measurement error

`7ba14f0` against `425ac9e`: pooled **0.506 +/- 0.028** over 77 seeds
(tuning 0.469, held out 0.533), **ACCEPTED** and honestly neutral. Two
candidate nuclear losses, flagged for replay (seed 4001 USSR T9, seed 4019
USSR T4), which is the expected direction: a planner that no longer
expects DEFCON to fall every round takes more DEFCON risk. Within the cap.

Keep it anyway. The old 0.75 was seven times a rate that had already been
measured and written down in this repo, and neutral games are not a reason
to keep a number that is known to be wrong. But the *reason* to keep it is
correctness, not strength, and not speed either:

**The speed claim in `7ba14f0`'s commit message is wrong.** It says an
ordinary mid-war decision goes 0.191s to 0.052s. Measured properly --
same process, same corpus positions, the two prior values interleaved so
drift cancels, five repetitions, best of each:

| Position | prior 0.75 | prior 0.15 | speedup |
| --- | ---: | ---: | ---: |
| opening T1 | 0.003s | 0.003s | 1.02x |
| mid-war T5-7 | 0.054s | 0.051s | 1.07x |
| late T8+ | 0.146s | 0.146s | 1.00x |

Nothing. The 3.7x came from comparing two `frozen_bench` runs taken at
*different revisions* and attributing the whole difference to the last
change; everything between them, the Military Ops work included, was in
that gap. The same error produced the claim that the hazardous position's
whole-hand risk fell from 0.469 to 0.081: `frozen_bench` selects the
highest-risk late position *from the corpus*, the corpus was regenerated
in between, so those two numbers describe **different positions**.

And the gate's own timings say the opposite again -- 8.95 s/turn before,
11.31 after -- because those two gates ran under different machine load.
Three measurements, three answers, and only the interleaved in-process one
is worth anything.

This is the same mistake the file already warns about ("never time
anything while a gate runs"), in a new dress. The warning needs widening:
**a timing is only evidence when the two things being compared run in one
process, interleaved, on the same inputs.** Two runs of the same script at
two revisions is not an A/B, it is two anecdotes. Neither is a per-game
average from two gates that shared the machine with different work.

## 2026-09-10 — The bugs this repo actually gets, and what would stop them

Read back over every `fix(...)` commit and the incidents in this file. The
defects are not random: eight shapes account for nearly all of them, and
every one of the eight has now recurred. Listed by how often they have
bitten, with the practice that would have caught each. This is the list to
design against, not a generic checklist.

**Every shape here is gated.** `tests/test_recurring_defects.py` is the
index: it names the tests that make each shape fail, checks those tests
still exist, and reads the counts below -- so recording a new recurrence
here makes the suite ask for the gate. The shapes that had no home
anywhere else are gated in that file too (the sentinel, interleaved
timing, the characterisation-test convention); the rest are listed and
live beside their subject.

### 1. A cached value keyed on less state than it reads (seven times)

`7cb9fbe` two evaluator memos ignoring neighbouring influence; `9d9890f`
valuing only the countries an event touched; the rollout cache not syncing
the board; MCTS leaves inheriting the last ranking's context; the
`_event_basis` surviving across decisions; and tonight the VP price, where
`coup -> vp_value -> ops_value -> coup` made one Op worth 28.43 or 27.78
depending only on which arm of the ranking asked first.

The seventh was the forward search: `_after_reply` moved the board and
then called `delta`, which prices against per-decision caches keyed on the
board as synced. Not a stale number but an inverted *sign* -- the term
written to discourage poking encouraged it, and the minimum-poke rate sat
at 13 a game instead of falling to 0.25. Written hours after this list
was. Gated by `tests/test_base_cache_discipline.py`.

**The practice: an order-independence property test.** Every one of these
is the same assertion -- *evaluating the same position twice, in different
orders, gives the same numbers*. That is a property test over the corpus
positions and it is cheap. The pure-function extraction into `evaluator.py`
was the right structural move and did not stop instance six, because the
cycle was in the stateful wrapper. **Nothing may be memoised until this
test exists**, and the planner memoisation is next in the queue.

### 2. A sentinel used as a number (four times)

`LOSS = -1e6` means "certain defeat", and it has escaped into arithmetic
through `ops_value`, `_resolve_sandbox`, `hold_value`, and dice averaging
(`0.4167 * LOSS`). Each time the fix was another clamp.

**The practice: make it unrepresentable.** A separate type -- `Certain`
versus a float price -- so the type checker refuses the mean of a hand
containing defeat. Codex proposed this independently. Clamps are a fourth
patch on a design that invites the mistake.

### 3. The measurement comparing something against itself (six times)

`871b170` snapshotting two files instead of the package; the gate running
against a dirty working tree; counting the opponent's nuclear losses as
the candidate's; drawing unplayed seeds from the wrong sample; and tonight
the package loader, where a baseline would have bound the candidate's
submodules.

**The practice: negative controls.** A test for an isolation mechanism is
worthless unless it fails when the mechanism is removed. Tonight's first
attempt at one passed either way, and only checking that revealed I was
testing the wrong half. Also worth keeping: the "standard error of exactly
zero" alarm, which is a cheap tell that two things are identical when they
should not be.

The sixth is the parity corpus, and it is the quietest of them. A record
stores the weights it was captured with and the test rebuilds them as
`StrategicWeights(**rec['weights'])` -- so a weight added *after* capture
is absent from the record and filled from the current default. The oracle
then takes two of its inputs from the code it exists to check. It sat
harmlessly for as long as the new weights' defaults did not move, and
surfaced the day `reply_model` went from 0 to 3: 525 records "failed"
against behaviour they had never recorded. Backfilled at the values in
force at capture (`reply_model=0`, the search not yet existing), which
restores the oracle without re-running anything, and gated by
`test_every_record_pins_every_weight` -- every field of the dataclass
must appear in every record.

### 4. Two implementations of one rule, drifting (four times)

`cddb7a0` three copies of region scoring, only one of which knew about the
scoring overrides; two Ops estimates, one for card choice and one for the
Ops-type branch; and the invariant checker, where the copy in the property
tests was silently the weaker.

**The practice: derive, then prove equality exhaustively.**
`test_coup_forbidden_matches_the_engine_under_every_prohibition` walks all
32 flag combinations against the engine's own answer, and asserts each
prohibition fired at least once. That is the pattern to copy whenever the
bot mirrors an engine rule.

The fourth: `Decision.public()` hides an option list that names cards, and
decided "names cards" as `"card" in option.payload` -- the rule written a
second time, as a key name. Blockade asks the US to discard a 3+ Ops card
and keys its options `choice`, so the qualifying part of the US hand went
into the shared history both players are handed. Found by
`tests/test_history_privacy.py`, which asks the rules' question instead:
every card id in the shared history must already have been revealed by an
event the history carries. The filter now matches option *values* against
the card ids, which cannot be forgotten when a new decision spells its key
differently.

### 5. A silent fallback hiding a defect (twice, and it paid off once)

`event_value` caught every exception and substituted a plausible estimate,
so a programming error read as an approximation. `b5466cc` made unexpected
failures a warning and recorded them. **That fix caught tonight's bug**:
the Military Ops sandbox credit read a variable that is an evaluator index
rather than a `Side`, and every sandboxed event fell back silently until
the warning said otherwise.

**The practice: distinguish "unsupported" from "broken" at the type level**
and never let the second be quiet.

### 6. A number on the wrong scale (four times)

VP priced at 0.14 Ops; the event estimate at 0.02-0.06 Ops; the DEFCON
prior at seven times its measured rate; Military Ops at an eighth of a VP.
Each was a hand-set constant sitting next to quantities on a different
scale.

**The practice: units in the name, and one conversion point.** Every
weight should say what it multiplies. `military` is now a multiplier on a
VP, not a raw number, and reads that way.

### 7. Timing measured under uncontrolled conditions (three times)

"Never time anything while a gate runs" was already in this file, and I
did it anyway, twice tonight: a 3x slowdown that was contention, and a
3.7x speedup that was two runs at different revisions.

**The practice: both arms in one process, interleaved, same inputs.**
Anything else is two anecdotes.

### 8. A test that encodes the defect as the contract (twice)

`test_mutation_can_be_restricted_to_named_weights` asserted that *every*
weight changes under a default mutation, which is exactly the bug -- the
disabled terms were being switched on. The parity test that expected a
`vp` ending partway through Final Scoring preserved a rules defect the
same way.

**The practice: assert intent, not observed output.** When a test is
written to pin current behaviour rather than desired behaviour, say so in
its name or docstring so the next reader knows it is a characterisation
test and not a specification.

### Seed 4015, third pass: the residual question was the real finding

The maintainer, reversing their own correction: **the bot needs to play
Lone Gunman before DEFCON 2.** Carrying it is the error.

So the sequence on this one game was: I claimed two defects, both wrong
(you cannot Space a 1-Ops card, and the planner does see the card); the
maintainer corrected both and said a turn-8 death to Terrorism while
holding it is hand pressure, not a bug; what I left over as "a question
rather than a finding" -- that it sat in hand through all of turn 7 at
DEFCON 5, 4 and 3 -- is the actual defect. The death was not avoidable by
turn 8. **Arriving at turn 8 still holding it was.**

The mechanism, stated so it can become a term. Lone Gunman hands the USSR
its Operations. At DEFCON 3 they spend them on a Battleground Coup, DEFCON
falls to 2, and the game continues. At DEFCON 2 the same Coup ends it, and
the phasing player loses. So the card has a **safe window that closes as
DEFCON falls**, and the bot has no notion of one. It ranked Lone Gunman
last every round of turn 7 because playing it is worth little, which is
true and beside the point: its value is not what it buys, it is that
playing it now costs almost nothing and later costs the game.

This is the clearest argument yet for the hand planner, and unlike the
rest of that case it names the objective precisely: a card is worth
disposing of early in proportion to *the chance its safe window closes
before the hand is emptied*. The DEFCON planner already enumerates the
state space that answers this -- hand, rounds, DEFCON -- and already knows
Lone Gunman is lethal at DEFCON 2. What it does not do is look forward
from a safe DEFCON to an unsafe one and price the difference. That is the
change: the search exists, the objective is missing.

Worth noting for its own sake: the cheap version may not need the full
planner. "Play a card whose forced value is certain defeat at DEFCON 2
while DEFCON is still 3 or more, if nothing better is pressing" is a
disposal-urgency term over the existing per-card risk, and the seed 4015
turn-7 position is its test case. Try that before building the planner,
because if it captures most of the value the planner's justification
shrinks to scoring timing and hold choice.

### The hand planner's real justification, from the maintainer

Not survival, and not only the disposal urgency the Lone Gunman position
argues for. The objective is **minimising the opponent's event value per
turn while maximising your own, measured in VP per Op** -- which is a
different and much larger thing than "do not die". Every card you must
play is a decision about whose event fires and when; a turn is an
assignment problem over that, and the survival search already enumerates
the state space it would run on.

Their estimate: **about 75% of the value of the MCTS work**, number
explicitly not calibrated. That is worth taking seriously against
tonight's MCTS measurement, which came in at 0.547 +/- 0.062 -- not
significant -- with 58% of its searches choosing a move on fewer than five
visits. If the planner captures most of what a search would, at a fraction
of 650 seconds a game, then the search's remaining case is narrow.

It also reframes the cheap disposal-urgency term: that term addresses the
*survival* corner of this objective only. Worth trying first because it is
a day and it has a test case, but it is not a substitute, and the notes
should not pretend the planner's justification shrinks to scoring timing
and hold choice if it works.

### The VP-cycle fix was rejected, and the reason is worth keeping

`a12d2af` priced a VP off the placement spend instead of `ops_value`,
breaking the `coup -> vp_value -> ops_value -> coup` cycle. Gate:

| Sample | Seeds | Score | Nuclear losses |
| --- | ---: | ---: | ---: |
| tuning | 32 | 0.320 | 6 |
| held out | 63 | 0.492 | 7 |
| pooled | 95 | **0.434 +/- 0.033** | **13** |

**REJECTED** -- upper bound 0.489, and thirteen nuclear losses against
nought to two in every recent gate. Reverted.

The mechanism is one line: `game_value = GAME_SWING_VP * vp_value`. The
placement-only price is *lower* than the better of a placement and a
Coup, so cheapening a VP cheapened **losing the game**, and the risk that
`safety_key` prices against it became affordable. The bot bought fatal
risk at a discount. Thirteen nuclear losses is not a side effect of the
change, it is the change.

Two things to take from it.

**The cycle is load-bearing.** It is not an accident to be tidied away:
the VP price is the numeraire for risk as well as for value, and any
change to it moves how much the bot will pay to avoid dying. A future
attempt has to hold `game_value` fixed while breaking the cycle -- for
instance by pricing the *risk* numeraire separately from the *value* one
-- rather than redefining what an Op is worth.

**The order-independence test is scoped by this.** It re-establishes the
VP price first, as `rank_actions` does, so it asserts what production
guarantees. Asked genuinely cold the values still differ, and that is now
a known, deliberate limitation with a gate result behind it rather than
an oversight. Recorded in the module docstring.

A cheaper reading: I found a real inconsistency, fixed it in the obvious
direction, and the obvious direction cost 0.07 and a nuclear loss every
seven games. The parity corpus said 8 positions changed their action and
the expert table said nothing changed at all. **Neither instrument could
see this; only the games could.**

### Improving DEFCON is worth about an Op, and the bot prices it at zero

The maintainer, unprompted: *acting immediately after a DEFCON
improvement in the Mid to Late War is worth an Op, because of the free
Battleground Coup it unlocks.* Their own judgement is that it does not
need a parameter -- it is a constant, not a term.

They are describing rule 6.3.4 from the other side. DEFCON 4 forbids Coups
in Europe, 3 also Asia, 2 also the Middle East, so improving DEFCON
**re-opens a region to Coups**, and the side that improved it acts first.
The value is the tempo of a Coup the opponent could not have made a moment
earlier.

The bot cannot see any of this. The event sandbox values an event by the
influence it moves and the VP it awards; DEFCON is neither, so an event
whose effect is "improve DEFCON one level" prices at exactly 0 -- the
flag-only blindness again, in a case nobody had listed as flag-only.
`defcon` does reach `country_value`, but only to gate Coup prohibitions
and the `wipe` term, which ships at 0.

Cards this under-prices, all of them by roughly the same Op: Glasnost,
Salt Negotiations (two levels), Summit's raise branch, Warsaw Pact's
partner NATO, and every Coup the bot declines to make in a region it has
just unlocked. It is a small constant and a wide one.

Worth adding to the flag-only list in `docs/EXPERT_ASKS.md` item 4 rather
than treating as its own item: same cause, same fix.

**Still unresolved, and the arithmetic does not close.** If the DEFCON
improvement alone is worth ~1 Op, and Glasnost's whole base is 1.0, then
its 2 VP to the USSR is worth about nothing -- against a stated Late War
scale of 2 Ops per VP, which would put those 2 VP at ~4 Ops on their own.
Three readings and I cannot pick between them from here: granted VP
converts differently from bought VP; or the DEFCON improvement is a real
*cost* to the USSR that cancels the VP; or the 2-Ops-per-VP rule is a
buying price rather than a holding value. `vp_late` is 2.0 and every Late
War VP event is priced through it, so this is worth one sentence from the
maintainer.

### Twenty Late War valuations, and what my errors were actually made of

Scoring my own estimates against the maintainer's, on the fourteen cards
where a comparable number exists: **7 within the 0.75 tolerance, 5
overpriced by an Op or more, 2 underpriced by an Op or more.** The split
is not noise, it is two clean groups:

| Overpriced | Mine | Expert | | Underpriced | Mine | Expert |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| Glasnost (base) | 4.0 | 1.0 | | Aldrich Ames Remix | 3.5 | 6.5 |
| The Iron Lady | 3.0 | 0.5 | | Tear Down This Wall | 4.0 | 5.0 |
| Ortega | 2.5 | 0.5 | | | | |
| LADC (base) | 2.5 | 0.0 | | | | |
| An Evil Empire (base) | 2.5 | 1.5 | | | | |

**Every card I overpriced is conditional, and I priced each at its best
case.** Glasnost's bonus taken as its base, An Evil Empire's Flower Power
case as its base, Ortega's free Coup without its DEFCON cost, Latin
American Debt Crisis assuming a country flips, The Iron Lady's Socialist
Governments cancellation as though it usually matters. **Both cards I
underpriced are unconditional with a large realised swing.** So the error
is not a level bias to correct; it is that I collapse a distribution to
its best case and compress the top of the range.

That has a direct consequence for the bot, and it is not the same
mistake. The bot also has exactly one number per card, so it must collapse
conditionals too -- but it collapses them by *simulating the actual
board*, which is the right way and is strictly better than my guess. The
places it fails are where the condition is not on the board it can see:
Flower Power being active, John Paul II having been played, whether the
US will be forced to play Socialist Governments for Ops, and above all
**win probability**, which it does not represent at all.

### The rule that explains the whole exercise

The maintainer: **context-dependence scales with the turn.** Early War
values are the least context-specific, Mid War in between, Late War the
most, because more turns played means more state a value can hang on.

That is why `models/expert_valuations.json` -- thirty constants on the
opening board -- works as a fixture at all, and why the Late War table
will never be a list of constants. Of the twenty Late War entries now
recorded, **eight are schedules or formulas rather than numbers**. It
also predicts the Military Ops result: a term that pays in the Late War
was invisible to an Early War fixture, and the games saw it.

The design consequence is bigger than the fixture. A single number per
card is the right shape for the Early War and the wrong shape for the
Late War, and the bot uses one shape throughout.

### Three corrections that change the roadmap

**Win probability is a parameter, not a nicety.** The maintainer, flatly.
Nothing in `bots/` represents it: `game_value` is `GAME_SWING_VP * 40` at
this turn's VP price, whatever the position. So every risk trade the bot
makes is priced against the same constant whether it is winning by
fifteen or losing by fifteen -- and Wargames, whose entire worth is the
uncertainty it removes, cannot be priced at all. This is now the largest
single structural gap, ahead of the hand planner in the queue's logic
even if not in its order, because the planner's objective (opponent event
value against your own) is itself worth different amounts depending on
whether you are ahead.

**My "hardest card to value" answer was wrong, and instructively.** I
argued Bear Trap and Quagmire, because their value depends on *future
draws*. The maintainer: redraws are random and are modelled by an average
draw; the value should change only with **hand knowledge**, yours and the
opponent's. So the temporal axis I invented collapses, and Bear Trap sits
in the same class as Missile Envy and UN Intervention -- a hidden hand,
not an unknowable future. That is a much smaller and more tractable
problem than I made it, and it is a modelling instruction: **do not build
machinery for draw variance; build it for hand belief.**

Which leaves exactly one genuinely missing quantity behind all of these,
and it is the same one: win probability.

**The China Card is worth about 5 to hold.** The floor is a 2 VP swing,
which at the Late War rate of 2 Ops per VP is already 4 Ops, and it is
basically always worth more. The bot charges 4 for playing it (`score`'s
card branch), which encodes a holding value of 4 -- the right shape, a
little low.

### Correction: improving DEFCON is usually a gift to the *opponent*

I recorded "acting immediately after a DEFCON improvement is worth an Op"
and treated it as a benefit to the side that improves it. The sign is
usually wrong, and the maintainer's Glasnost explanation is why.

The mechanism is not the regional restriction I assumed (8.1.5 geography,
which never covered Africa anyway). It is that **at DEFCON 2 any
Battleground Coup ends the game**, so improving to DEFCON 3 makes
Battleground Coups safe again *everywhere*. The value goes to whoever
acts next -- and after your own action round, that is your opponent about
80% of the time.

So Glasnost's base finally adds up: 2 VP to the USSR, worth roughly 4 Ops
at the Late War rate, **minus** handing the US a free Battleground Coup
worth about the same. Base 1.0. The arithmetic that would not close was
missing a cost, not a discount on the VP, and `vp_late` at 2.0 is fine.

Two consequences.

**The bot has this backwards twice over.** It prices a DEFCON improvement
at 0 (the sandbox measures influence and VP), and my proposed fix would
have added a *positive* constant for the improver. The correct treatment
is a transfer: mostly negative for the side that improves DEFCON, positive
for the side that moves next.

**It is the same shape as Military Ops.** Both are turn-order effects that
the position evaluator cannot see because they are not on the board, and
both are worth about a card. That is now two, which suggests looking for
the rest rather than patching each.

Also from the maintainer, and it belongs in the Battleground table: **a
free Battleground Coup in the Mid to Late War is worth almost 2 VP by
itself**, and the proposal is to value Battleground Coups as equal to an
Africa Battleground (Angola, Zaire, Nigeria). Noting a tension to resolve
with them: the Sankt-derived table puts an Africa Battleground at ~4 VP,
so "a Coup is worth almost 2 VP" and "value a Coup as an Africa
Battleground" differ by about a factor of two unless the second means the
marginal rather than the total.

### The Battleground table, answered as structure rather than numbers

The maintainer declined to give per-region constants and gave the rules
that generate them instead, which is better and is directly
implementable.

**Europe Control is 40 VP.** Today it is `null` in `rules.json` and a bare
`1_000.0` in `greedy._scoring_card_favorability`. Forty is the whole VP
track, which is what an automatic victory is worth, and it puts Europe on
the same scale as everything else instead of a magic number.

**What a marginal Battleground is worth, by what it swings:**

- **Domination hinges on a one-Battleground differential.** 3 against 2,
  or 2 against 1: the tier turns on being strictly ahead, not on a
  threshold. So the Battleground that takes you from level or behind to
  ahead is the whole tier, and the next one is worth almost nothing.
- **Control only matters when you are one away**, because Control needs
  *every* Battleground in the region (`board.region_tier`:
  `side_bg == total_bg`). Central America at 2 of 3, Africa at 4 of 5.
- **Presence matters only if you hold no Battleground.**
- **Ignore country count everywhere except Asia.** That is a deletion:
  `margin_country` (0.05) can go to zero outside Asia, which is one fewer
  tuned weight and serves the audit.

**The sharp prediction, and the test case.** Because Control needs all
Battlegrounds and Domination needs only strictly more, the *second to
last* Battleground in a region buys nothing -- it neither creates
Domination (already held) nor reaches Control. In the six-Battleground
regions that is the fifth, so **the 5th Battleground in Asia and the
Middle East are the worst on the map at turn 4**. That follows from the
engine's own tier rule, and it is exactly the non-linearity an additive
per-country value function cannot represent.

It is also a free check on the bot: rank every Battleground on a turn-4
board and see whether the fifth Asia and Middle East ones come last. They
almost certainly do not, since `battleground` is a flat tier weight times
a regional scoring weight.

**Calibration positions offered:** turn 1 and turn 4 Mid War with all
scoring cards still in the deck. That is the fixture the current
opening-board table cannot be -- see the context-scaling rule -- and it is
what the `margin_*` weights should be fitted against.

### The dead Battleground is not dead: it is an option on Control

Refining the previous section with the maintainer. Every Battleground I
called "dead" -- the one that creates no Domination because you already
hold it -- turns out to be **exactly one away from Control**, because
Control needs the whole region. So its value is not zero:

    dead BG  =  insurance on the Domination you hold  +  P(Control) x Control VP
                (~0.5 VP)

| Region | Control VP | Dead BG | Away from Control |
| --- | ---: | ---: | ---: |
| Europe | **40** | 4th | 1 |
| Asia | 9 | 5th | 1 |
| Middle East | 7 | 5th | 1 |
| Africa | 6 | 4th | 1 |
| South America | 6 | none | - |
| Central America | 5 | none | - |

With Europe Control at 40 this is not a small correction. **Europe's 4th
Battleground is worth several times Asia's 5th** on the option term
alone, though both look identical to a tier-based value function. The
maintainer's ~2.5 VP figure is the ordinary case; Europe is the exception
and the whole reason Control VP has to scale it.

Which sharpens the earlier claim rather than overturning it. The 5th
Battleground in Asia and the Middle East really are the worst on the map,
but the reason is not that they buy nothing -- it is that their Control
prize (9 and 7) is small against the difficulty of holding *all six*
Battlegrounds. Europe's dead Battleground has the same shape and a
40-point prize.

**Two quantities the margin term needs, neither of which it has:**

1. **Tier fragility.** Domination at a +1 differential dies to one swing;
   with no Battlegrounds left for the opponent it cannot. The maintainer's
   South America case: at 2 against 1 you dominate, but the free
   Battleground means the opponent can reach 2-2, so the third is
   insurance rather than progress. Cheap to compute -- it is just how many
   Battlegrounds the opponent can still take.
2. **Distance to Control, priced by that region's Control VP.** Currently
   nothing distinguishes being one Battleground from Control in Europe
   from being one away in Africa.

And Central America and South America are the flattest regions precisely
because three and four Battlegrounds leave no room for a middle one:
every Battleground taken from the Domination point onward changes a tier.

### The region margin, specified

Enough has now arrived to write this as a function rather than tune it.
Collecting the maintainer's rules into one place, in the order the value
accrues as you take a region.

**1. Presence is a tier, and one Battleground denies Control.** The first
country in a region buys Presence. The first *Battleground* additionally
makes the opponent's Control impossible outright, because Control needs
`side_bg == total_bg` -- there is no partial version. In Europe that is
denying an automatic victory, so the first Europe Battleground carries a
denial term worth a share of 40 VP whatever else it does. Nothing in the
current function represents denial at all.

**2. Linear up to Domination.** Between Presence and the Domination
differential the value is roughly linear in Battlegrounds -- this part
the existing `progress` and `margin_battleground` terms already
approximate, and it is the part they get least wrong.

**3. The differential is the tier.** Domination turns on `side_bg >
opp_bg`, so the Battleground that takes you from level or behind to ahead
is worth the whole tier and the next is worth much less. A threshold
model gets this wrong in both directions.

**4. Equality is worth something on its own.** Being level on
Battlegrounds *blocks* the opponent's Domination. That is a real
defensive value with no term today: the bot sees no difference between
being level and being one behind, when one denies a tier and the other
concedes it.

**5. Insurance, once ahead.** A +1 differential dies to one swing; it
stops dying when the opponent has no Battlegrounds left to take. The
South America 2-against-1 case: the third Battleground is insurance, not
progress.

**6. The last Battleground is an option on Control**, priced by that
region's Control VP -- 40 in Europe against 9 in Asia and 6 in Africa.

So the shape is: `denial + linear progress + tier step at the
differential + insurance + option on Control`, with Control VP scaling
the last and the first. Six regions, one function, and it replaces
`margin_presence`, `margin_battleground`, `margin_country` (which goes to
zero outside Asia) and part of `progress`.

That is four tuned weights becoming one structured function with two
constants -- the insurance rate and the Control option rate -- which is
the kind of collapse the weights audit was supposed to find and could
not, because the structure had to come from outside.

### Forced defensive spend, and why Europe is not like the other regions

The maintainer, correcting the Aragorn row rather than accepting it:
Europe's 4th Battleground is **2 VP plus about 2 Ops the opponent must
spend defending**, and at Mid War that is a lot. The 2 VP figure is not
wrong so much as half the quantity. And the reason it generalises to
*every* Europe Battleground, and to no other region, is Control.

Europe Control is an automatic loss for the opponent. So any credible
progress toward it **obliges them to spend Ops defending**, whether or
not you ever get there. Everywhere else Control is 5 to 9 VP --
unpleasant, survivable, and therefore optional to contest. That is the
asymmetry, and it is not in the tier structure at all: it is a cost
imposed on the opponent's *future turns*, not a change in what the region
scores.

So the region-margin specification gains a seventh element:

7. **Forced defensive spend.** Proportional to the credibility of your
   Control threat times what Control costs them. In Europe that is large
   for every Battleground; elsewhere it rounds to nothing.

Which also settles the "Europe's 4th is only 2 VP" reading I had checked
as internally consistent. I made it consistent by inferring a ~4% chance
of Europe Control -- the table silently embedding a probability. The
maintainer's answer is better: the threat pays whether or not it is
realised, because the defending Ops are spent either way. **A term keyed
on P(Control) alone would still be wrong; it has to charge for the
defence the threat forces.**

This is the third quantity found today that lives in turn order and
opponent obligation rather than on the board -- after the Military Ops
requirement and the DEFCON hand-off. The position evaluator cannot see
any of them, and that now looks like a category rather than a list.

**Calibration point agreed: start of turn 4.** Per-Battleground values
are to be defined there, which is exactly where all six regions first
weigh the same (Africa, Central and South America go 0.51 -> 0.80 ->
1.64 across turns 1, 3 and 4, matching Europe/Asia/Middle East). Turn 4
is the one board on which a single flat table is even coherent.

### Per-country adjustments, and the class of card that makes overprotection useless

The maintainer's per-country notes, calibrated at **start of turn 4** like
the region table above. These are adjustments to the per-Battleground
value, not replacements for it.

| Country | Adjustment | Because |
| --- | --- | --- |
| Thailand | **up**, to ~6 VP + the Asia Battleground | Southeast Asia Scoring counts it twice. The biggest non-Europe country on the map at start of turn 4 |
| India, Pakistan | −1 VP each | Indo-Pakistani War in the deck |
| South Korea | −1 VP | Korean War in the deck |
| Egypt | −2 VP | Sadat Expels Soviets in the deck. Muslim Revolution also bites |
| Israel | −1 VP | Arab-Israeli War in the deck |
| Iran | −1 VP each | Iranian Hostage Crisis, Iran-Iraq War |
| every South American country | **+1 VP** | Realignment is far swingier there |
| 1-stability African Battlegrounds | discount to **1/4 – 1/3** | Less stable than the 2-stability ones and jammable by a 4-Ops play. Still better value per Op, just not by the ratio the stability numbers imply |

**Every one of these is conditional on the card still being live**, which
makes the whole table implementable: `public_cards.card_state` already
distinguishes `removed` / `discard` / `future` / `unseen` without breaking
mandate #4. The discount is simply not applied once the card is `removed`.

And the removal flags decide whether a discount ever lifts:

| Card | Removed after firing | So the discount |
| --- | --- | --- |
| Korean War | yes | lifts permanently once it fires |
| Sadat Expels Soviets | yes | lifts, for its half of Egypt |
| Iranian Hostage Crisis, Iran-Iraq War | yes | lift |
| **Arab-Israeli War** | **no** | never lifts (except via Camp David, which blocks it) |
| **Indo-Pakistani War** | **no** | never lifts |
| **Muslim Revolution** | **no** | never lifts (except via AWACS, which cancels it) |

So Israel, India, Pakistan and the Middle East carry a *standing* discount,
while South Korea and Iran carry one that expires. The bot currently
applies neither.

### The Middle East cannot be overprotected, and Asia cannot be wiped

Asked which non-war cards can erase a whole country's Influence, here is
the complete list the engine implements (`whole=True`, or a named
`remove_all_influence`):

| Card | Period | Wipes | Where |
| --- | --- | --- | --- |
| Truman Doctrine | Early | USSR | one *uncontrolled* Europe country |
| Warsaw Pact Formed | Early | US | 4 Eastern Europe countries |
| Blockade | Early | US | West Germany, unless the US discards 3+ Ops |
| Nasser | Early | US | Egypt — half, rounded up |
| De Gaulle Leads France | Early | US | France — 2, not a wipe |
| **Muslim Revolution** | **Mid** | **US** | **2 of Sudan, Iran, Iraq, Egypt, Libya, Saudi Arabia, Syria, Jordan** |
| Sadat Expels Soviets | Mid | USSR | Egypt |
| Marine Barracks Bombing | Late | US | Lebanon, plus 2 elsewhere in the Middle East |
| Iranian Hostage Crisis | Late | US | Iran |
| The Iron Lady | Late | USSR | UK |
| Ortega Elected in Nicaragua | Late | US | Nicaragua |

Two things fall out, and both are larger than the Egypt note that prompted
the question.

**Muslim Revolution reaches five of the six Middle East Battlegrounds.**
Libya, Egypt, Iraq, Iran and Saudi Arabia are all on its list; only
**Israel** is not. It is a 4-Ops USSR card that is *not* removed after
firing, so it returns at every reshuffle. For the US the conclusion is
categorical rather than per-country: **there is no such thing as
overprotecting a Middle East Battleground other than Israel**, because the
Influence can be removed entire without the USSR spending an Op on the
board.

**Correction, and the same mistake for the third time.** I concluded from
this that AWACS Sale to Saudis, which cancels Muslim Revolution, must be
worth well more than a 3-Ops US card. The maintainer: Muslim Revolution's
event is very strong on the board but "the marginal value of it over Ops
is only 1" — it is a 4-Ops card, so playing it as an event beats simply
spending the four Ops by about one. Cancelling it is therefore worth
around half an Op, and AWACS matters mainly as a way to defuse Muslim
Revolution as a hand trap in the Late War. **A card is worth its event
minus its own printed Ops, and a denial card is worth the opponent's
margin, not the event's board effect.** Third recurrence of shape 6, "a
number on the wrong scale", and the same error as Warsaw Pact Formed.

Israel is not the safe harbour the Muslim Revolution list makes it look,
either. **Arab-Israeli War targets Israel specifically**, is not removed
after firing, and a won war does not wipe: `core.py:2157` **seizes**,
moving the defender's Influence to the attacker, so it is a 2-for-1 swing
rather than a removal. Camp David is the only thing that blocks it. The
maintainer's own ranking puts Israel seventh of eleven and Egypt third —
Israel's worth to the US is access to Lebanon, Egypt and Libya, not the
Battleground itself.

**Asia has no wipe card at all.** Nothing in the list above touches Asia,
in any period. Every Asian Battleground can be lost only to a Coup, a
Realignment, or the two war cards. That is the exact inverse of the Middle
East, and it is a reason to prefer Asian Battlegrounds at equal VP that
neither the region table nor the country table above expresses.

The asymmetry within the list is worth noting too: of the eleven cards,
**eight wipe US Influence and three wipe USSR Influence**. Overprotection
is a US problem far more than a USSR one.

Adjacent to the class, and the reason the question was framed as
"overprotection": **Shuttle Diplomacy** (Mid, US, not removed after
firing) drops one USSR-controlled Battleground from the next Middle East
or Asia scoring. It removes nothing from the board, but it makes the
marginal Battleground worthless at exactly the moment it would have been
counted.

### Turn-1 Battleground importance for the US, priced in Ops-to-reach

The maintainer's proposal was Egypt / Pakistan / France at the top, on
wipe and adjacency, with Malaysia-for-Thailand as roughly the fourth place
Ops go. Three of those four are *second-hop* Battlegrounds, so the honest
comparison is total Ops from the setup, which the board file settles.

The US controls exactly two countries at setup: **UK** (5 Influence,
stability 5) and **Australia** (4, stability 4). Everything reachable on
turn 1 follows from those two plus the countries the US already occupies:

| Line | Ops to control | Battlegrounds bought |
| --- | ---: | --- |
| UK → **France** | 3 | 1 |
| Iran (1) → **Pakistan** (2) | 3 | 2 (Iran is itself a Battleground) |
| Australia → Malaysia (2) → **Thailand** (2) | 4 | 1, but Thailand counts twice in Southeast Asia Scoring |
| Israel (3) → **Egypt** (2) | 5 | 2 |

Overlaying the wipe exposure from the section above changes the order:

- **France, 3 Ops.** One Early War card takes 2 back (De Gaulle) and
  nothing in the Mid or Late War touches it. Five adjacencies — UK, West
  Germany, Spain/Portugal, Italy, Algeria — the most of any reachable
  Battleground. And it is the only one of the four that carries Europe's
  forced-defensive-spend multiplier. First, clearly.
- **Iran → Pakistan, 3 Ops for two Battlegrounds.** Cheapest by a
  distance, and the most perishable: Iran is the single most exposed
  country the US holds (Muslim Revolution standing, Iranian Hostage
  Crisis, Iran-Iraq War), and Pakistan carries the Indo-Pakistani discount
  that never lifts.
- **Thailand, 4 Ops.** Zero wipe exposure — Asia has no card in the class
  — and the USSR cannot reach Malaysia or Thailand at all on turn 1; its
  entire turn-1 Asian reach is the two Koreas. The only ways to lose it are
  a Coup (stability 2, so cheap) and Brush War.
- **Egypt, 5 Ops.** The most expensive to reach and the most exposed
  Battleground on the map: Nasser, Muslim Revolution and Sadat all name
  it, and Sadat *hands it to the US for free*.

So: **France, then the Iran-Pakistan line, then Thailand, then Egypt** —
Egypt last, because its wipe exposure is a reason to spend turn-1 Ops
elsewhere, not there. You pay three Ops for Israel before Egypt is even
reachable, to buy the one country the USSR can be evicted from later at
the cost of a 1-Ops US card.

**This is not a disagreement with the maintainer — it is a disagreement
with the bot, and the maintainer already recorded the answer.**
`models/expert_valuations.json` ranks US opening placement **France,
Pakistan, Egypt, Iraq, …**, which matches the derivation above on all
three. The bot's order is **Egypt > Pakistan > Iraq > France**, and it is
one of the five recorded US placement inversions in the expert fixture.

That inversion has a shape: the bot puts both Muslim Revolution targets
(Egypt, Iraq) above France, and France last of the four. **Both
structural terms the maintainer described today would move it the right
way** — Europe's forced defensive spend raises France, and wipe exposure
lowers Egypt and Iraq. Two independently-motivated terms predicting the
same five recorded misses is the strongest evidence so far that they are
real terms and not just good commentary, and it makes the US placement
inversions a cheap way to test them before spending a gate.

Thailand is not in the fixture because it is not a legal turn-1
placement — it is second-hop, behind Malaysia — so its third place here
is an addition to the recorded ranking rather than a check against it.

What this reasoning cannot see, and the maintainer can: contest
probability. It prices Ops-to-reach and card exposure, both of which are
in the data files, and assumes nothing about how hard each is to hold
against a USSR that wants it. Asia's freedom from wipe cards is partly
offset by how cheaply the USSR reaches it once Decolonization and
Afghanistan are out.

### Threat is effect minus printed Ops, and it inverts the whole wipe table

The maintainer, on why Muslim Revolution matters less than it looks:
"war cards are 2 Ops, Muslim is 4. If Muslim were 2 Ops, it would
actually affect VP values more."

That is the general rule, and it is the same one that corrects the AWACS
claim above. **The threat a card poses is its effect minus its own
printed Ops**, because the opponent's alternative is always to spend
those Ops on the board. Ranking the wipe class that way inverts it
almost completely:

| Card | Ops | What it does | Threat per Op |
| --- | ---: | --- | --- |
| Sadat Expels Soviets | **1** | wipes USSR from Egypt entirely | highest in the class |
| Blockade | **1** | wipes US from West Germany unless they burn a 3+ | highest |
| Nasser | **1** | halves US in Egypt, +2 USSR | high |
| Truman Doctrine | **1** | wipes USSR from an uncontrolled Europe country | high |
| Korean War | **2** | **seizes** South Korea, +2 VP, +2 MilOps | very high |
| Arab-Israeli War | **2** | **seizes** Israel, +2 VP | very high |
| Indo-Pakistani War | **2** | **seizes** India or Pakistan, +2 VP | very high |
| Iran-Iraq War | **2** | **seizes** Iran or Iraq, +2 VP | very high |
| Marine Barracks Bombing | 2 | wipes Lebanon, removes 2 more in the ME | medium |
| Ortega | 2 | wipes Nicaragua, free Coup | medium |
| De Gaulle Leads France | 3 | −2 US in France, +1 USSR | medium |
| Iranian Hostage Crisis | 3 | wipes US from Iran, +2 USSR | medium |
| The Iron Lady | 3 | wipes USSR from UK | low |
| Warsaw Pact Formed | 3 | wipes US from 4 Eastern Europe countries | low — the maintainer prices it 0.5 |
| **Muslim Revolution** | **4** | wipes US from 2 of 8 Middle East countries | **lowest in the class** |

So the card the previous section built its conclusion on is the least
threatening one in the table, and the war cards — which the question
excluded — are the most, because seizure is a 2-for-1 swing bought for
two Ops.

This makes the per-country table above *derivable* rather than a list of
constants. A country's discount is the sum, over the cards still live,
of **(what the card does there − the card's printed Ops)**. It predicts
the maintainer's own numbers: Egypt takes −2 because Sadat costs 1 Op and
Nasser 1, the two cheapest in the class, and only a little more from
Muslim Revolution at 4; South Korea, Israel, India, Pakistan and Iran each
take −1 from a 2-Ops seizure.

### Wipe exposure is a variance term, not a discount — and turn 1 is not turn 4

Two corrections that fit together. The maintainer: "turn 1 is obviously
super different than turn 4", and "on turn 4, France by a mile;
Iraq/Pakistan/Iran/Egypt are only important **because of** wipes."

The second reads at first like the opposite of the discount table, and it
is not. The two statements are about different terms:

- **The marginal Influence point** in a wipeable country is worth little,
  because a card can remove the whole stack without the opponent spending
  an Op on the board. That is the discount, and it is what "you cannot
  overprotect the Middle East" means.
- **Whether you hold the country at scoring time** is worth as much as
  ever, and in a wipeable country that outcome is decided by which card
  turns up rather than by who spent Ops. That is what makes Iraq,
  Pakistan, Iran and Egypt *important* at turn 4 with every scoring card
  still in the deck: they are where the VP actually moves.

So wipe exposure lowers the value of the marginal point while leaving —
arguably raising — the value of the tier swing the country participates
in. **Those are different terms in the region-margin function and the bot
conflates them into one.** It has no notion of variance at all, which is
why it cannot express either half.

On the periods: the Ops-to-reach ordering in the previous section is a
turn-1 instrument and says nothing about turn 4, where the setup is long
gone and the Mid War region weights have risen from 0.51 to 1.64. France
leads both, and at turn 4 "by a mile" — which is what Europe Control at
40 plus forced defensive spend predicts. The rest of the turn-1 order does
not carry over.

### The Battleground scale, measured: the bot is 4x low, 5x flat, and orders it wrong

The per-Battleground question finally asked in the right units. Flipping
one Battleground from USSR control to US control, and measuring the whole
board value in VP (seed 4002, start of turn 4, all seven scoring cards
live):

| Region | Mean swing | Range |
| --- | ---: | --- |
| Africa | **1.32** | Angola 1.37 … Nigeria 1.24 |
| South America | 1.30 | Chile 1.36 … Brazil 1.26 |
| Central America | 1.11 | Cuba 1.13 … Panama 1.09 |
| Asia | 0.99 | Thailand 1.32 … Pakistan 0.89 |
| **Europe** | **0.98** | West Germany 1.05 … East Germany 0.89 |
| Middle East | 0.91 | Iraq 0.93 … Libya 0.88 |

The maintainer's answer, same board: **a Battleground is worth at least 4
VP** at turn 4 unscored, the spread between best and worst is **2 to 3
VP**, and the order is **Europe top, South America and Asia second,
Middle East and Central America least**.

Three separate defects, and they are independent of each other:

1. **Scale.** Every Battleground on the map swings about 1 VP where it
   should swing 4 or more. Four times low.
2. **Spread.** The bot's whole map spans 0.88 to 1.37, a range of 0.49 VP,
   against a stated 2 to 3. Five times too flat. Thailand is the only
   country anywhere that stands out, and only because Southeast Asia
   Scoring counts it twice.
3. **Order.** The bot ranks **Africa first and Europe fifth of six**. The
   expert ranks Europe first and Africa in the middle. Central America is
   third for the bot and last for the expert. This is not a
   miscalibration; the ranking is close to inverted at the top.

The third is the one that cannot be fixed by tuning, and the reason is
structural. A Battleground's importance is `w.battleground * urgency`,
and `urgency` is built *only* from how soon and how often the region will
score. It has no term for what Control is worth when it arrives, so
Europe -- where Control ends the game -- cannot rank above a region that
merely scores more often. Africa comes first because it has five
Battlegrounds and cheap tiers, not because anyone thinks it matters most.
**Europe's premium has to enter as its own term**, which is the same
conclusion the forced-defensive-spend section reached from the other
direction.

### Urgency never reaches zero, and its absolute level is not a parameter

Confirmed, as the maintainer expected. `_scoring_weight_uncached` ends with
`w.scoring_final * final_scoring_odds(obs)`, a floor for the end-of-game
scoring that no amount of played scoring cards can remove. Measured: the
floor is **0.75** (seed 4000, turn 9) and the turn-4 values are **1.75 to
2.95**. So it is stable across the game exactly as they said, and it never
drops to nothing.

Their suggested band was 0.5 to 1.5 and the actual is 0.75 to 2.95, but
**the absolute level is not a parameter at all**: importance is
`w.battleground * urgency`, and `w.battleground` is free, so scaling every
urgency by a constant changes nothing. Only two things about urgency are
real -- the ratio between regions, and the ratio between turns. Worth
recording before anyone "fixes" the range and finds the gate cannot see it.

### The China charge is in the wrong units, and rescaling is not a no-op

The maintainer, on the claim that scaling the board terms changes nothing:
"rescaling does matter because of VP cards (like OPEC / Arms Race)."

Measured on seed 4002 at turn 4, scaling `w.battleground` and `w.control`
by 0.5, 1, 2 and 4, OPEC's value stays at exactly −2.000 times the one-Op
value at every scale, so *that* ratio is preserved. But the one-Op value
itself goes 45.02 → 83.77 → 161.25 → 316.21, which is **sub-linear**:
1.86x, 1.92x, 1.96x for successive doublings. So the system is not
scale-free, it merely converges to scale-free as the board terms grow.
Something absolute is anchoring it, and the maintainer is right that the
absolute level is a real parameter -- the earlier note claiming otherwise
was wrong, and is corrected in place above.

Chasing the anchors turned up a bare one. **The China Card charge is
subtracted from `card_play_value`, which is in raw board units where one
Op is worth 83.77 on this board.** The constant is 5.0. That is **0.06
Ops**, where the intent was 5.

And the write-up made it worse rather than better. The code it replaced
was `value -= 4`, which claimed nothing. It was renamed `CHINA_HOLD_OPS`,
documented "in Ops", given a test asserting `>= 4.0` as "the 2-VP-swing
floor", and committed with a message saying it implemented the
maintainer's figure. **Shape 6 (a number on the wrong scale) and shape 8
(a test that encodes the defect as the contract), in the same change, in a
commit whose whole subject was scale discipline.**

It is renamed `CHINA_HOLD_RAW` and left at 5.0 rather than multiplied by
thirty, because the naive correction is worse than the bug: 5 Ops
converted honestly is about 187 raw against a 4-Ops card worth 149, so
China would never be played at all. The maintainer's 5 Ops is what
*holding* the card is worth, and playing it hands that to the opponent
rather than destroying it, so the charge is some function of both, not the
hold value. That needs their number and a gate. The test now pins the
discrepancy so closing it has to be deliberate.

**The open question this leaves**, and it is bigger than China: how many
other bare constants are added to or subtracted from board-unit values?
`value -= max(0, len(obs.hand)-3)` for Five Year Plan is the next one, and
it is at least documented as a tie-break. A sweep is warranted.

### Correction: playing The China Card costs *more* than holding it, and it decays

The reasoning in the section above was backwards. It guessed that because
playing China transfers the card rather than destroying it, the charge
must be *less* than the 5 Ops holding is worth. The maintainer:

> playing it costs 8 ops, yes, until end of game. Basically whoever has it
> on t10 is going to play it 100% of the time (even with a 2 VP swing).
> the transfer is a ton... So playing it is a hand planner decision.

**The transfer is the expensive half.** You lose the option and hand the
same option to the opponent, so the cost is roughly double the hold value,
not a fraction of it. 8 Ops against 5.

And it is **not a constant**: it is a rounds-remaining quantity. On turn 10
there is no future to hold it for, so the charge is zero and the card is
played unconditionally -- against a 2 VP swing, even. The same shape as
`military_credit`, which already divides by `_rounds_left`.

So the target is a term worth about 8 Ops with a full game ahead, decaying
to 0 by the last turn, where the bot currently charges 0.06 Ops flat. That
is not a rescale of `CHINA_HOLD_RAW`; it changes when China is played in
most games and needs a gate. And the maintainer's own conclusion is that
the decision belongs in the whole-hand planner, not in a constant applied
at the point of play -- which makes this the second thing waiting on the
planner, after the safe-window problem.

`docs/EXPERT_ASKS.md` item 7 is answered: holding 5 Ops, playing 8,
decaying to 0 at the end of the game.

### Turn 10 action round 7: the play that cannot be answered

The maintainer, refining the China charge:

> it's actually basically 8 ops up until t10, where it replaces playing
> your worst card ... t10 ar7 is always like 5 to 10 vp at final scoring
> (I guess we can call it 7), because 4 ops can almost always double break
> and can't be countered. That's a special case.

Two corrections to the section above, and one finding larger than China.

**The decay is not smooth.** The charge is a flat 8 Ops until turn 10, not
a quantity shrinking with the rounds left. On turn 10 it stops being a
charge at all and becomes a comparison: playing China replaces playing
your worst card, so its worth is the gap between the two. That is a
different formula, not a smaller number, and it means copying
`military_credit`'s `_rounds_left` division would be the wrong shape.

**And the last action round inverts it.** At turn 10 action round 7 China
is worth **5 to 10 VP, call it 7**, because four Ops can almost always
break two countries at final scoring and *nothing can answer it*. So the
term is not monotonic: 8 Ops of cost for most of the game, roughly zero on
the last turn, and a large positive on the final action round.

**The generalisation is the part worth keeping.** Nothing about that
depends on the card. The final action round of turn 10 is the one play in
the game with no response, so *any* Ops spent there are worth their full
uncontested effect on final scoring -- no discount for the opponent
rebuilding, no risk of a counter-Coup, no defensive spend forced in reply.
The bot has `scoring_final * final_scoring_odds` for whether the game
reaches final scoring at all, and nothing whatever for **who moves last**.
Every term that quietly assumes the opponent gets a reply is wrong in that
one round, and it is the round that settles a close game.

That makes three quantities now found in turn order rather than on the
board -- the Military Operations requirement, the DEFCON hand-off, forced
defensive spend -- plus this fourth, which is the extreme case of the same
thing: the value of moving last.

### Correction: the turn-10 worst card is about one Op, not eight

The −8.55 Ops reported above was a mean over ten observations dragged by a
single one. Over 20 turn-10 hands:

| | Worst card in hand |
| --- | ---: |
| **Median** | **−1.26 Ops** |
| Mean | −5.33 Ops |

The outlier is **Duck and Cover at −77.97 Ops**, held by the USSR at
DEFCON 2, where playing it degrades DEFCON to 1 and loses the game. Not a
sentinel leak -- `is_certain` is False on all 20 -- but the planner
pricing a near-certain loss at about 78 Ops, which is defensible.

So the earlier claim that turn-10 China clears the maintainer's 8-Ops
crossover was an artifact. On the median the gap is about **4.3 Ops**,
which does not clear it.

What is actually there is more useful than the number that was wrong.
**China's late value is bimodal.** Usually the worst card costs about an
Op and China beats it by a few; occasionally the worst card loses the
game and China is worth almost anything. A mean over those two regimes
describes neither, and the bimodality is exactly the safe-window
structure: China's worth at the end is *insurance against being forced to
play a trap*, which explains "100% of the time" better than an expected
value does.

**The safe-window list is confirmed from play, not from theory.** The most
frequent worst turn-10 holdings are Duck and Cover (3), Lone Gunman (2)
and Grain Sales to Soviets (2) -- three of the eight cards the maintainer
named -- then Marine Barracks Bombing, Aldrich Ames Remix, Che, OPEC and
The Voice of America. Their verdict on the list: "these are all basically
unplayable. I think Marine is the only one that isn't just dreadful, and
it's still bad."

Caveat on the measurement: 24 seeds gives only 20 turn-10 observations,
because most games end earlier. Enough to see the shape and to kill the
mean, not enough to pin either mode.

### Aldrich Ames is already right; Five Year Plan's whole risk is unpriced

Two cards the maintainer flagged, and they come out opposite ways.

**Aldrich Ames Remix is free when it is the last card, and the bot knows
it.** `own_hand = [c for c in obs.hand if c != cid]` excludes the card
being played, so pricing it with one card in hand leaves an empty hand,
`best` falls to 0 and the loss is 0. The engine agrees: `_aldrich_ames`
returns early on an empty US hand. Nothing to fix -- worth recording
precisely because the instinct was to go and fix it.

**Five Year Plan is the opposite: its entire risk is explicitly
unpriced.** From `event_value`:

```
# The victim loses a uniformly random card. Five Year Plan's
# "a US event fires" rider is not priced.
```

The bot charges only the expected loss of a random card. But the rider is
the whole card -- the maintainer: "really safe in early war, pretty safe
in mid war, and **death in late war**" -- and that era dependence comes
entirely from how bad the US event is when it fires. Pricing only the card
loss removes exactly the term that varies. The `DefconPlanner` does model
it (`_hazard` averages over the US cards in hand) but only for terminal
risk, so a Five Year Plan that fires a merely *expensive* US event is
still free to the value function.

The nudge beside it is wrong in a second way:

```
if cid == 'Five_Year_Plan' and obs.side is Side.USSR:
    value -= max(0, len(obs.hand)-3)
```

Another bare constant in board units (about 0.01 Ops per card), and keyed
on the wrong variable. The maintainer: Five Year Plan "loves discarding
negative / even scoring cards / 1-Op cards", so what matters is the
*quality* of the hand and the fraction of it that is US-associated, not
how many cards are in it. The expected loss at line 1620 already accounts
for hand size. The bot computes the per-card hold values three lines
earlier and then throws them away for a card count.

### The game is not worth 40 VP from where you are standing

The maintainer, on China's insurance value: "China is often worth 30 VP
in late war. Rarely 40, because generally you're not ahead by that much
in final scoring without 20 VP edge."

The first half confirms the bimodal reading above and puts a number on the
bad mode: in the late war, holding China is *often* worth three quarters
of the whole game. Against a median turn-10 gap of 4.3 Ops -- roughly 2 VP
-- the bot captures the ordinary mode and misses the mode that matters.

The second half is a finding about a constant, not about China.

```python
GAME_SWING_VP = 40.0
def game_value(self, obs):
    return GAME_SWING_VP * self.vp_value(obs)
```

Flat, symmetric, and used twice: as the cap on `hold_value`, and by
`priced()` to bound a certain outcome before it may be combined. But the
VP track ends at ±20, so **the swing actually available from VP = v is
`20 - v` upward and `20 + v` downward** -- and those are only equal at
zero. At +15 to the US, the US can gain 5 more VP before the game ends and
can lose 35; a flat 40 overstates its upside eightfold and understates its
downside by five VP. That asymmetry is exactly the maintainer's
observation: a card is rarely worth the full 40 because being worth 40
means converting a certain loss into a certain win, which requires a
position close enough to both.

So `game_value` should take a direction, or return the pair. It is a
small change with a wide blast radius -- it touches every sentinel bound
landed tonight -- so it wants its own gate rather than riding along with
anything else. Recorded now because the constant is currently *documented*
as "the whole -20..+20 track", which is true of the track and false of the
position.

### Win probability is now the answer to four separate questions

The maintainer, on the swing constant: "the sentinel being 30 as an
average is probably better (or variability calculated). But win
percentage is more important."

So the cheap fix is `GAME_SWING_VP = 30`, as the average reachable swing
rather than the track's full width -- one line, and strictly closer to
the truth than 40 for the same cost. The better fix is to compute the
reachable swing per position, `20 - vp` and `20 + vp`. Neither is the
real answer.

**The real answer keeps being the same one.** Win probability has now
been named as what a quantity actually depends on in four places:

| Where | What was said |
| --- | --- |
| Late War valuations | "Late War values are the most conditional on **win probability** of any period" |
| Wargames | its worth is `(1 - win_pct) * game_value` -- the uncertainty it removes |
| Terrorism | "swingy on win percentage" |
| `GAME_SWING_VP` | "win percentage is more important" than any average swing |

It appears seven times across `docs/` and `models/`, and **zero times in
`src/`**. The bot has banked VP, a board value, and a flat 40-VP constant;
it has no notion of how likely it is to win, so every one of those four
becomes a constant where the truth is a function.

That is now the largest single missing piece, ahead of the hand planner,
and it is cheaper than it sounds: the benchmark already plays thousands of
games from known positions, so a first estimator could be fitted from
recorded play rather than derived -- board value and VP margin and turn
in, win frequency out. It would replace a constant in at least four
places, and it is the one thing that makes Late War card values
expressible at all.

### Control efficiency reproduces the bot's order, not the expert's

Asked for control VP over the Ops needed to take it. Ops here is the sum
of stability across a region's Battlegrounds -- what it costs to control
every one of them from empty -- with Europe Control priced at the
maintainer's 40 rather than its printed 7.

| Region | BGs | Pres | Dom | Ctrl | BG Ops | **Ctrl per Op** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Europe | 5 | 3 | 7 | **40** | 15 | **2.67** |
| Africa | 5 | 1 | 4 | 6 | 8 | 0.75 |
| Central America | 3 | 1 | 3 | 5 | 7 | 0.71 |
| South America | 4 | 2 | 5 | 6 | 9 | 0.67 |
| Asia | 6 | 3 | 7 | 9 | 17 | 0.53 |
| Middle East | 6 | 3 | 5 | 7 | 16 | 0.44 |

**Europe first by a factor of three and a half**, which is the answer, and
the reason Europe's premium is not a tuning question.

But below Europe the metric gives **Africa, Central America, South
America, Asia, Middle East** -- and the maintainer's order is **Europe,
{South America, Asia}, Africa, {Middle East, Central America}**. Control
efficiency puts Africa second where the expert puts it fourth, and
Central America third where the expert puts it last. That ordering,
Africa high and Asia low, is almost exactly the *bot's* current measured
order.

So efficiency is not the missing term. It measures what a region costs to
take and says nothing about what it costs to keep, and Africa is the
clearest case: its Battlegrounds are 1-stability, so the same Ops that
buy them buy them back. The maintainer already said as much about Africa
-- "1-Op BGs less stable than 2-Op BGs, and can be jammed by a 4-Op,
still more valuable per Op, but discount by maybe 2/3rds or 3/4ths". That
discount is exactly the gap between this table and their ordering.

**Durability is the term, and it is the same one the wipe work found.**
A holding that can be taken back for what it cost is worth less than its
efficiency, whether the taking is a Coup into 1-stability ground or a
free wipe from a 1-Op card. Two independent routes to the same missing
quantity is a good sign it is real.

Africa's place is now the maintainer's word rather than my inference:
**fourth**.

### What function fits the three tiers: one VP per Op, and Europe is not special

Asked what function fits Presence, Domination and Control together. Every
region's three tiers were priced as (Ops to reach the tier uncontested, VP
received including the 10.1.2 bonuses), giving 18 points.

**First answer, and it was wrong.** Using the *minimum* Ops -- the
cheapest country for Presence, the cheapest Battleground plus cheapest
non-Battleground for Domination -- the best fit was strongly concave,
`VP = 3.30 * sqrt(Ops)`, and a constant VP-per-Op model was three times
worse. The maintainer: "consider avg ops, not minimum." That concavity
was an artifact: taking the cheapest country makes the low tiers look
artificially cheap, and the low tiers are where the curvature came from.

**On average Ops the relationship is linear with slope one.**

| Fit | Mean abs error | Max |
| --- | ---: | ---: |
| linear `1.76 + 0.83*Ops` | 1.11 VP | 2.64 |
| power `1.27 * Ops^0.94` | 1.25 VP | 4.25 |
| **proportional `1.00 * Ops`** | 1.42 VP | 3.46 |
| sqrt `3.17 * sqrt(Ops)` | 1.40 VP | 2.93 |

The power fit's exponent is **0.94** -- near enough to 1 that the honest
reading is a straight line. So, over eighteen points spanning three tiers
and six regions:

> **A region pays about one VP for each Op of stability you have to buy to
> reach a tier.**

Two parameters buy little: the linear fit's 1.76 intercept is the fixed
bonus for entering a region at all, and its slope drops to 0.83 to pay
for it. `VP = Ops` is one number and within half a VP of the two-parameter
fit on average.

**This reconciles with the 2-Ops-per-VP rate rather than contradicting
it.** These Ops are the *uncontested* cost of control. Real games are
contested, so if taking a country actually costs about twice its
stability, the realised rate is the familiar 2 Ops per VP -- and the
reason to play the board rather than buy VP directly is that the board
pays double when the opponent lets you have it.

**And Europe is an ordinary region on this curve.** At its printed
Control value it is 13 VP for 15 Ops, against a predicted 15.0 -- and
every region sits between 0.92x and 1.18x of the curve. The scoring
table is internally consistent and Europe is not special in *scoring*
terms at all. Its premium is entirely the automatic victory, which is why
`Europe Control = 40` sits 3.6x off the curve, and why the maintainer
corrects the earlier "3.5x" reading to about **1.67x**: that implies an
effective Europe Control of roughly 15 VP, not 40. The 40 is what it is
worth when it happens; the 1.67x is what it is worth to chase.

**What this says about the bot.** `importance` is
`w.battleground * urgency` -- one constant per region, flat across
Battlegrounds, with no dependence on how many Ops the region absorbs. The
data says value tracks Ops-to-take almost exactly. A region weight
proportional to its summed stability, plus a separate Europe premium of
about 1.67x for the win threat, is a better starting shape than six free
constants -- and it has one parameter instead of six.

### Two exceptions, and both are arithmetic

The maintainer: "Thailand and Europe have to be the only differences,
because of math? That 20 VP minimum jump is real."

Checked, and yes -- exactly two, and neither is a matter of judgement.

**Thailand is the only Battleground scored by two cards.** Seven
countries lie in Southeast Asia and are counted by both Asia Scoring and
Southeast Asia Scoring: Burma, Laos/Cambodia, Thailand, Vietnam,
Malaysia, Indonesia, Philippines. **Thailand is the only Battleground
among them.** Every other country on the map is scored once. That is why
it is the single per-country exception the bot's own numbers already
show -- 0.176 against 0.117 for the rest of Asia -- and it needs no
expert input, because it falls out of the country table.

**Europe is the only region whose Control is a win condition rather than
a VP award**, and the size of it is not a constant:

| VP (US view) | Europe Control to the US |
| ---: | ---: |
| −15 | 35 VP |
| −5 | 25 VP |
| **0** | **20 VP** |
| +5 | 15 VP |
| +15 | 5 VP |

**It is worth `20 - vp`: the distance to auto-victory.** Twenty at par,
which is the "20 VP minimum jump", and more when behind. It is also a
genuine discontinuity -- Europe Domination is 7 VP and Control is 20 at
par, a cliff between adjacent tiers that no smooth function of Ops can
represent.

**And it is the same expression the game-swing work arrived at
independently.** `game_value` should be `20 - vp` upward and `20 + vp`
downward rather than a flat 40; Europe Control's value *is* that upward
swing, because it realises it in one step. Two unrelated threads landing
on one formula.

That also resolves three numbers that looked like they were fighting:

- **40** is the whole track, and is only right from −20.
- **20** is the value at par, and is the honest default.
- **~15**, the maintainer's 1.67x of the fitted curve, is what it is
  worth to *chase* -- the realised value discounted by the odds of
  getting there.

**So the region model reduces to one parameter and two rule-derived
exceptions.** Value proportional to the Ops a region absorbs; Thailand
counted twice because two cards score it; Europe Control priced at the
distance to victory. That replaces six free constants with something
fitted to eighteen points and two facts about the rulebook, and it is a
far better starting shape than tuning six weights against a gate that
needs 96 seeds to see six points.

### The 2x was the 10.1.2 bonuses, and Southeast Asia is the third exception

**The open factor of two is closed.** The maintainer:
"uncontested/uncontrolled is 2 Ops per VP, it's just that in mid war
everything is contested." Splitting the tier value from the 10.1.2
bonuses settles it:

| Region | BG Ops | tier VP | with bonuses | Ops/VP tier | Ops/VP with |
| --- | ---: | ---: | ---: | ---: | ---: |
| Middle East | 16 | 7 | 13 | 2.29 | 1.23 |
| Europe | 15 | 7 | 13 | 2.14 | 1.15 |
| Asia | 17 | 9 | 16 | 1.89 | 1.06 |
| South America | 9 | 6 | 10 | 1.50 | 0.90 |
| Central America | 7 | 5 | 8 | 1.40 | 0.88 |
| Africa | 8 | 6 | 11 | 1.33 | 0.73 |
| **mean** | | | | **1.76** | **0.99** |

**1.76 Ops per VP on the tier alone -- the maintainer's 2 -- and 0.99
with the bonuses, which is what the earlier fit measured.** Neither
number was wrong; they are different quantities. And the split is worth
knowing on its own: **about half the VP a region pays comes from the +1
per Battleground Controlled and +1 per country adjacent to the enemy
superpower, not from the tier.** Europe Control is 7 tier and 6 bonus.

The remaining gap to what a real game costs is contest, as they say:
uncontested is 2 Ops per VP, mid war is dearer because everything is
fought over, and the bot's era rates already encode the progression --
`vp_early 0.5, vp_mid 1.0, vp_late 2.0`.

**And Southeast Asia Scoring is a third exception, not a second.** It
has no tiers at all: `+2 VP for Control of Thailand, +1 VP per other
controlled Southeast Asian country`.

| Country | Stability | VP | Ops/VP |
| --- | ---: | ---: | ---: |
| Laos/Cambodia | 1 | 1 | **1.0** |
| Vietnam | 1 | 1 | **1.0** |
| Indonesia | 1 | 1 | **1.0** |
| Thailand | 2 | 2 | **1.0** |
| Burma, Malaysia, Philippines | 2 | 1 | 2.0 |
| **all seven** | **11** | **8** | **1.38** |

So four Southeast Asian countries pay **1 Op per VP** against a map
average of 1.76, and three of the four are not Battlegrounds. That
breaks two of the rules the region table rests on at once: "ignore
country count outside Asia" is false here, and a non-Battleground with
real VP value exists nowhere else on the board.

**The three exceptions, then, and all three are arithmetic rather than
judgement:**

1. **Thailand** -- the only Battleground scored by two cards, and worth 2
   on one of them.
2. **Europe** -- the only Control that is a win condition, worth `20 - vp`.
3. **Southeast Asia Scoring** -- the only card that pays per country with
   no tiers, making three 1-stability non-Battlegrounds the most
   Ops-efficient VP on the map.

Everything else sits on one line within 18%.

### Thailand is not a multiplier, and Southeast Asia is priced as the wrong kind of thing

The maintainer, correcting "Thailand x2": "Thailand isn't a full x2,
should be 1 + discounted scoring of 4 VP? something like that."

Right, and it exposes a category error that reaches all seven Southeast
Asian countries, not just Thailand.

`importance` is `(w.battleground if battleground else w.control) *
urgency`, and `urgency` sums a contribution per scoring card that will
still score. Being in Southeast Asia adds a second card, so it adds about
1.0 to urgency -- which is then **multiplied by the tier weight**:

| Country | urgency | tier weight | SEA contributes |
| --- | ---: | ---: | ---: |
| Thailand | 2.952 | `w.battleground` 5.0 | **5.0** |
| Malaysia, Vietnam, Laos/Cambodia, Philippines, Indonesia, Burma | 2.952 | `w.control` 1.5 | **1.5** |

So the bot prices Thailand's Southeast Asia scoring at **3.33 times** each
of the others. Southeast Asia Scoring pays `+2 VP for Control of Thailand,
+1 VP per other controlled country` -- **a flat 2:1**. Thailand is
overweighted against its neighbours by 1.67x.

The deeper problem is the shape, not the ratio. **Southeast Asia Scoring
awards flat VP per country; it has no tiers at all.** Routing it through
`w.battleground` and `w.control` prices a flat award as though it were a
Presence/Domination/Control contribution, which is what those weights
mean. No amount of tuning the weights fixes a term that is the wrong kind
of quantity, and the two weights cannot be set to satisfy both Southeast
Asia's 2:1 and the tier structure they exist for.

**The right form is the maintainer's: additive, not multiplicative.**

```
value(Thailand)          = ordinary Asia Battleground value + P(SEA scores) * 4 VP
value(other SE Asian)    = ordinary value                   + P(SEA scores) * 2 VP
```

4 and 2 rather than 2 and 1 because these are *swings*: holding Thailand
is +2 VP at the scoring and the opponent holding it is −2.

`P(SEA scores)` is the one free number, and it is measurable rather than
a matter of opinion, because Southeast Asia Scoring is the only scoring
card with `remove_after_event=True` -- it fires at most once per game,
where every other region's card recycles through the reshuffle. A
measurement is running.

This is the third exception earning its place: Thailand's double-count is
not a special case bolted onto the region model, it is a consequence of
Southeast Asia Scoring being a different kind of card, and the correct
implementation prices all seven of its countries, four of which are not
Battlegrounds.

### Correction: urgency is already right; the VP function is the only wrong part

The maintainer: "urgency is same, VP calculation is special without
tiering. Oh, there are probably two terms, an urgency term and a rest of
game term (based on average/expected game length)? Something like that."

**Urgency already handles Southeast Asia correctly**, and the previous
section overstated the damage by implying otherwise.
`public_cards.scoring_schedule` returns `(0,)` for Southeast Asia Scoring
where every other card gets `(0, reshuffle)`:

```python
once = card == 'Southeast_Asia_Scoring'
...
schedule = (0,) if once else (0, reshuffle)
```

So the one-shot nature is already in the timing machinery. The error is
confined to what the previous section called the shape: the resulting
urgency is multiplied by a **tier** weight (`w.battleground` or
`w.control`) when Southeast Asia Scoring's award is flat. Urgency stays
as it is; only the VP function is wrong.

**And the two terms half-exist already.** `_scoring_weight_uncached` sums

1. the scheduled scorings, each discounted `w.scoring_discount ** turns`
   -- the *urgency* term, how soon and how often; and
2. `w.scoring_final * final_scoring_odds(obs)` -- the *rest of game* term,
   and it is already keyed on expected game length rather than flat:
   `FINAL_SCORING_ODDS` runs 6/27 at turn 1 to 6/6 at turn 10.

What is missing is that they are **added into one scalar and then
multiplied by a tier weight**, which is where the VP-function distinction
gets lost. Keeping them apart is the maintainer's point, and the
factorisation that follows makes Southeast Asia fall out rather than
needing a special case:

```
value(country) = SUM over expected future scorings of
                     P(that scoring happens) * VP_of(card, position, country)
```

`VP_of` is the tiered Presence/Domination/Control function for the six
region cards and the flat per-country award for Southeast Asia. Urgency
and rest-of-game are both inside `P`, where they belong, and the tier
weights stop being applied to something that has no tiers.

That is a better target than patching a Thailand constant: it removes a
special case instead of adding one, and it is the same restructuring the
region-model rewrite needs anyway.

### Win probability: the shape, and the ceiling

The answer to the open question of what win probability should *do*, which
was the one thing I said I should not decide alone.

**Direction: variance is worth more when you are behind.** The maintainer:
"a 75% to win is definitely worth less when you're winning, you want to
take tons of DEFCON / Europe Control shots when behind." So a high win
probability lowers the value of a risky line and a low one raises it. The
bot has no such term: it prices a risky line the same whether it is ten
ahead or ten behind, which means it declines the shots that are the only
way back from a losing position and takes ones it does not need.

**Ceiling: win probability tops out around 0.75 to 0.90**, at the start of
a turn before cards are drawn, *even when far ahead on the board*, because
you cannot force a win and the opponent can always take shots at you. And
it is **asymmetric: lower for the USSR**, "because USSR has to die more."

That ceiling is the most useful part of the answer and the easiest to get
wrong. **A fitted estimator will happily report 0.99 from a dominant board
and be wrong**, and an over-confident estimator inverts the whole term:
the bot would stop taking shots exactly when a human would judge the
position not yet safe. Any estimator has to be clipped, not just fitted.

The USSR asymmetry is plausible and mechanically motivated but **not yet
measured**. What is on hand is weak: over the 192-game hunt, `defcon_1`
endings split 8 USSR to 5 US, and three explicit "USSR is responsible"
lines appear across the session's logs. Thirteen events is not a result.
Worth measuring properly before the asymmetry is built in, since it is a
per-seat constant and those are exactly what the mirror gate cannot see.

### P(SEA scores) is ~0.95; the discount is in the payout, not the odds

The maintainer: "P(SEA scores) is at least .9, almost certain it's .95.
It's just E(Scoring) that's much lower."

Measured: **11 of the first 12 games, 92%**, run still going.

Which corrects the formula from two sections up. It was written as
`P(SEA scores) * 4 VP`, with the discount carried by P. P is nearly 1, so
that form would price Thailand's Southeast Asia contribution at almost its
full 4 VP swing. The discount belongs in the *payout*: whether you still
hold the country when it scores, what else you hold in the subregion, and
which turn it lands on.

**And that is not a constant to be supplied -- it is a position, which the
evaluator already computes.** So the right implementation adds no new
number at all:

```
Southeast Asia contribution = 0.95 * (Southeast Asia VP swing on this board)
```

with the swing read off the position exactly as the six tiered regions
already are. One measured constant near 1, and no per-country table.

### Europe Control is priced as a scoring, not a win -- and the U-shape is already there

Measuring what the next European Battleground is worth, by how many the
US already holds (seed 4002, turn 4):

| Already held | Next one is worth |
| ---: | ---: |
| **0 of 5** | **2.30 VP** |
| 1 of 5 | 0.95 VP |
| 2 of 5 | 1.05 VP |
| 3 of 5 | 0.90 VP |
| **4 of 5** | **2.24 VP** |

The maintainer, independently: "the 0th BG and 5th BG in Europe are the
most important countries on the map, unless you need to gamble on DEFCON
or are looking to force 20 VP before Europe scoring comes back."

**So the bot already has the right shape and the wrong magnitude.** The
U is there -- the first and the last are worth twice the middle -- which
is more than the region model deserves credit for, and it comes out of
the tier structure rather than from anything anyone tuned. What is wrong
is that the fifth one *wins the game* and is priced at 2.24 VP.

The arithmetic of why:

```
region_vp returns 100 for Europe Control
  x w.region 1.3  x urgency 1.752  /  vp_value 83.8   =   2.7 VP
```

**Which is why capping the constant, as the maintainer asked, is right but
cannot help on its own -- and alone makes it worse.** 100 was arbitrary
and 20 is the honest value at par (`20 - vp`, up to 40 from behind), so
the constant is now `EUROPE_CONTROL_VP = 20.0` and named. But at 20 the
same arithmetic gives 0.5 VP for winning the game, against 2.7 before.
The parity corpus reproduces every ranking unchanged after the switch,
which confirms the point: **no position in 547 ever reaches the branch.**

The defect is the routing, not the number. Europe Control is a *terminal
outcome* and it is priced as a very large *scoring*, so it is discounted
by `urgency` (how soon the region will score -- irrelevant to a win) and
by `w.region` (a scoring weight). It belongs on `game_value`'s scale,
where `LOSS` and the certain outcomes already live.

**A correction to withdraw.** Before measuring, this looked like the
region term being ~37x under-scaled, and that was wrong. A full Africa
swing pays 22 VP by the rules and moves the bot's board value by 9.1 VP:
the bot sees **41%**, not 3%. `country_value` and the margin terms carry
most of the weight, and the region term is one contributor among three.

### One source of truth for what winning is worth

The maintainer: "all of the 'win the game' constants should either be
static or based off win probability. I guess, ideally, it's better to
just have one win probability function. But I think it might be
practically better to have the VP constant. At the very least, the VP
constant should calibrate what the win probability is."

There are currently **four** of them and no two agree:

| Constant | Value | Where |
| --- | --- | --- |
| `LOSS` | −1,000,000 | the certain-outcome sentinel |
| `GAME_SWING_VP` | 40 | `game_value`, the whole VP track |
| `EUROPE_CONTROL_VP` | 20 | `region_vp`'s stand-in |
| the win-probability ceiling | 0.75–0.90 | not implemented |

They are supposed to be the same fact seen from different angles: what it
is worth to convert this position into a certain win. The directive is
that they be made consistent -- and that whichever is chosen as primary
calibrates the others, rather than each being tuned where it sits.

### VP are not linear, and two places are discontinuous

The maintainer: "the 20th VP is much, much more important than the 19th.
I guess the 20th VP, and the 6th and 7th VP in the Late War, are
discontinuously important. It's probably some kind of very sharp
exponential in early/mid war."

`vp_value` is **one price per VP per era** (`vp_early` 0.5, `vp_mid` 1.0,
`vp_late` 2.0), so the twentieth VP costs exactly what the first does.
Two discontinuities it cannot express:

- **The 20th ends the game.** Going +19 to +20 is winning; +18 to +19 is
  nothing. The auto-victory is a step, not a slope.
- **The 6th and 7th in the Late War are Wargames.** It ends the game and
  hands the opponent 6 VP, so at +6 you tie and at +7 you win. The
  seventh VP is worth the game and the sixth is worth a draw -- which is
  exactly the maintainer's earlier reading of Wargames as
  `(1 - win_pct) * game_value`, now placed on the VP curve rather than on
  the card.

And a convexity underneath both: being further ahead is worth more than
linearly, sharply so in the Early and Mid War. That is the same quantity
as win probability, which is what makes the previous section's directive
coherent -- a VP curve and a win-probability function are two
parameterisations of one thing, and calibrating either fixes both.

### A country's value is three terms, and a wipe destroys only one of them

The maintainer, on Egypt: "Egypt with Nasser/Sadat only has adjacency and
urgency value."

That is the resolution of the whole per-country thread, and it says the
adjustment table is the wrong *shape* rather than the wrong size. A flat
"Egypt −2 VP" reduces everything about the country in proportion. What
actually happens is that one of three components goes to zero and the
other two are untouched:

| Component | What it is | Wipe exposure does |
| --- | --- | --- |
| **Durable holding** | the Battleground's own tier value, kept over time | **destroyed** -- you cannot keep what a 1-Op card removes |
| **Adjacency** | the reach it gives: Egypt opens Libya, Sudan, Israel | **untouched** |
| **Urgency** | holding it *at the moment the region scores* | **untouched** -- a wipe before scoring costs nothing you had banked |

So Egypt is not a Battleground worth 2 VP. It is a Battleground worth ~0
to *invest* in and its ordinary value to *hold at a scoring*, which are
different decisions the bot currently cannot separate.

**And the bot already has all three as separate terms** -- `country_value`
for the holding, `access` for adjacency, and the region/urgency terms for
scoring. So the implementation is to discount the holding component by
exposure, not to subtract VP from the total. That is strictly easier than
the flat table and strictly more correct.

**Why Egypt specifically.** Mapping every cheap eviction onto the
Battlegrounds it reaches:

| Country | Against the US | Against the USSR |
| --- | --- | --- |
| **Egypt** | **Nasser (1)**, Muslim Revolution (4) | **Sadat (1)** |
| Iran | Iran-Iraq (2), Iranian Hostage (3), Muslim Rev (4) | Iran-Iraq (2) |
| Iraq | Iran-Iraq (2), Muslim Revolution (4) | Iran-Iraq (2) |
| India, Pakistan | Indo-Pakistani (2) | Indo-Pakistani (2) |
| West Germany | Blockade (1) | -- |
| UK | -- | The Iron Lady (3) |

**Egypt is the only Battleground on the map with a one-Op eviction
available against both sides.** Five are two-sided, and the other four are
two-Op. That is the whole explanation for why it alone loses its holding
value rather than merely being discounted -- and it is arithmetic from the
card list, not a judgement anyone had to supply.

It also explains the spread question from the section above. The
per-country spread (4.0 VP) being larger than the per-region spread (2.67)
is not an inconsistency: they measure different things, and the per-country
figure is large precisely because a handful of countries lose an entire
component of their value rather than a fraction of all of them.

### Wars have dice, and 1-Op cards have no exits

Two qualifiers from the maintainer that change the exposure table above.

**"And wars have dice."** Every war card is `win_from=4`, so the attacker
needs a 4+ on a d6: **50% before penalties**, and −1/6 for every country
adjacent to the target that the *defender* controls, plus the target
itself where the card counts it (Arab-Israeli does). Brush War is
`win_from=3`, so 67%.

So the war cards are not wipes. They are coin flips that the defender can
push below even by holding the neighbourhood -- which is a real strategic
difference, and the only member of the eviction class that responds to
defence at all. That splits the table in two:

| | Certain | Probabilistic |
| --- | --- | --- |
| Cards | Nasser, Sadat, Blockade, Truman, Muslim Revolution, Warsaw Pact, De Gaulle, Iranian Hostage, Iron Lady, Marine Barracks, Ortega | Korean, Arab-Israeli, Indo-Pakistani, Iran-Iraq (50%), Brush War (67%) |

And it isolates Egypt completely: of the five two-sided Battlegrounds,
India, Pakistan, Iran and Iraq are two-sided only through **war cards at
50%**. Egypt is the only Battleground on the map facing a **certain
one-Op eviction from both sides** -- Nasser against the US, Sadat against
the USSR. That is the whole reason it alone drops to adjacency and
urgency value.

**"Getting rid of 1-Op cards is like 10x harder than 2-Op cards."** It is
stronger than that: every exit is closed, not merely dearer.

| Exit | Minimum Ops |
| --- | ---: |
| Space race, boxes 1-4 | **2** |
| Space race, boxes 5-8 | 3 to 4 |
| Quagmire / Bear Trap discard | **2** (`core.py` `_payable_cards`) |
| Blockade / Latin American Debt Crisis payment | 3 |

**A 1-Op card cannot be spaced, cannot be thrown to a trap, and cannot
pay a discard clause.** The only way out is to play it, which fires the
event if it is the opponent's. This is the maintainer's very first
correction of the session -- "you generally can't space Lone Gunman" --
as a general rule rather than a fact about one card.

The fourteen cards with no exit:

| Side | Cards |
| --- | --- |
| USSR | **Lone Gunman**, Blockade, Nasser, Romanian Abdication, Allende |
| US | **CIA Created**, Truman Doctrine, Kitchen Debates, Panama Canal, OAS Founded, Sadat |
| Neutral | Captured Nazi Scientist, UN Intervention, Summit |

Forty cards sit at 2 Ops with every exit open. Two of the no-exit cards,
**Lone Gunman and CIA Created**, are on the maintainer's safe-window list,
and they are the two the planner was found scoring at 0.00 risk.

**And the exits are computed on the *modified* Ops** (`_effective_ops`,
FAQ 7.4), which cuts both ways: Containment or Brezhnev can lift a 1-Op
card to 2 and open every exit, while **Red Scare/Purge can strand a 2-Op
card at 1 and close them all**. Using an Ops modifier to trap an opponent's
card is a line the bot has no way to see.

### The complete list of exits, corrected

The maintainer, on the claim that a 1-Op card has no way out: "there is
Ask Not / Containment / Brezhnev? Anything else I'm missing?" -- and the
previous section was indeed incomplete. Three exits work regardless of a
card's Ops, and two modifiers move a card across the threshold.

**Exits that ignore Ops entirely:**

| Exit | Who | Reach |
| --- | --- | --- |
| **UN Intervention** | either side, holding it | Play the opponent's card for its Ops and the event does not fire. The clean exit, at any Ops value. Cannot be used on itself (`cid != un_intervention_id`). |
| **Ask Not What Your Country Can Do For You** | **US only** | Discard any number of hand cards and redraw. The event benefits the US whoever plays it, so the USSR playing it for Ops hands the US the discard -- it is not an exit the USSR can buy. |
| **Space Race box 6** (Eagle/Bear Has Landed) | its sole holder | Discards the **Held Card** before the next deal -- one card, once a turn, and only the card carried between turns, not anything in hand. Much narrower than "discard a held card" suggests. |

**Involuntary, but they do clear a trap:** Terrorism, Five Year Plan,
Grain Sales, Aldrich Ames and Missile Envy all remove cards from a hand
without playing them. An opponent attacking your hand may take the 1-Op
card you could not get rid of, which is a real reason the hand-attack
terms should not be priced as pure harm.

**Exits that need 2+ Ops, and so are closed to a 1-Op card:** the space
race (boxes 1-4 need 2, rising to 4), the Quagmire / Bear Trap discard
(`>= 2`), and the Blockade / Latin American Debt Crisis payment (`>= 3`).

**And the threshold moves.** Exits test the *modified* Ops (FAQ 7.4), so:

- **Containment** (+1 to all US Operations) and **Brezhnev Doctrine** (+1
  to all USSR) lift a 1-Op card to 2 and **open every exit** for a turn.
  That makes them defensive cards as well as offensive ones, which is not
  how either is usually described.
- **Red Scare/Purge** (−1 to the opponent, **minimum 1**) pushes a 2-Op
  card down to 1 and **closes them all**. The minimum means it cannot
  strand anything below 1, so its trapping power is exactly the 2-Op
  cards.

So the corrected statement is not "a 1-Op card cannot be shed" but: **a
1-Op card can only be shed by UN Intervention, by Ask Not if you are the
US, or by luck** -- and Containment or Brezhnev can lift it out of the
trap for a turn. Fourteen cards sit at 1 Op; Lone Gunman and CIA Created
are on the safe-window list and are two of the three the planner scores
at 0.00 risk.

One consequence for the planner, which already models `payable` at 2+:
**it should also model UN Intervention and Ask Not as exits**, or it will
keep reporting a trapped hand that a held UN Intervention makes safe.

### The yardstick is a coup: why the Battleground scale cannot be tuned

Trying to raise the Battleground scale to the maintainer's 4 VP produced
a result that killed the plan and then explained itself.

**Scaling `battleground` does nothing.** From 5.0 to 40.0, an eightfold
increase, the measured Battleground swing moves from 1.08 VP to 1.10.
The bot has no absolute scale: board value is denominated in Ops,
`vp_value` is `vp_era * ops_value(1)`, and `ops_value` is itself computed
from board terms -- so scaling the board scales the yardstick with it and
every ratio survives untouched.

**Only `vp_mid` moves it**, and only by redenominating: 1.0 to 0.25 puts
the swing at 4.44 VP. But the era rates are the maintainer's own rule and
the best-supported numbers in the project, so bending them to fix a
Battleground is the wrong repair.

**The actual cause is what sets the yardstick.** `ops_value` is the max
of the best placement and the best Coup, and the Coup wins at every Ops
level:

| | 1 Op | 4 Ops |
| --- | ---: | ---: |
| best placement | 0.24 VP | 1.15 VP |
| **best Coup** | **1.11 VP** (Nigeria) | **1.78 VP** (Zaire) |
| `ops_value` | 1.00 | 1.78 |

So `vp_value` -- the price of a VP, and therefore the denominator of
**every** VP figure in this project, including every measurement in these
notes -- is anchored to **the single most efficient Coup available on the
board**. At turn 4 that is Nigeria, stability 1, worth 4.6x the best
placement.

Two consequences.

**The "Battleground is 4x low" finding was measured against a coup.** The
swing reads 1.08 VP because a VP is priced at the best coup; against what
a *placement* buys it would read about 3.5, which is the maintainer's 4.
The Battleground weight may not be wrong at all. What is wrong is that
two different exchange rates are in use and nothing says which.

**And the rate is unstable.** One cheap Coup target anywhere sets the
price of an Op everywhere, for every decision. It jumps when DEFCON
changes, when a 1-stability country fills up, when a Coup prohibition
turns on. Every VP-denominated comparison moves with it -- including
`military_credit`, the China charge, `game_value`, and the sentinel
bounds.

Whether pricing an Op at its best use is right is a real question and not
obviously wrong. What is not defensible is that it is undocumented, that
the region calibration was being fitted against it without anyone
noticing, and that half the constants in `models/provenance.json` are
denominated in a unit that moves when Nigeria fills up.

**This supersedes the plan to rewrite the region weights.** The
calibration the maintainer supplied is sound; the yardstick it would have
been fitted against is not. Fixing the yardstick comes first.

### Correction: Aldrich Ames is not an exit, because the opponent chooses

The maintainer: "you can Aldrich Ames yourself as US as well." True --
the event fires for the USSR whoever plays the card, so a US player
spending it for Ops is choosing to be attacked. But that makes it the
opposite of an exit, and the previous section listed it wrongly.

The involuntary removals split by **who picks**:

| Card | Who picks | Can it clear a trapped 1-Op card? |
| --- | --- | --- |
| Terrorism | random | **yes** |
| Five Year Plan | random | **yes** |
| Grain Sales to Soviets | random | **yes** |
| **Aldrich Ames Remix** | the opponent | **no** -- they take your best |
| **Missile Envy** | highest Ops | **no** -- a 1-Op card is never the highest |

So only the random ones are exits, and the two chosen ones are
adversarial by construction: Aldrich Ames removes the card you least want
to lose, and Missile Envy removes your biggest. Listing all five together
was wrong.

### Correction: the three prices are functions, and the bug is the fixed multipliers

The maintainer: "ops_value, vp_value and game_value (which is basically
win probability) are not fixed in this game, they are related but change
over turns / position / VP difference."

Which corrects the plan in the section above. It proposed finding a
*stable anchor* for `game_value` so that `vp_value` could be repriced
without cheapening defeat. Wrong shape: none of the three should be
stable. Each is a different function of the position, and the defect is
that the code relates them by **constant multipliers**, which forces all
three to move together when they should move independently.

What the code does today:

```
vp_value(obs)   = vp_era             * ops_value(obs, 1)
game_value(obs) = GAME_SWING_VP (40) * vp_value(obs)
```

Two fixed multipliers in a chain. So a cheap Coup appearing in Nigeria
raises `ops_value`, which raises the price of a VP, which raises what
losing the game is worth -- three unrelated facts moved by one board
change. And it is why the earlier attempt to reprice a VP failed: the
gate saw the bot stop avoiding nuclear war, because `game_value` was
chained to it.

What each should actually depend on:

| Price | What it is | Varies with |
| --- | --- | --- |
| `ops_value(n)` | what n Ops buy **here** | the board -- correctly, since it is the best use available |
| `vp_value` | what a VP is worth **here** | the turn (era) **and the VP position**: the 20th VP wins, the 19th does not, and the 6th and 7th in the Late War are Wargames |
| `game_value` | what is still at stake | the VP difference and the win probability -- `20 - vp` upward and `20 + vp` down, and nothing at all once the game is decided |

So the fix is three functions, not one anchor:

1. **`game_value` stops being `40 * vp_value`** and becomes a function of
   the VP position directly. This is the step that makes the rest safe,
   because it is what chained defeat to the coup price.
2. **`vp_value` gains the VP-position term** -- the convexity and the two
   discontinuities -- instead of being one flat rate per era.
3. **`ops_value` is left alone.** Pricing an Op at its best available use
   is right; it only looked wrong because two other things were chained
   to it.

`stakes.py` is what makes (1) expressible: `AUTO_VICTORY_VP` is a stake,
not a price, and `value_of_win_probability` already maps a probability
onto the same scale. The maintainer's "ideally it's better to just have
one win probability function" is the end state -- `game_value` *is* win
probability times what is left to play for.

### The win-probability fit: the maintainer's shape wins, and it saturates

936 rows from 60 self-played games, one per turn start per seat, labelled
with the eventual result (`scripts/collect_winprob.py`). The maintainer's
proposed shape was "VP difference plus board VP position times a
turn-based factor".

**The data has signal, and it is not just banked VP.** Win rate by banked
VP runs smoothly from 0.11 at −12 to 0.93 at +12. But among *near-level*
positions (|VP| ≤ 3, n=410) the board splits them 0.37 / 0.48 / 0.73 —
so board value predicts independently, which is what makes the term worth
having at all.

**And the proposed shape beats both the simpler and the more general
alternative:**

| Model | logloss | accuracy |
| --- | ---: | ---: |
| vp only | 0.5844 | 0.663 |
| vp + board | 0.5204 | 0.721 |
| **vp + board x turn/10** | **0.4976** | **0.746** |
| vp + board + turn | 0.5195 | 0.728 |

`logit(p) = -0.077 + 0.158*vp + 0.510*(board_vp * turn/10)`

Turn as a *multiplier on the board term* beats turn as its own feature,
which is the non-obvious part and is exactly what was specified: the
board matters more as the game shortens, rather than the turn mattering
on its own.

**The ceiling warning is confirmed, empirically and on the first try.**
The most confident prediction this model makes on its own training data
is **0.999**. The maintainer's ceiling is 0.75 to 0.90 -- "you cannot
force a win" -- and a term fed 0.999 inverts: the bot would stop taking
DEFCON and Europe Control shots exactly where a strong player judges the
position not yet safe. `stakes.clipped_win_probability` was written
before this fit existed, on their word alone, and it is the only thing
between the fitted model and that failure.

Caveats worth keeping with the number. These are 60 bot-versus-bot games,
so the label is "did this bot beat this bot", not "would a strong player
win"; the fit is on training data with no held-out split; and the
`board_vp` feature is measured against `vp_value`, which the section
above establishes is anchored to the best Coup on the board and therefore
moves. All three push the same way: the coefficients are a starting
shape, not a calibration.

### The USSR asymmetry is still not established, and the row counts lied

Tested against the win-probability data, because it was the one part of
the ceiling the maintainer gave that had no measurement behind it.

The row-level split looks decisive: **US 0.579, USSR 0.421** over 936
rows, and at near-level positions 0.718 against 0.390. It is an artifact.
Rows are one per turn per seat and every row of a game carries that
game's outcome, so they are perfectly correlated within a game and the
count weights by game length rather than by evidence.

**Game-level: the US seat won 33 of 60, 55%, two-sided p = 0.52.**
Nothing. Resolving a genuine 58/42 split at p < 0.05 needs roughly 150
games. So the asymmetry stays out of `stakes.py`, where
`WIN_PROBABILITY_CEILING` remains symmetric, and stays listed as
unmeasured in `models/provenance.json`.

This is the third time this session that a promising number has come
from counting correlated observations as if they were independent -- the
first was "96% pool efficiency" from summing wall-clock across workers,
the second the turn-10 worst card at −8.55 from a ten-sample mean with
one −78 outlier. Same shape each time: **the denominator was not what it
looked like.**

What the data *does* support is the ceiling's magnitude. The best
populated buckets top out at 0.90 for the US and 0.82 for the USSR,
against the maintainer's stated 0.75 to 0.90 -- consistent, with the same
correlation caveat attached.

### The same-Ops tie-break, specified

The maintainer, on Decision 8, where Arms Race and NORAD score 35.40 to
the bit:

> I would rather play NORAD because you can event Arms Race for the event
> later... Ops value is the same, but you hold the card with the highest
> **remaining event value** during tiebreaks. It's really expected over
> end of turn, but calculating that is probably not a good use of
> resources; I fully expect the heuristic to be good enough.

So the rule is: **among plays of equal Ops, spend the card whose event
you least want to keep, and hold the one with the highest remaining event
value.**

That is not quite what the earlier note in these notes said. It framed
the tie-break as "burn the least valuable event", which invites using
`event_value` — the *immediate board effect* of firing it now. The right
quantity is the **option value of playing it as an event later**, which
is a different thing:

- **NORAD**'s event is a conditional flag (one Influence when DEFCON
  falls to 2, if the US holds Canada). Near-worthless to keep.
- **Arms Race**'s event is real VP off the Military Ops comparison, and
  it is worth keeping for a turn when the comparison is favourable.

Both are 3-Ops US cards in a US hand, so neither fires when played for
Ops and the Ops value is identical. The whole difference is which one you
would rather still be holding.

**And the maintainer has pre-empted the obvious over-engineering.** The
exact quantity is the expectation over the rest of the turn — will a
better moment for this event arrive before the hand runs out — and they
judge that not worth computing, expecting the plain heuristic to
suffice. Worth recording, because the hand planner exists and it would be
easy to route this through it for no gain.

This is the third thing the planner might have owned and should not:
China's play charge and the safe windows genuinely need lookahead, and
this does not.

**Implementation.** `_score_card_play` returns the same number for both,
so the tie is broken by the engine's option order. The fix is a
tie-break key: among plays whose value ties, prefer the lower
`event_value` of the card *as a future play from our own seat*. The 26
indifference positions in `docs/POSITION_PACK.md` Part C are the test
set, 19 of them card plays.

### Measured: the bot prefers an inert point in a 40-Ops war to an empty Battleground

The maintainer: "the bot doesn't fill empty BGs enough and also gets into
BG ops wars... assume the bot is doing something wrong if there are more
than 20 Ops in a country outside Europe/Thailand. Maybe there needs to be
a bonus for uncontrolled countries? Or will a single Ops penalty for
breaking handle that?"

Confirmed, and the mechanism is narrower than "ops wars".

**Every one of the eight most over-invested countries in the corpus is
stability 2:**

| Country | Influence | Stability |
| --- | --- | ---: |
| **Thailand** | **US 21, SU 19 — 40 points** | 2 |
| Algeria | US 13, SU 11 | 2 |
| Mexico | US 9, SU 11 | 2 |
| Egypt | US 9, SU 8 | 2 |
| Brazil | US 9, SU 8 | 2 |
| Pakistan | US 9, SU 7 | 2 |

At seed 4001 turn 9, with Thailand at US 21 / SU 19 and the USSR to move,
here is what the greedy placement ranks, by value per Op — which is what
it actually chooses on:

```
Thailand   BG  0.213 VP/Op   buys 1 pt at 2 Ops   (US 21 SU 19)   <- rank 1 of 69
Pakistan   BG  0.213 VP/Op   buys 1 pt at 2 Ops   (US  9 SU  7)
India      BG  0.197 VP/Op   buys 1 pt at 2 Ops   (US  3 SU  0)
Chile      BG  0.164 VP/Op   buys 3 pts at 1 Op   (US  0 SU  0)   <- empty
Saudi      BG  0.147 VP/Op   buys 3 pts at 1 Op   (US  0 SU  0)   <- empty
```

**The top-rated use of an Operation on the whole board is one point into
Thailand** — moving the margin from US+2 to US+1. It flips no control,
buys no reserve, crosses no tier, and the US restores it for two Ops. An
empty Battleground it could take outright ranks fourth.

**So the answer to the maintainer's question is: neither fix, quite.**

A bonus for uncontrolled countries would help by accident. A flat penalty
for breaking would help by accident. The actual defect is that
`progress` pays for movement toward a control that is not going to
arrive: at stability 2 the margin is always small relative to the
threshold, so every point looks like meaningful progress no matter how
many are already there. Nothing in the term knows that the fortieth point
in a country is not like the first.

And the engine is already charging correctly — the USSR pays **2 Ops per
point** in a US-controlled country, so Thailand costs double and *still*
wins. The economic disincentive exists and is not enough, because the
valuation overrates what it buys.

**The right term is the maintainer's own break-war observation**: the
value of a break should be discounted by the chance it survives the
opponent's reply. At US 21 / SU 19 a one-point break has essentially no
chance — the defender restores the margin for two Ops, and they will,
because the same valuation that made the bot spend there makes them
spend back. That is the feedback loop that produces forty points in a
stability-2 country, and it is why "the defender should win a huge
percentage of break wars" is the fix rather than a bonus anywhere else.

### Why the bot buys exactly one point: `_investment` keeps the smallest tie

The full placement ranking at seed 4001 T9, USSR to move, by value per Op
-- which is what the greedy chooses on:

```
 1 Thailand  0.213  1 pt @2  THEIRS  US 21 SU 19   needs 2 more to flip
 2 Pakistan  0.213  1 pt @2  THEIRS  US  9 SU  7   needs 4 more
 3 India     0.197  1 pt @2  THEIRS  US  3 SU  0   needs 6 more
 4 Japan     0.176  1 pt @2  THEIRS  US  4 SU  0   needs 8 more
 5 Cuba      0.176  1 pt @2  THEIRS  US  3 SU  0   needs 6 more
 6 Chile     0.164  3 pts@1  EMPTY                 takes it outright
 7 Saudi     0.147  3 pts@1  EMPTY                 takes it outright
```

The top five are **one-point buys into opponent Battlegrounds**, and one
of them puts a single point into Japan where the USSR needs eight. The
maintainer's rule is "4-Op breaks into stability-2 countries are a thing,
but you have to spend all your Ops, because otherwise you make it too
easy for the opponent". The bot spends the minimum, which is the one
amount that is strictly worse than not breaking at all.

**The mechanism is in `_investment`:**

```python
gain = self.delta(obs, cid, own=points) / spent    # value PER OP
if gain > best[0]:                                  # strict: ties keep the FIRST
    best = (gain, points)
```

It maximises value per Op, and `progress_curve` is 1.0, so progress
toward control is **linear**: `delta` and `spent` both grow linearly and
the ratio is flat across point counts. A flat rate plus a strict `>`
means **the smallest investment wins every tie.**

In an *empty* country the rate is not flat -- control is a step, so the
rate jumps at the threshold and the greedy buys all three. In a
*contested* one there is no reachable step, the rate is flat, and it buys
one. So the bot fully invests exactly where investment is cheap and
safe, and token-invests exactly where the maintainer says you must commit
or stay out. Precisely inverted.

**Two candidate fixes, and they are not equivalent.**

1. `>=` instead of `>`, keeping the *largest* point count on a tie. One
   character, and it makes flat-rate investments go all-in rather than
   all-out. Cheap to gate, and it does nothing to the empty-country case
   where the rate is genuinely peaked.
2. The maintainer's **half-action-round forward search**: value a
   placement by the position after the opponent's cheapest reply. The
   inert Thailand point then evaluates at ~0 without any new term,
   because the reply restores the margin for two Ops. This also gets the
   all-or-nothing structure for free -- a full break survives the reply
   and a partial one does not.

(1) is a patch that happens to point the right way; (2) is the actual
model. Worth trying (1) first only because it is a one-line gate.

**And two legitimate reasons to break that neither fix should destroy**,
both from the maintainer: breaking Middle East countries as the USSR to
set up Muslim Revolution, and breaking South America to set up Latin
American Debt Crisis (rarer -- Late War, and the discard option). Those
are *instrumental* breaks whose value is in a card in hand, not in the
board. A forward search sees them only if the reply model knows the card
is coming, which it does not.

### Correction: those points are not inert, they are cheapest-possible breaks

The section above is wrong in its central claim and the conclusion it
drew from it. It said the bot's top-ranked placements were "inert" points
that "flip no control". **They all flip control**, and checking takes one
line:

| Country | US | SU | Stability | Control now | After +1 USSR |
| --- | ---: | ---: | ---: | --- | --- |
| Thailand | 21 | 19 | 2 | US | **nobody** |
| Pakistan | 9 | 7 | 2 | US | **nobody** |
| India | 3 | 0 | 3 | US | **nobody** |
| Japan | 4 | 0 | 4 | US | **nobody** |
| Cuba | 3 | 0 | 3 | US | **nobody** |

"One point into Japan where the USSR needs eight" was the error: eight is
what *control* costs, one is what *breaking* costs. The bot is finding
the cheapest break available, every time, and ranking it first. That is
locally correct, and `_investment` returning one point is correct too --
the rate is concave because the first point does all the work. The
proposed `>` to `>=` fix is a no-op and was reverted; the rate is never
flat.

**And the real economics are exact, which is better than the story it
replaces.** Placing into an opponent-*controlled* country costs 2 Ops per
point. Once broken, nobody controls it, so *restoring* costs 1 Op per
point. Break Japan for 2 Ops and the US puts it back for 1.

> **A break that does not also take control loses the exchange two to
> one.**

That is the maintainer's "you have to spend all your Ops, because
otherwise you make it too easy for the opponent", as arithmetic rather
than as judgement, and it is why the defender wins break wars. It also
explains the stability-2 concentration: those are the countries where
both sides can keep re-breaking cheaply, so the 2:1 exchange runs over
and over and forty points accumulate.

**The fix is unchanged and now better motivated.** No discount term is
needed and none would be principled -- the bot's valuation of the break
is right, and what it is missing is the reply. One ply of
opponent-response makes the 2:1 exchange visible, and "commit or stay
out" falls out of it: a break big enough that restoring costs the
opponent more than it cost you is exactly a break that survives one ply.

### Four answers, two of which are predictions about the forward search

**The Battleground table, closed.** Egypt −1.5 (was −2) and Cuba −1.0
(was −1.5, and possibly −0.5, since adjacency is worth about +1 and
partly offsets Fidel and Ortega). The 2-3 VP spread bounds the **region
means** -- 2.67, inside it -- not the whole map, so the per-country
figures are free to run wider. Europe and Thailand tied at 6.0 is fine.
And the 4.0 floor is "probably a touch low": it gives 0.81 VP per Op
where Europe and South America sit exactly on the fitted 1.00, so about
5.0 would put ordinary ground on the same line.

**Coup size is hand-planner work.** The bot may be choosing the right
target and the wrong amount -- one Op where two or three buys the chance
of the bigger result -- and the maintainer's instruction is not to fix it
on its own. Filed against the planner with China's play charge and the
safe windows.

**OAS into Chile: "empty battleground, zero access. One ply look ahead
makes this obvious."** That is a prediction about code written tonight,
and a free test of it: the forward search should reach the maintainer's
answer on Decision 8 without being told. If it does not, the search is
weaker than the argument for it.

**Region readiness: "when you've been behind and then get to even, or
you've been even and have gone ahead."** Which is a *trajectory*
condition, not a state one -- it compares the region now against the
region earlier, and nothing in the bot remembers earlier. That explains
why `EXPERT_ASKS` item 3 has resisted an answer for so long: every
attempt has looked for a rule about the present board. The real home is
the hand planner; one ply should help.

**And the 2x risk premium has two candidate explanations**, per the
maintainer and astra: nested terms double-counting, or the 20th VP
mattering most -- the auto-victory discontinuity. The second is
testable and links the two halves of the unchaining plan: **if the
premium is really the VP discontinuity in disguise, then giving
`vp_value` its convexity should make the premium unnecessary**, and
`game_value` at its honest arithmetic value should then survive the gate
it failed twice. That is a sharp prediction and worth running as the
test of step 2.

### The scale invariance, stated properly -- and what it makes unbuildable

Astra's algebra, which is not a model of the ranking but literally
`safety_key`:

```
V_vp   = e * O                 vp_value  = era multiplier x best one-Op value
V_game = 40 * e * O            game_value = GAME_SWING_VP x vp_value
Q      = (1-r) * S - r * (40 e O)        the ranking key, policy.py:665
```

Divide by `O > 0`, which preserves order:

```
Q/O = (1-r)(S/O) - 40 e r
```

**So any change that scales both the action value `S` and the one-Op
reference `O` leaves the ranking alone.** Not a hypothesis: raising
`battleground` from 5.0 to 40.0, an eightfold change, moved the measured
Battleground swing from 1.08 VP to 1.10.

Three consequences, and the third is the one that matters.

**Only three things move the risk/value trade.** `e` (the era
multiplier), the constant 40, and `r` (the residual loss probability).
They survive the division; everything in the board weights does not.
That is why `vp_mid` was the *only* lever that moved the swing when I
swept for one, and it explains a run of null results tonight rather than
leaving them as coincidences.

**It predicts the `ops_value` change fails, and why.** Pricing an Op on
placement instead of the best coup lowers `O` roughly fourfold without
touching `S`, so `S/O` quadruples and value dominates risk four times
more. More risk-taking, more nuclear losses -- which is exactly how the
historical attempt failed (0.434, 13 nuclear losses) and how gate B
failed tonight (0.464, 21). Twice for the same algebraic reason.

**And it means the maintainer's turn-4 calibration is currently
unbuildable.** Its *scale* half -- an ordinary Battleground swinging 4 VP
where the bot measures 1 -- is expressed entirely in board weights, and
board weights cancel. There is no setting of `battleground` that
produces it. I spent a stretch tonight preparing to fit those numbers
without noticing that the fit could not take.

The relative half is not equally hopeless. A weight change is inert *to
the extent it moves the best available option*, so a region-specific
change (Europe up against Asia) shifts `O` far less than a global one
and should survive partially. That is testable and worth testing before
anyone assumes either way.

**Which reorders everything.** The dependency runs:

1. decouple `game_value` from `ops_value`, without the asymmetry that
   lost gate D on strength;
2. then board weights stop cancelling and the region calibration becomes
   implementable at all;
3. then `ops_value` on placement can be gated for its own merits rather
   than failing on a coupling.

And the maintainer's "20th VP" hypothesis is load-bearing for step 1: if
the 2x risk premium is really the auto-victory discontinuity, a convex
`vp_value` supplies it and `game_value` can stop being a flat multiple
of anything. Three changes that have each failed alone may only work
together.

### Price Ops in VP, not VP in Ops -- the fix the invariance points at

The maintainer: "maybe ops value needs to be calculated by VP... that's
actually how most players think about it."

That inverts the dependency, and it is what breaks the invariance rather
than working around it.

**Today, VP is priced from the board.** `vp_value = e * ops_value(1)`,
and `ops_value` is the best action the board offers. So the unit of
account is "what an Op buys here", which is itself a board quantity --
there is no absolute anchor anywhere in the system, and
`game_value = 40 * e * ops_value(1)` inherits that. Everything floats
together, which is precisely why `Q/O` eliminates the board weights.

**Proposed: VP is the anchor and Ops are priced in it.** Board terms
are denominated in VP directly; `ops_value(n)` becomes "the VP that n
Operations buy on this board", a derived quantity rather than the unit.
`game_value` becomes a number of VP -- 40, or `20 - vp` -- that does not
reference the board at all.

**The invariance breaks, which is the point.** With `V_game = G` fixed
in VP rather than `40eO`:

```
Q/O = (1-r)(S/O) - r * G/O
```

Scaling every board weight by `k` scales `S` and `O` together, so `S/O`
holds -- but `G/O` falls by `k`. The risk term shrinks as the board
grows. **Board weights stop cancelling**, which is exactly what the
turn-4 calibration needs in order to be expressible at all.

**Two things may fall out for free.**

The **era rates** (`vp_early` 0.5, `vp_mid` 1.0, `vp_late` 2.0) exist to
convert between the two units. If board value is already VP, an Op is
worth more early because there is more to take, not because a constant
says so -- the rate becomes emergent. Worth checking against the
measured 1.76 Ops per VP before assuming it.

And the **coup anchor** stops mattering as a yardstick. A cheap Nigeria
coup would still be the best available Op, correctly, but it would no
longer set the price of a VP for every other decision in the position.
The thing that made the yardstick move goes away rather than being
tuned around.

**Cost, honestly.** Every board weight is currently denominated in Ops
and would need re-expressing -- which is what the maintainer's turn-4
table supplies, so the recalibration and the re-denomination are one
job rather than two. The parity corpus moves wholesale. And the
documented `coup -> vp_value -> ops_value -> coup` cycle disappears,
which is a simplification but invalidates the reasoning in
`tests/test_order_independence.py` that currently justifies fixing the
VP price once per decision.

This supersedes the three-step order in the section above. It is not a
bigger change than those three together; it is the same change, done at
the root instead of three times at the branches.

### Correction: the break exchange is n : n-1, not 2:1

The 2:1 figure recorded above is true only of the *minimum* break, and
stating it as the general rule got the maintainer's own advice backwards.

The doubled rate for placing into an opponent-controlled country stops
the moment control breaks -- which the **first** point does. Every point
after is single rate. So the 2x toll is paid once. Measured through the
engine against a defended stability-2 country (US 2, SU 0):

| Ops spent | points bought | end state | repair Ops | ratio |
| ---: | ---: | --- | ---: | --- |
| 2 | 1 | US 2 SU 1 | 1 | 2:1 |
| 3 | 2 | US 2 SU 2 | 2 | 3:2 |
| 4 | 3 | US 2 SU 3 | 3 | **4:3** |
| 5 | 4 | US 2 SU 4 | taken | -- |

**Breaking with n Ops costs the defender n-1 to repair.** The penalty is
one Op whatever the size, so the relative loss shrinks the more you
commit. A four-Op break is 4:3, near enough fair, and the maintainer
calls it "the effective way of breaking, and the best way to break
control in stability 2 countries with no overprotection."

So "spend all your Ops" is not a warning that partial breaks get undone
-- they all get undone at these sizes. It is that **the rate improves
with commitment**, because the toll is fixed and the gain is not. My
earlier framing had the mechanism wrong while happening to reach the
same advice.

Two riders, both the maintainer's. Five Ops takes the country but only
to *bare* control, which a single point breaks again -- security needs a
sixth. And over-protection is a Mid and Late War move: on turns 1-4
neither side can spare the Op.

`tests/test_ops_wars.py` pins all of it through the engine rather than
through `points * influence_cost`, which is exactly the arithmetic the
first version of that module got wrong.

**And this is the case for the forward search rather than against it.**
The maintainer: "the weighted look ahead should handle most of this for
free." It should -- a one-ply reply prices a 3-point break against the
3-Op answer it actually invites, where a fixed discount would have to
encode the whole n : n-1 table by hand.

### The poke count: the forward search does not yet work in play

The maintainer's test, and a far sharper instrument than the gate or the
control percentage: **how often does the bot break a Battleground with
the minimum two-Op placement?** Their expectation is about once a game.

Measured over 8 games:

| | search off | search on |
| --- | ---: | ---: |
| Battleground breaks per game | 24.50 | 24.12 |
| **...minimum 2-Op pokes** | **13.75** | **13.25** |
| ...committed, 3+ points | 1.62 | 0.50 |

**Fourteen times the expected rate, and the forward search barely moves
it.** Fifty-six per cent of every break the bot makes is the minimum
poke, which the `n : n-1` table says is its worst available version --
2 Ops spent, 1 Op to undo.

That is a much better measurement than either of the ones I reached for
first. The gate says 0.488 +/- 0.035, which is "not a measurable
regression". Turn-8 control says 78% to 82%, on populations of different
size. The poke count says 13.75 to 13.25, which is **nothing**, and says
it from 8 games.

**And the mechanism is not broken, which is the puzzling part.** On a
clean fixture -- Italy at US 2 / SU 0, the USSR placing one point -- the
reply discounts the gain by **70.7%**, from 2.99 VP to 0.88. It works
exactly as designed there.

In real games it fires on **7.2%** of calls and discounts **11.2%** when
it fires. So the gap is not that the discount is too small where it
applies; it is that it applies almost nowhere. The guard is "control
changes hands", and in play the overwhelming majority of candidate
placements do not change control -- but the *chosen* ones evidently
still are pokes, which means the pokes being chosen are somehow not the
ones being discounted.

Unresolved, and I would rather say so than guess again: three
explanations have suggested themselves tonight and two were wrong, so
the next step is to instrument which placements are actually chosen and
whether each was discounted, rather than reason about it.

**The instrument is the lasting result here.** A behavioural count with
a maintainer-supplied expectation -- "about one a game" -- caught in 8
games what a 96-seed gate and a 16-game control sweep both missed. It
belongs in the suite.

### The rule: twice means a test

The maintainer, after the stale-base inversion: "if you make a mistake
more than once, gate that with a test. That's just a good rule."

Adopted, and written into `CLAUDE.md` above the list of recurring
defects, because that list is the argument for it. Eight shapes are
recorded there; six recurred. The ones that stopped recurring are the
ones with a test beside them -- the sentinel escapes stopped after
`Certain` refused arithmetic, the scale errors stopped after
`test_scale_discipline.py`, the stale evaluator memos stopped after the
terms were made pure.

The stale-base inversion is the seventh occurrence of "a cached value
keyed on less state than it reads", and it was written by the same hand
that had documented the other six a few hours earlier. Which is the
whole case: knowing the rule is not the same as being unable to break
it. `tests/test_base_cache_discipline.py` now reconstructs the defect --
stubs `_invalidate_base` to a no-op, runs a real ranking, and requires
the checker to object.

Worth noting what made it catchable at all. The guard rests on
`Position.digest`, which was built earlier tonight for a *performance*
reason, measured as not worth it, and kept only because it made "the
board has not moved" checkable rather than merely commented. That is
exactly the use it was kept for, three hours later.

One thing the episode says about testing more generally: every unit test
of `_after_reply` asked what a value *was*, and the bug was in the
*sign of a difference*. `test_the_forward_search_discounts_a_break_rather
_than_rewarding_it` asserts the direction instead, and would have caught
it where none of the value tests could.

## 2026-09-11 — Breaks by Operations spent: the maintainer's 4 > 3 > 2, measured

The maintainer, refining the poke instrument: count breaks by the Ops
they cost, not the points they buy, and expect **4-Op breaks to be more
common than 3-Op than 2-Op**. The prediction is not intuition, it is the
rate structure. Read off the engine against bare control of a
stability-2 country:

| Ops spent | points | position left | their repair | exchange |
| --- | --- | --- | --- | --- |
| 2 | 1 | 1-2 | 1 Op | 2.00 : 1 |
| 3 | 2 | 2-2 | 2 Ops | 1.50 : 1 |
| 4 | 3 | 3-2 | 3 Ops | 1.33 : 1 |
| 5 | 4 | 4-2 | takes Control | 1.00 : 1 |

The first point costs double and the rest cost single, so every Op past
the break improves the trade. And against overprotection, confirming the
maintainer's own rule: +1 needs **4 Ops** to break (4.00 : 1), +2 needs
six. Odd budgets strand an Op there -- 3 Ops buys one point at cost two
and cannot afford a second.

### Measured, 24 games a side

| Ops on the break | search off | search on |
| --- | --- | --- |
| 2 | 301 (55%) | 4 (3%) |
| 3 | 206 (38%) | 121 (86%) |
| 4 | 25 (4.6%) | 4 (2.8%) |
| 5 | 14 (2.6%) | 12 (8.5%) |
| total | 546 (22.8/game) | 141 (5.9/game) |

Not the maintainer's ordering: 3 dominates at 86%. Two findings fall out.

**The bot never attacks overprotection.** Zero of 141 spends faced more
than bare control, so it never takes the 4:1 trade and never strands an
Op. That part is already right and needs nothing.

**The forward search suppresses 4-Op breaks harder than 3-Op ones**, 84%
against 41%, which is backwards -- the 4-Op break is the better trade.
Only the 5-Op breaks, which take Control outright and cannot be answered,
come through untouched (-14%).

### Where it actually comes from, after two wrong answers

**Wrong answer one: the deck.** Only 13 of 103 non-scoring cards are 4
Ops against 36 at 3, so 4 > 3 is unreachable by spending policy alone --
it would need the bot to *reserve* big cards for breaks. True, and not
the explanation: at the deck ratio one would still expect ~44 four-Op
breaks, not 16.

**Wrong answer two: consolidation is unpriced.** `_after_reply` returns
early when control does not change, so the point that takes 2-2 to 3-2
gets no reply discount at all -- and it raises their repair from 2 Ops to
3. That looked like the bug. It is not: `country_value` already prices
margin through the `progress` ramp, so that point is worth 21.76 raw at
cost 1, against the break's 40.69 at cost 2 *minus* a 30.65 discount.
Per Op the consolidating point rates **21.76 to the break's 5.02**. The
model is not underpaying for commitment.

### The real one: the budget cross-tab

| card's Ops | breaks | spent 2 | spent 3 | spent 4 | spent 5 |
| --- | --- | --- | --- | --- | --- |
| 3 | 78 | 2 | **76 (97%)** | -- | -- |
| 4 | 63 | 2 | **45 (71%)** | 4 | 12 |

Given a 3-Op card the bot commits the whole card 97% of the time. Given
a 4-Op card it spends 3 on the break and sends the fourth Op elsewhere
71% of the time. A trace confirms the mechanism and is starker: on an
opening-ish board with four Ops and a breakable Brazil, **all four go to
Angola, Panama and Egypt and none to the break**, with the search on or
off. Cheap uncontested points at 1 Op beat a contested point at 2 on the
per-Op criterion, so the bot breaks only once the cheap ground is gone
and the break budget is whatever is left over.

So "3-Op break" is not a commitment level; it is a residue. The
maintainer's conclusion: **this is a hand planner issue.** `_investment`
is per-country by construction, the ranking re-compares after every
point, and neither can see "should this card's last Op finish a job or
start one". The country valuation is doing its job.

Open, and not to be confused with the above: whether the fourth Op
leaving is *wrong*. In the trace it went to empty Battlegrounds, which
the maintainer has separately asked for more of. What the 45 cases
actually did with it is unmeasured.
