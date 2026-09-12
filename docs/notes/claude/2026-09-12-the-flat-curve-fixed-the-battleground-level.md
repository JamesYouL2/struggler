# The flat VP curve fixed the battleground level, and the Ops rate is still a parameter

Two corpus diagnostics at the shipped weights, after `vp_swing` and
`access_chain` were removed. No games; both read positions only.

## 1. The battleground level is no longer the defect it was

`models/provenance.json` rates `battleground` **known-wrong**, on three
recorded symptoms: a turn-4 Battleground pricing at **2.05 VP** against the
maintainer's floor of ~4, a whole map spanning 0.49 VP against a stated
2-3, and the region order inverted at the top.
`2026-09-12-what-deserves-256-seeds.md` proposed spending the sample
ceiling on it -- but only after running this diagnostic first, because the
arithmetic said the flat VP curve might already have closed most of it.

It did, and by more than predicted. Best Battleground of any occupancy, in
VP, `scoring_discount` at the shipped 0.8, over 20 corpus positions:

| turn | T1 | T3 | T5 | T7 | T9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| now | 6.59 | 3.28 | 4.05 | 4.00 | 3.05 |
| previously recorded | 5.87 | 2.58 | -- | -- | ~1.3 |

**T5 reads 4.05 and T7 4.00, which is the maintainer's figure.** And the
decay is not halved, it is gone: from T3 on the sequence is 3.28, 4.05,
4.00, 3.05 -- not monotonic, roughly flat around 3.5. T3 -> T9 is **1.08x**
against the **1.33x** predicted and the **2.66x** it was.

The prediction and why it held: `vp_value = per_vp * ops_value(1)`, and a
Battleground's VP is `delta / vp_value`. `per_vp` used to rise 2.0x across
a game on `vp_swing` alone, so the denominator grew and the VP reading
fell. Flat `per_vp` removes that growth, and what is left -- `ops_value(1)`
rising about 1.12x -- is close enough to a Battleground's own `delta`
growth (~1.28x recorded) that the ratio barely moves.

**So the 256-seed ceiling should not be spent on `battleground`.** The
experiment that note proposed is not needed, because a change made for an
entirely different reason fixed what it was going to measure. That is the
whole argument for running the free diagnostic first, and it is the second
time today the cheap measurement retired the expensive one.

Three caveats, because this number will get quoted. Twenty positions is
thin. It is the model pricing *itself*, not evidence the bot plays better
-- no games were involved and nothing here is a strength claim. And the
"empty stability-2" comparison blanks from T7, because by then every one is
contested, so the row shown compares slightly different things turn to
turn.

What is left is T1 at 6.59, now the outlier rather than the late-game
collapse. Whether that is wrong is a different question from the one this
closes, and it points the other way -- toward turn 1 being priced high,
which the maintainer's "Ops first on turn 1" reading may well want.

## 2. VP per Op is flat at exactly 2.000, as predicted

The table the rebuild has to move, re-measured after the deletions:

| turn | n | `ops_value(1)` | `vp_value` | VP per Op |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 124 | 23.3111 | 11.6556 | 2.000 |
| 3 | 107 | 19.6101 | 9.8050 | 2.000 |
| 5 | 117 | 22.0202 | 11.0101 | 2.000 |
| 7 | 105 | 26.4671 | 13.2335 | 2.000 |
| 9 | 52 | 26.0286 | 13.0143 | 2.000 |

Exactly 2.000 at every turn, to three decimals, because `vp_value` is
defined as `per_vp * ops_value(1)` and `per_vp` is now the single constant
`vp_base = 0.5`. VP-per-Op is `1 / per_vp` identically and carries nothing
from the board. This is not a discovery -- it was predicted before the run
-- and recording it is the point: **the expert rule wants this column to
fall 2.0 -> 0.5 across the game, and the model now says it never moves.**

After the rebuild it should fall *because the board says so*. If it comes
out flat again, the rebuild did not move the thing it was for.

One improvement worth noting: `ops_value(1)` is much smoother than it was
this morning. Before the chain removal: 24.2, 19.3, 31.7, 16.4, 28.0. Now:
23.3, 19.6, 22.0, 26.5, 26.0. The two-hop walk was contributing most of the
turn-to-turn noise, which is a small argument that removing it improved the
term's behaviour beyond making it cheaper.

## 3. A new defect, found by accident

The run logged, twice:

    event Latin_American_Debt_Crisis failed in the sandbox
    (RecursionError: maximum recursion depth exceeded); using the estimate

Not recorded anywhere -- not in `docs/LIMITATIONS.md`, not in the notes,
not in the code. The card is *"Unless the US discards a 3+-Ops card, USSR
doubles its Influence in up to 2 South America countries"*, so resolving it
needs an opponent discard decision, and evaluating that decision plausibly
re-enters the evaluator that is resolving the event.

It fails loudly and falls back to an estimate rather than silently
returning a wrong number, which is the right behaviour and is why it was
visible at all. But the card is mispriced every time it is evaluated, and
"using the estimate" is exactly the shape that hides a defect for weeks
once nobody is reading the log. Worth its own investigation; not chased
here.
