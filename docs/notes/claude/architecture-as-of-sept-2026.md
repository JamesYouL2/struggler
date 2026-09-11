# Architecture, as of Sept 2026

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
