# 2026-09-17 — Three scoring arms after the deck-walk fix: all level, and the rival term is not over-set

Dispatched on the reasoning that the audit's F3 changed these knobs'
leverage without anyone choosing it. Total occurrence mass was unchanged
(8.696 -> 8.693 per position over 70 corpus positions) but 0.39 of it moved
from bucket 3 to bucket 2, so the this-cycle term that `scoring_rival` and
`scoring_hand` multiply grew 16% for a card we do not hold and not at all
for one we do.

All three arms ran 128 verdict seeds + 64 held, 384 games, on the fixed
code (`ce1293d`).

| arm | weight | reading |
| --- | --- | ---: |
| `scoring-hand-premium` | `scoring_hand` 1.0 -> 1.25 | 0.514 +/-0.034 |
| `scoring-rival-half` | `scoring_rival` 1.0 -> 0.5 | 0.497 +/-0.035 |
| `scoring-rival-quarter` | `scoring_rival` 1.0 -> 0.25 | 0.466 +/-0.035 |

Halfwidths are one-sided 95% (1.645 x SE), the same convention the gate
uses. Every one of them is "not measurably worse". Nothing here ships.

## What the rival pair says, and why it needed to be a pair

The hypothesis was that `scoring_rival` might now be over-set: it
multiplies buckets 1+2 by (1 + r * P(the opponent holds it)), so at r=1.0 a
card they certainly hold doubles its own this-cycle urgency, and F3 grew
exactly that base. **The readings do not support it.** Ordered by weight:

    r = 0.25  ->  0.466
    r = 0.50  ->  0.497
    r = 1.00  ->  0.500 by construction (it is the baseline)

Monotone, in the direction that says shrinking the term makes the bot
worse. Each step is inside its own interval, so no single arm convicts
anything -- but the ordering across three points is the reason the pair was
run instead of one arm. A lone 0.497 at r=0.5 is exactly the reading that
cannot distinguish "the term is over-set" from "the term does nothing", the
trap `experiments.json` records from the 2026-09-12 arms. With the far side
in, neither reading survives: an inert term would sit at 0.500 at both
points, and an over-set one would read ABOVE 0.500 when shrunk.

The weakness to state: the arms are on DISJOINT seed ranges (11236-11427
and 11620-11811), so the ordering is three independent samples and not a
paired comparison. It is weaker evidence than the same three weights run on
one seed set would be, and if anyone wants to act on the curve rather than
merely decline to shrink it, that is the run to do.

## What it says about the hand premium

`scoring_hand` ships at 1.0 -- no premium at all -- and 1.25 reads 0.514,
level. The arm was motivated by holding being worth relatively LESS in mass
terms after F3 (the held card's this-cycle mass did not move, 0.3857 per
position on both sides, while the unseen card's rose 16%). If holding
deserved compensation for that, 1.25 was where it would have shown. It did
not. Either holding is worth nothing beyond bucket 1's certainty, or the
forecast already credits it; this arm cannot separate those.

## Where this leaves the drift hunt

Nowhere, which is the useful part. The scoring knobs are not where the
2026-09-18 regression lives: three arms spanning a 4x range on the term
whose leverage most changed all read level. Whatever put HEAD measurably
behind v0.2.0 (0.402 +/-0.047) and v0.2.1 (0.426 +/-0.049) is not a
mis-set scoring weight of this kind, and the six-tag bisect is the thing
that will say what it is.
