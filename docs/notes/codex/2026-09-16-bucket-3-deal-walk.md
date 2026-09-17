# 2026-09-16 — Factor 2, bucket 3: the post-reshuffle deal walk

Still unwired (nothing consumes `schedule.Opportunity` yet — the live
ranking's `_scoring_weight_uncached` keeps its 0.5/0.5/1.0 assumed masses,
which is integration work, one recapture, one gate).

## What changed

`schedule.opportunities` bucket 3 was flat 1.0 conditioned on
"the reshuffle happens". The old note (2026-09-16-schedule-and-regions)
had already real-mathed buckets 1/2 (`p_opponent_holds` pile-share,
`cycle_deal_masses`). Bucket 3's 1.0 was only *nearly* right: the
must-play rule puts every live scoring in the discard pile by the
reshuffle, so the card recycles with certainty — but it then fires the
turn it is **dealt**, and if the post-reshuffle deals run out before game
end the flat 1.0 overstated it.

So bucket 3's mass is now `P(dealt before game end | the reshuffle
happens)`, the same uniform `deal / pile` walk continued over the
recycled deck:

- `public_cards.deck_walk` — the pile's forward walk extracted so
  `turns_to_reshuffle`, `cycle_deal_masses` and the new walk share one
  deck arithmetic (the bug-shape "second copy of a rule" closes here; the
  two walks had already been written twice inline).
- `public_cards.recycled_pile_size` — the ONE estimate in the change:
  entered-by-the-reshuffle minus removed minus the spent SEA one-shot
  minus `2 x hand_limit` holdings. The bi�ased part is documented (the
  partial recycled remainder of the exhausting deal is left out, so
  holdings are (slightly) overcounted and the masses are a lower bound
  by at most one partial deal).
- `public_cards.post_reshuffle_deal_masses` — walk from the reshuffle
  turn in; the exhausting deal's deficit (how short it fell) is taken
  from the shared walk, not guessed; an exhausting deal before the last
  turn stops the walk (reshuffle 2's leftover belongs to the next
  cycle); the last turn's exhausting deal is in fully.

## What did NOT change

- Bucket 4 stays zero mass, now for a sharper reason than "no timing
  model": its recycled pile would include cards neither played by today
  nor dealt hence — plays still to choose — so its size is not derivable
  from today's public state at all.
- A `future`-state card's bucket 3 stays flat 1.0: what it joins is its
  period's entry layered on whatever earlier cycles left, which the
  current walk does not model. Documented in the module.

## Checks

- Conservation the tests pin: bucket 1+2 ≤ 1 exactly (holder-uncertainty
  split of one firing); bucket 3 = 1 - prod(1 - m) and > 0 on a fresh
  deal. Cross-bucket sums do NOT stay ≤ 1 and must not be tested to:
  buckets are alternative firing *events*, not exclusive survivors of
  one firing — a card that fires this turn also recycles and fires
  again.
- "Walking the same card twice across cycles" is correct behavior:
  `_scoring_weight_uncached` prices each scoring event, and a scoring
  card genuinely pays twice (this cycle, then post-reshuffle).
- Masses-only change, nothing consumes them, corpus and rankings
  untouched. Suite green before commit.
