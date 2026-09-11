# 2026-09-11 — Breaks by Operations spent: the maintainer's 4 > 3 > 2, measured

The maintainer, refining the poke instrument: count breaks by the Ops
they cost, not the points they buy, and expect **4-Op breaks to be more
common than 3-Op than 2-Op**. The prediction is not intuition, it is the
rate structure. Read off the engine against bare control of a
stability-2 country:

| Ops spent | points | position left | their repair | exchange |
| --- | --- | --- | --- | --- |
| 2 | 1 | 1-2 | 1 Op | 2.00 : 1 |
| 3 | 2 | 2-2 | 2 Ops | 1.50 : 1 |
| 4 | 3 | 3-2 | 3 Ops | 1.33 : 1 |
| 5 | 4 | 4-2 | takes Control | 1.00 : 1 |

The first point costs double and the rest cost single, so every Op past
the break improves the trade. And against overprotection, confirming the
maintainer's own rule: +1 needs **4 Ops** to break (4.00 : 1), +2 needs
six. Odd budgets strand an Op there -- 3 Ops buys one point at cost two
and cannot afford a second.

### Measured, 24 games a side

| Ops on the break | search off | search on |
| --- | --- | --- |
| 2 | 301 (55%) | 4 (3%) |
| 3 | 206 (38%) | 121 (86%) |
| 4 | 25 (4.6%) | 4 (2.8%) |
| 5 | 14 (2.6%) | 12 (8.5%) |
| total | 546 (22.8/game) | 141 (5.9/game) |

Not the maintainer's ordering: 3 dominates at 86%. Two findings fall out.

**The bot never attacks overprotection.** Zero of 141 spends faced more
than bare control, so it never takes the 4:1 trade and never strands an
Op. That part is already right and needs nothing.

**The forward search suppresses 4-Op breaks harder than 3-Op ones**, 84%
against 41%, which is backwards -- the 4-Op break is the better trade.
Only the 5-Op breaks, which take Control outright and cannot be answered,
come through untouched (-14%).

### Where it actually comes from, after two wrong answers

**Wrong answer one: the deck.** Only 13 of 103 non-scoring cards are 4
Ops against 36 at 3, so 4 > 3 is unreachable by spending policy alone --
it would need the bot to *reserve* big cards for breaks. True, and not
the explanation: at the deck ratio one would still expect ~44 four-Op
breaks, not 16.

**Wrong answer two: consolidation is unpriced.** `_after_reply` returns
early when control does not change, so the point that takes 2-2 to 3-2
gets no reply discount at all -- and it raises their repair from 2 Ops to
3. That looked like the bug. It is not: `country_value` already prices
margin through the `progress` ramp, so that point is worth 21.76 raw at
cost 1, against the break's 40.69 at cost 2 *minus* a 30.65 discount.
Per Op the consolidating point rates **21.76 to the break's 5.02**. The
model is not underpaying for commitment.

### The real one: the budget cross-tab

| card's Ops | breaks | spent 2 | spent 3 | spent 4 | spent 5 |
| --- | --- | --- | --- | --- | --- |
| 3 | 78 | 2 | **76 (97%)** | -- | -- |
| 4 | 63 | 2 | **45 (71%)** | 4 | 12 |

Given a 3-Op card the bot commits the whole card 97% of the time. Given
a 4-Op card it spends 3 on the break and sends the fourth Op elsewhere
71% of the time. A trace confirms the mechanism and is starker: on an
opening-ish board with four Ops and a breakable Brazil, **all four go to
Angola, Panama and Egypt and none to the break**, with the search on or
off. Cheap uncontested points at 1 Op beat a contested point at 2 on the
per-Op criterion, so the bot breaks only once the cheap ground is gone
and the break budget is whatever is left over.

So "3-Op break" is not a commitment level; it is a residue. The
maintainer's conclusion: **this is a hand planner issue.** `_investment`
is per-country by construction, the ranking re-compares after every
point, and neither can see "should this card's last Op finish a job or
start one". The country valuation is doing its job.

Open, and not to be confused with the above: whether the fourth Op
leaving is *wrong*. In the trace it went to empty Battlegrounds, which
the maintainer has separately asked for more of. What the 45 cases
actually did with it is unmeasured.
