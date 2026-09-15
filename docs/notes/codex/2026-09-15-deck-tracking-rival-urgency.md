# 2026-09-15 — Deck tracking I: rival urgency for a scoring they likely hold

Branch `experiment/deck-tracking` off `origin/main` (`35182ef`).

## The gap

`public_cards.p_opponent_holds` -- P(the opponent holds a card) from public
counts alone -- existed and was pinned by tests, and consumed by nothing.
The deck-tracking machinery ended at the library door.

## The arm

When the opponent likely holds a region's scoring card, this cycle's
urgency for that region is multiplied by `(1 + scoring_rival * p)`. They
score at their best moment, so control banked before they do is worth
more. Ships at `scoring_rival = 1.0`; 0.0 is off.

This deliberately breaks side-agnostic urgency: holder identity predicts
TIMING, not just retention. The zero-sum accounting moves with it -- both
seats price the same urgency -- so nothing is double-counted, but a
fixture, not an argument, has to carry it.

Why this shape and not a flat bonus: p is theirs/pile, so the term is
small early (~0.08) and concentrates exactly where a strong player's
information does -- the drained pile before a reshuffle. The information
is free (public counts) and the cost is one arithmetic call per scoring
card per decision, skipped entirely with the arm off.

## Pins

- `test_rival_tracking_raises_urgency_only_where_they_may_hold_the_scoring`:
  drained pile raises Iran urgency, a discarded scoring does not move,
  arm-off is bit-identical across the drain.
- Ledger `scoring_rival`: guess/underdetermined, pending a gate vs
  `origin/main`.

## Gate (pending at time of writing)

Verdict to be appended.
