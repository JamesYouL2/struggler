# The VP potential as per-position linear weights

2026-09-18. This answers the maintainer's question: can the VP value
function be a set of linear weights? It can, and exactly, provided the
weights are recomputed for each position rather than fixed once. This
reopens [the 2026-09-17 viability verdict](../codex/2026-09-17-potential-delta-design.md)
("no gate survives" 40-120 s a game), which stands between the potential
and the hand planner's step 6 ([v3 plan](2026-09-18-hand-planner-plan-v3.md), step 5).

## The observation

The potential's expensive part is the tier expectation. Under the
independence DP, each country is an independent draw over (US, USSR,
uncontrolled). That makes the expectation **multilinear** in the
countries' probability triples: with every other country held fixed, it
is exactly affine in any one country's triple. So each country has three
numbers:

    W[c] = (E[tier | c US], E[tier | c USSR], E[tier | c uncontrolled])

These are exact linear weights at this position. A trial that moves one
country's triple from q to q' changes the region's expectation by
`(q' - q) . W[c]`, with no DP. The country bonuses and Southeast Asia's
payout are already linear, so they are exact as they stand.

Two things these weights are not:

- **Global constants.** W moves with every other country. A fixed table
  fitted offline would be today's `board_value` with regressed instead
  of guessed weights. That is a calibration gain, but it cannot see
  thresholds: whether one country flips domination depends on the rest
  of the region.
- **Exact for multi-country moves.** A placement that flips reach at
  neighbours in the same region moves several triples at once. The dot
  product drops the interaction terms.

## The prototype: `forecast.tier_weights`

A forward-backward pass. alpha_k is the count distribution of the first
k members. beta_k(y) is the expected payout given counts y after k
members. The weights are `W[k][s] = sum_x alpha_{k-1}(x) beta_k(x + shift_k(s))`.
beta is kept on every state a *forced* outcome reaches, because forcing
US where the forecast gives the US nothing is exactly what a placement
asks. It is not wired into anything.

Proved equal, member by member and outcome by outcome, to `tier_e_minus`
plus a forced reconvolve. The dot product for each member reproduces the
full DP. This holds in all six regions, at both horizons, on random
triples, with and without the Formosan/Shuttle overrides
(`test_tier_weights_are_the_exact_linear_weights_of_every_member`, 24
cases). Negative controls: mis-shifting a battleground fails all 24, and
letting a Shuttle-ignored member move fails the 12 override cases.

## Measured (local, idle 8-core box, 31 corpus positions, turns 3-9)

| region | full DP | weight table | all-member `tier_e_minus` |
| --- | ---: | ---: | ---: |
| Europe | 10.1 ms | 50.9 ms | 143.1 ms |
| Asia | 2.8 ms | 14.7 ms | 23.3 ms |
| Africa | 4.8 ms | 27.5 ms | 58.3 ms |
| Middle East, Central and South America | 0.5-0.6 ms | 2.6-2.8 ms | 2.6-3.0 ms |

- **Whole board** (6 regions x 2 horizons): the tables take 211 ms mean,
  253 ms max.
- **One delta** by dot product: 4 us per region-horizon, against the
  verdict's 6-30 ms per delta. That removes the ranking fan-out (10-60
  deltas per candidate, 10-20 candidates) as a cost.
- **Exactness, over every country +1 for the side to move (2604
  candidates):**
  - single-member region deltas: error at most 9e-15;
  - multi-member region deltas: median 1.3% relative, p95 5.8%, max 21%
    (0.09 VP of a 0.46 VP change, a Central America move touching five
    members);
  - the whole mass-weighted potential delta: median 0, p95 4.1%, max 17%.
- **The build is 5x a DP, not the 2-3x the arithmetic suggests.** The
  difference is Python set and tuple overhead in the forward
  needed-state pass. It is unoptimised.

## What a game would cost: an estimate, not a measurement

Two full self-play games (seeds 4000, 4001) made 627 and 747 rankings but
visited only **247 and 274 distinct boards**. A board change touches about
one region, so there were about as many distinct region states. The
tables are a per-board object, so the cost is per distinct board, not per
ranking:

- rebuild only the regions that moved: about 250 x 2 horizons x ~17 ms
  mean, **about 8 s a game**;
- about **25 s** if every rebuild were Europe;
- about **55 s** if the whole board were rebuilt every time, which the
  region cache avoids.

Against 40-120 s in the verdict, on a 34 s and an 88 s game here (the
second includes the T9 headline hot spot). It is still a real share of a
game, and the number to trust is a timed game, not this sum.

## The contract it needs (bug shape 1)

The tables are a per-decision cache keyed on the board **as synced**.
Every hypothetical must be priced as a linear delta from them: trial
placements, `_after_reply`'s replies and the event sandbox. A table must
never be rebuilt on a board moved mid-ranking. That is the
`_invalidate_base` discipline, which `test_base_cache_discipline.py`
gates. The reply and event paths are multi-member moves, so they carry
the approximation above.

## Next, if the maintainer wants it wired

1. Put `delta`'s scoring half behind a weight, default off, priced from
   the tables. Time full games locally, interleaved with the off arm
   (shape 7). That gives the real per-game number.
2. If the multi-member error matters: re-price exactly only the top few
   candidates, or add pairwise weights for same-region neighbour pairs
   (the reach flips). Measure the ranking change first. A 4% error on
   deltas may never flip a decision.
3. Gate it on CI. The strength question (does the potential beat the
   heuristic?) is the one the 2026-09-17 descope never got to ask.
