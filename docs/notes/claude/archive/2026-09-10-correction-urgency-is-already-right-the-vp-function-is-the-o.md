# Correction: urgency is already right; the VP function is the only wrong part

The maintainer: "urgency is same, VP calculation is special without
tiering. Oh, there are probably two terms, an urgency term and a rest of
game term (based on average/expected game length)? Something like that."

**Urgency already handles Southeast Asia correctly**, and the previous
section overstated the damage by implying otherwise.
`public_cards.scoring_schedule` returns `(0,)` for Southeast Asia Scoring
where every other card gets `(0, reshuffle)`:

```python
once = card == 'Southeast_Asia_Scoring'
...
schedule = (0,) if once else (0, reshuffle)
```

So the one-shot nature is already in the timing machinery. The error is
confined to what the previous section called the shape: the resulting
urgency is multiplied by a **tier** weight (`w.battleground` or
`w.control`) when Southeast Asia Scoring's award is flat. Urgency stays
as it is; only the VP function is wrong.

**And the two terms half-exist already.** `_scoring_weight_uncached` sums

1. the scheduled scorings, each discounted `w.scoring_discount ** turns`
   -- the *urgency* term, how soon and how often; and
2. `w.scoring_final * final_scoring_odds(obs)` -- the *rest of game* term,
   and it is already keyed on expected game length rather than flat:
   `FINAL_SCORING_ODDS` runs 6/27 at turn 1 to 6/6 at turn 10.

What is missing is that they are **added into one scalar and then
multiplied by a tier weight**, which is where the VP-function distinction
gets lost. Keeping them apart is the maintainer's point, and the
factorisation that follows makes Southeast Asia fall out rather than
needing a special case:

```
value(country) = SUM over expected future scorings of
                     P(that scoring happens) * VP_of(card, position, country)
```

`VP_of` is the tiered Presence/Domination/Control function for the six
region cards and the flat per-country award for Southeast Asia. Urgency
and rest-of-game are both inside `P`, where they belong, and the tier
weights stop being applied to something that has no tiers.

That is a better target than patching a Thailand constant: it removes a
special case instead of adding one, and it is the same restructuring the
region-model rewrite needs anyway.
