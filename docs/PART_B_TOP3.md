# Part B: the three worth doing first

Of the twelve in `docs/POSITION_PACK.md`, these three each answer a
question that is blocking something. The other nine are useful but
redundant with work already under way.

Each is reproduced in full here with the bot's own numbers, so this file
stands alone.

---

## 1. Decision 7 — `ops_type`, 4 Ops, **USSR**, seed 4001 turn 7 AR1

DEFCON 4, VP **−11** (so the USSR is well behind).

**What the bot chooses**

| Mode | Bot's value |
| --- | ---: |
| **coup** | **2.96 VP** ← plays this |
| influence | 1.52 VP |
| realignment | 1.36 VP |

**Its best option in each mode** (4 Ops, *not* 4 points — every South
American target costs the USSR **2 Ops per point**, since the US controls
them all):

| Influence, 4 Ops | | Coup, 4 Ops | | Realign | |
| --- | ---: | --- | ---: | --- | ---: |
| greedy multi-country | **1.52** | **Argentina** | **2.96** | Argentina | 1.36 |
| Venezuela, 2 pts | 1.25 | Brazil | 2.80 | India | 1.27 |
| Angola, 2 pts | 0.12 | Angola | 2.57 | Angola | 0.98 |

The board it is looking at — the whole of South America is US-held and
thin:

```
 *Argentina   US 2  SU 0  stab 2  [US]
 *Brazil      US 2  SU 0  stab 2  [US]
 *Venezuela   US 3  SU 0  stab 2  [US]
  Colombia    US 0  SU 4  stab 1  [USSR]
```

**Why it matters.** This decision *defines the bot's exchange rate*:
`ops_value` is the max of best-placement and best-coup, and it is the
denominator of every VP figure in the project — `vp_value`,
`game_value`, the sentinel bounds, and the region calibration you
supplied. The coup wins here by roughly 2:1.

**But it may be right here**, which is the thing worth your judgement.
Placing into opponent-controlled ground costs double; couping does not.
With every South American battleground US-held, the USSR is locked out of
cheap placement, so the coup advantage may be a correct reading of a
locked position rather than a bias. **Is Argentina the play, and if not,
what is?**

## 2. Decision 10 — `coup_target`, 1 Op, USSR, seed 4002 turn 7 AR6

**Which country to coup with a single Op.**

You have said the 1- or 2-Op coup into Nigeria, Angola or Zaire is often
the best play on the board — and that is exactly the play that sets
`ops_value(1)`, and therefore the price of a VP, for every other decision
in the position. One cheap African target anywhere moves the whole
exchange rate.

Two questions at once: is the **target** right, and is a 1-Op coup really
worth what the bot thinks (1.11 VP, against 0.24 for the best
placement)? You have already suggested the answer may be that 2 or 3 Ops
is the better spend, for the chance at the bigger result — which would
say `ops_value(1)` should be fitted on **placement only**.

## 3. Decision 8 — `action_round_play`, US, seed 4001 turn 7 AR3

**Which card to play.**

The most frequent decision in the game, and the one with the worst known
pathology: **19 of the 26 positions where the bot scores its top two
identically are card plays.** It spends equal-Ops own-side cards in
whatever order the engine lists them, rather than burning its least
valuable event first.

**Your answer: OAS Founded into Chile.** Recorded. What would help is the
one-line *why* — whether it is the Chile foothold specifically, the
South America tier it moves, or that the alternative was worth holding.
The reason is what generalises; the move alone only fixes one position.

---

## Two defects these turned up before anyone annotated anything

**Realignment is priced as `realign(c) * ops`** — one country, linear in
Ops. Two things wrong, both of which you named: a multi-Op realignment
can target **different countries**, and it is **sequential with
feedback**, so the right model is a branching tree (best target, then the
next choice conditioned on whether the first roll succeeded). The bot
prices it as the same country attacked *N* times.

**Influence spreads and the earlier version of this file did not say
so.** A 4-Ops card can place into four different countries, and
`_placement_ops_value` does model that as a greedy multi-country plan.
An earlier table here listed single-country spends and conflated
influence *points* with *Ops*, which in an opponent-controlled country
differ by a factor of two. Corrected above.

---

**If you only do one, do Decision 7.** It is the only one that can tell
me the measurements themselves are mis-denominated, and everything else
in the queue is calibrated against them.
