# Wiring the VP rebuild into the ranking: 172x, and where it actually goes

2026-09-20. Measured on `6ff8b2b` (`exp/potential-in-ranking`), which puts
the potential behind a `StrategicWeights.potential` weight, off by default:
`delta` adds `potential_delta` (the cheap linear dot product) and `value`
adds `scoring_potential` (the whole-board total) so that the two stay each
other's difference.

## The cost

A bounded prefix, seed 4000, same 120 bot decisions both arms, one idle box:

| `potential` | 120 decisions | per decision |
| --- | ---: | ---: |
| 0.0 | 1.76 s | 14.7 ms |
| 1.0 | 302.50 s | **2520.9 ms** |

172x. Whole games confirm it: seed 4000 finishes in 20.6 s at 0.0 and was
abandoned past 1200 s still on turn 7 at 1.0.

## Where it is NOT

The obvious suspect is `value`: `scoring_potential` is seven
`expected_payout` DPs, and `value` is called everywhere. It does not appear
in the top 22 of the profile at all. The whole cost is on the `delta` path:

| | calls (20 decisions) | cumulative |
| --- | ---: | ---: |
| `potential_delta` | 8,165 | 126.8 s |
| `_weight_tables` | 10,792 | 123.6 s |
| `forecast.member_weights` | 2,454 | 122.8 s |
| `forecast.tier_weights` | 2,454 | 121.0 s |

`potential_delta`'s dot product really is microseconds. It averages 15.5 ms
because 89% of the time is spent rebuilding the table it dots against.

## Two heuristics that do not work

**Prune the DP's low-mass states.** `tier_weights` is a forward-backward
walk over 4-D count states `(us_countries, ussr_countries, us_bg, ussr_bg)`;
Europe reaches 3,213 of them and costs 43 ms, Africa 2,205 and 28 ms, and
all six regions together 92 ms. Dropping states below a mass threshold, on
a turn-6 board:

| prune eps | six regions | worst weight error |
| --- | ---: | ---: |
| exact | 91.8 ms | 0 |
| 1e-9 | 90.2 ms | 1.1e-07 VP |
| 1e-7 | 81.5 ms | 2.2e-05 VP |
| 1e-5 | 71.7 ms | 3.2e-03 VP |
| 1e-4 | 61.2 ms | 3.9e-02 VP |
| 1e-3 | 50.8 ms | 5.3e-01 VP |

A third of the time for error a ranking can see. The count distribution has
no negligible tail: the mass is spread over states that all matter.

**Cache the tables harder.** Over 20 decisions the ranking makes 10,792
`_weight_tables` calls against **642 distinct `(digest, region)` keys**, and
runs 1,227 table builds -- **1.91 builds per distinct key**. The single-slot
per-region cache that `_invalidate_base` clears is already catching 89% of
the calls. A perfect LRU buys 1.9x against the 172x needed.

The ranking is not rebuilding redundantly. It visits 32 distinct positions
per decision -- the reply models (`_after_reply`, `_coup_reply`) and
`_investment` move the board, and `_invalidate_base` correctly drops the
tables each time -- and each of those positions honestly needs its own exact
table. 32 x 100 ms (two horizons) is the 2.5 s.

## The heuristic that does work: approximate freshness, not arithmetic

The linear weights answer "what is this country worth to this region's
expected payout". That is a property of the whole region's control
distribution, not of one placement, so it moves slowly. Build the tables at
the synced board and dot against them for every sub-position the ranking
visits, refreshing on a schedule instead of on every board move:

| rebuild the tables | added to a 20.6 s game | error |
| --- | ---: | --- |
| per position (today) | ~3,400 s | none |
| per position, perfect LRU | ~1,800 s | none |
| per decision | ~170 s | first order across a decision |
| **per action round** | **~13 s** | first order across a round |
| per turn | ~1.9 s | first order across a turn |

Per action round is the affordable row: 1.6x a game, which an anchored arm
can price. Per decision is not affordable, which is the surprising part --
even a perfect per-decision rebuild leaves 13x.

This is the same approximation `potential_delta` already documents itself as
making. It is exact for a one-country change against a fresh table, and
first order for several; extending the table across a reply model's trial
board is more of the same, and the error is measurable the same way --
price a game's deltas against stale and fresh tables and compare.

**This is bug shape 1 territory and the discipline is inverted here.** The
existing cache is keyed on `self._position.digest` precisely so that a table
built on one board is never read on another. Refreshing on a schedule
deliberately breaks that, so it cannot be a silent cache: it has to be a
named approximation with its own weight or flag, its error measured, and
`potential_delta`'s docstring has to say which board its weights came from.
A stale table read through a digest-keyed cache would be the shape's tenth
instance.

## Next

1. Compress the DP state. Tiers read the country counts only through
   "at least one" and "more than the opponent", so `(us_countries,
   ussr_countries)` could collapse to a clamped difference plus two presence
   flags. Estimated ~3x, not measured -- and 3x is not on its own enough,
   which is why it is second.
2. Refresh per action round behind a flag, measure the staleness error
   against fresh tables over a real game, then an anchored arm against
   `07d553a`.
3. Only then decide whether the potential earns its cost at all. Nothing
   here says it makes the bot stronger; every number above is a price.
