# Thailand is not a multiplier, and Southeast Asia is priced as the wrong kind of thing

The maintainer, correcting "Thailand x2": "Thailand isn't a full x2,
should be 1 + discounted scoring of 4 VP? something like that."

Right, and it exposes a category error that reaches all seven Southeast
Asian countries, not just Thailand.

`importance` is `(w.battleground if battleground else w.control) *
urgency`, and `urgency` sums a contribution per scoring card that will
still score. Being in Southeast Asia adds a second card, so it adds about
1.0 to urgency -- which is then **multiplied by the tier weight**:

| Country | urgency | tier weight | SEA contributes |
| --- | ---: | ---: | ---: |
| Thailand | 2.952 | `w.battleground` 5.0 | **5.0** |
| Malaysia, Vietnam, Laos/Cambodia, Philippines, Indonesia, Burma | 2.952 | `w.control` 1.5 | **1.5** |

So the bot prices Thailand's Southeast Asia scoring at **3.33 times** each
of the others. Southeast Asia Scoring pays `+2 VP for Control of Thailand,
+1 VP per other controlled country` -- **a flat 2:1**. Thailand is
overweighted against its neighbours by 1.67x.

The deeper problem is the shape, not the ratio. **Southeast Asia Scoring
awards flat VP per country; it has no tiers at all.** Routing it through
`w.battleground` and `w.control` prices a flat award as though it were a
Presence/Domination/Control contribution, which is what those weights
mean. No amount of tuning the weights fixes a term that is the wrong kind
of quantity, and the two weights cannot be set to satisfy both Southeast
Asia's 2:1 and the tier structure they exist for.

**The right form is the maintainer's: additive, not multiplicative.**

```
value(Thailand)          = ordinary Asia Battleground value + P(SEA scores) * 4 VP
value(other SE Asian)    = ordinary value                   + P(SEA scores) * 2 VP
```

4 and 2 rather than 2 and 1 because these are *swings*: holding Thailand
is +2 VP at the scoring and the opponent holding it is −2.

`P(SEA scores)` is the one free number, and it is measurable rather than
a matter of opinion, because Southeast Asia Scoring is the only scoring
card with `remove_after_event=True` -- it fires at most once per game,
where every other region's card recycles through the reshuffle. A
measurement is running.

This is the third exception earning its place: Thailand's double-count is
not a special case bolted onto the region model, it is a consequence of
Southeast Asia Scoring being a different kind of card, and the correct
implementation prices all seven of its countries, four of which are not
Battlegrounds.
