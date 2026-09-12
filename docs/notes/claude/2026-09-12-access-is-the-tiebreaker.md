# `access` is the tiebreaker, so the ablation cannot accept

The maintainer, on the queued access ablation: "We shouldn't run access
ablation first, because we can't delete it, tiebreaker issues."

That is right, and it retires the experiment rather than reordering it.

## The experiment's accepting outcome is unavailable

The ablation was queued to answer "is the access family worth anything?",
with the stated payoff that if it accepts, the family comes out and every
later game gets cheaper. But the family is also what keeps two countries
with the same stability, region and battleground flag distinguishable at
all. Remove it and they score *exactly* equal, and the search has nothing
to prefer between them.

So the accepting branch was never available: "not measurably worse on
strength" would not have licensed a deletion, because strength is not the
only thing the term is doing. An experiment whose accepting outcome cannot
be acted on is not worth 256 seeds.

## What the 0.0 run measured instead

The hung run is still evidence, and it is the only direct measurement of
what the term costs the search. Per-game wall times from the two 2026-09-11
queue runs:

| run | n | median | mean | p90 | slowest finished |
| --- | ---: | ---: | ---: | ---: | ---: |
| `access: 0.0` | 511 | 99.9s | 143.5s | 265.9s | 3623s |
| `vp_swing: 4.0` | 512 | 84.1s | 118.6s | 240.2s | 1664s |

Plus one game that never finished at all: seed 7500, USSR, four hours at
97% CPU before the maintainer killed it.

The shape matters more than the headline. The median moves 19% and p90
only 11%, but the slowest finished game is 2.2x and the tail runs off the
end. Zeroing `access` does not make every position expensive; it makes a
small number of positions unboundedly expensive, which is what a search
with no gradient to follow looks like.

Two confounds, stated because the table invites over-reading: the runs
used different seed ranges (7300-7555 against 7000-7255), so the deals
differ, and in both runs only one seat carries the modified weights. The
effect is large enough to survive both, but this is not a controlled
timing experiment and should not be quoted as one.

## Should every country get a slightly different core value?

The maintainer's follow-up: "I guess what I need to do is just make sure
every country that is tied on stability and region has a slightly
different core value?"

**Recommend against**, for three reasons.

1. **It is already there, and it is `access` itself.** The ablation at
   `0.01` -- the version that replaced `0.0` -- is exactly the proposed
   epsilon, except that it is derived from a real term rather than
   invented. At 1% of its magnitude `access` still orders countries that
   are otherwise identical, while contributing almost nothing to the
   value. Only the `0.0` run removed the tiebreak, and `0.0` is not run
   again.

2. **Ties are already broken, deterministically.** `RolloutPolicy.score`
   maxes over `(value, country)` and `_investment` keeps the first best
   point count with a strict `>`. Nothing is nondeterministic and nothing
   crashes; the cost is search time. A per-country epsilon would change
   *which* tied country wins -- from "alphabetically first" to "whichever
   got the larger jitter" -- and neither is principled. Alphabetical has
   the merit of being visibly arbitrary. An epsilon disguises the same
   arbitrariness as a value, which is shape 6: a number on the wrong
   scale, four recurrences.

3. **It may not even help, and could hurt.** If the slowdown is "many
   candidates share the maximum", an epsilon fixes it. If it is "the
   search has no gradient and expands more nodes", an epsilon hands it a
   *false* gradient of arbitrary sign, and the search will follow the
   jitter as though it were signal. Which of the two it is has not been
   measured. The cost of guessing wrong is permanent: the epsilon lives
   inside the value function, changes every ranking in the parity corpus,
   and a native port has to reproduce it exactly.

The pathology is also diagnostic-only. Production ships `access: 1.5`; no
shipped configuration has this problem. Paying a permanent semantic cost
to make one retired diagnostic cheaper is the wrong trade.

## What replaces the ablation

Not "is `access` worth anything" -- that question is closed, it is
load-bearing for the search -- but "is `1.5` the right magnitude". That is
a sweep, not an ablation: `0.75` and `3.0` against the shipped `1.5`, both
of which keep the ordering and neither of which can hang. Worth queueing
once the board-side terms are measured, since those move the same board
value the access term is a fraction of.

The operational half is already handled: `--stall-timeout` bounds any
future run of this shape whatever causes it, and it is now in one shared
`run_ab` rather than two copies that drifted.
