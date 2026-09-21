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

## What it cost to fix, in four steps

The maintainer asked for the action-round experiment, and asked whether any
of this could be precomputed before the game and looked up during it. Both,
and the second mattered more.

Seed 4000, whole game, one idle box:

| | seed 4000 | vs term off |
| --- | ---: | ---: |
| term off | 16.9 s | -- |
| exact, per position | abandoned past 1200 s at T7 | >70x |
| + round-level tables | 143.9 s | 8.5x |
| + precomputed trial plans | 141.9 s | 8.4x |
| + memoised control forecast | 85.8 s | 5.1x |
| + flat-lattice tier DP | **46.5 s** | **2.75x** |

Every step after the first is EXACT -- same turn reached, same final VP,
every game -- so only the first row is an approximation.

**1. Round-level tables (`potential_refresh`).** The named approximation:
build the linear weights at the first position of an action round and dot
every later position in that round against them. 172x to 8.5x.

**2. Precomputed trial plans (exact).** `potential_delta` rebuilt two dict
comprehensions over every member of every touched region on each of 45,000
calls, plus a `t.ids[m] == 'Thailand'` string compare. All terrain. Worth
1.4% -- real, and much smaller than the profile's call counts suggested.

**3. A memoised control forecast (exact).** `_control_features` reads six
things about a country: both influence counts, both reach flags, the
controller and the stability. The fit reads nothing else -- not the
country's identity, not the rest of the board -- so those six plus the side
and horizon ARE the key, and the table is shared across every country whose
local state matches. 1.4M logistic evaluations became lookups. 141.9 s to
85.8 s, the single biggest step.

**4. A flat-lattice tier DP (exact).** Which states the DP can occupy, what
one member's three outcomes do to a state, and what every state pays out are
all terrain; only the probabilities move. Built once per (region, override
pattern), with the 4-count state packed into one integer. All six regions
118.2 ms to 15.9 ms, 7.45x, worst weight error 3.1e-15.

**Two versions of step 4 were wrong while every existing test passed.**
Walking the packed lattice densely LOST, 0.65x, because it is five times
bigger than the set of states a dict actually holds. Restricting the
backward pass to the reachable states instead of the `needed` states looked
5.66x faster and was 3.0 VP wrong -- beta has to be defined where a FORCED
outcome lands, which is exactly what the original walk was being careful
about. `test_the_flat_lattice_agrees_with_the_dict_walk` is the only test
that compares the two implementations, and it fails on that second bug.

## What the approximation costs

With everything above in, the exact per-position arm is affordable enough to
measure against: 282.6 ms a decision versus 31.8 ms with round tables and
10.5 ms with the term off. So every `potential_delta` call can be priced
both ways and the difference recorded.

| | turn 1, 80 decisions | T7->T8, 80 decisions |
| --- | ---: | ---: |
| priced both ways | 30,192 | 84,157 |
| identical | 52% | 65% |
| median | 0.0000 VP | 0.0000 VP |
| p90 | 0.0336 VP | 0.0112 VP |
| p99 | 0.2634 VP | 0.0622 VP |
| max | **3.7315 VP** | 0.2178 VP |

The approximation is benign in the middle game and worst at turn 1, which is
the right shape: a round's staleness is how much influence moved during it,
and turn 1 moves the most. A 3.73 VP misprice on a ranking decided in tenths
is not something to wave through -- if the arm below disappoints, refreshing
on drift (rebuild when the region has moved more than k influence since the
table was built) prices the same idea with the error bounded instead of the
schedule.

## Where the remaining cost is NOT

Worth recording because two guesses were wrong. It is not `value`/
`scoring_potential`, which never reached the top 22 of any profile taken
here. It is not redundant caching: 10,792 `_weight_tables` calls hit 642
distinct `(digest, region)` keys with 1,227 builds, 1.91 per key, so the
existing digest-keyed cache was already 89% effective. And it is not the
DP's numerical tail, which pruning showed has nothing to throw away.

## The arm's answer (run 35531902621, 512 seeds 56000-56511)

| arm | vs | score | one-sided 95% |
| --- | --- | ---: | --- |
| `potential-round-base` | 07d553a | 0.541 | [0.518, 0.564] |
| `potential-round-on` | 07d553a | 0.562 | [0.538, 0.586] |

Paired, seed by seed: **+0.021 [-0.009, +0.052]**.

The interval contains zero. The term is not measured to help and not
measured not to -- which, against a cost of 2.75x a game, is a decision:
**both weights ship at 0.0.** `potential` and `potential_refresh` stay in
the tree as an experiment an arm can switch on, not as a default.

Worth being plain about what this does and does not say. It does not say the
VP rebuild is worthless in the ranking; +0.021 is the wrong sign for that
claim, and 512 seeds cannot resolve it. It says nobody may turn the term on
on the strength of what has been measured so far, and that the next person
to want it needs either a bigger block or a cheaper term, because 2.75x buys
a reading whose error bars swallow the effect.

The three exact changes underneath it -- the flat lattice, the memoised
control forecast, the precomputed trial plans -- do not depend on this
verdict and are on by default. They were never about the potential; they
were about the DP, the fit and the per-call rebuilds that the potential
merely made visible.

## Next

1. Nothing here. The term is off and the arm has answered; reopening it
   needs a cheaper formulation or a much bigger block, not another dispatch
   of the same arm on the same size.
2. If it is ever reopened: refresh on drift rather than on the clock (the
   turn-1 max of 3.73 VP is the reason), and close the known gap that the
   event sandbox does not price the potential, so that a placement and an
   event making the same board change are valued the same way.
