# What is still open, roughly in order

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
