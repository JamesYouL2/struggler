# Part B: the three worth doing first

Of the twelve in `docs/POSITION_PACK.md`. Each is reproduced here with
the board and the bot's own numbers, so the file stands alone.

**Status: all three answered, and the bot was right in all three.** That
is itself the finding — see "What three correct answers tell us" at the
end.

---

## 1. Decision 7 — `ops_type`, 4 Ops, **USSR**, seed 4001 T7 AR1

DEFCON 4, VP **−11**, so the USSR is well behind and should be taking
shots.

```
SOUTH AMERICA
 *Argentina   US 2  SU 0  stab 2  [US]
 *Brazil      US 2  SU 0  stab 2  [US]
 *Venezuela   US 3  SU 0  stab 2  [US]
 *Chile       US 0  SU 0  stab 3  (empty)
  Colombia    US 0  SU 4  stab 1  [USSR]
```

| Mode | Bot | Best target |
| --- | ---: | --- |
| **coup** | **2.96 VP** | **Argentina** 2.96, Brazil 2.80, Angola 2.57 |
| influence | 1.52 VP | greedy multi-country; Venezuela 2 pts = 1.25 |
| realignment | 1.36 VP | Argentina 1.36, India 1.27 |

**Verdict: correct.** "Argentina is the obvious coup, especially with
empty Chile."

Why it holds up, and why the alternative is worse than it looks: every
South American battleground is US-held, so the USSR pays **2 Ops per
influence point** there — 4 Ops buys two points in Venezuela, not four.
Couping pays no such tax. Argentina is the cheapest flip on the board (US
2, stability 2), and **Chile is empty**, so South America is not locked:
take Argentina and the region is live rather than conceded.

This matters beyond the one move. `ops_value` is the max of
best-placement and best-coup, and it is the denominator of every VP
figure in the project. The coup winning 2:1 here is *correct play*, which
means the coup bias is not a scoring error in this position — see below.

## 2. Decision 10 — `coup_target`, 1 Op, USSR, seed 4002 T7 AR6

DEFCON **2**, VP **−11**. Hand: Duck and Cover, Our Man in Tehran.

**Verdict: the target is right.**

The open question is the **amount**, not the target: "a 1-Op coup into
those countries is the best use of an Op, but generally you use 2 or 3
Ops because the 1/6th chance of BG is probably worth more."

So the bot picks the right country and may be systematically choosing the
wrong *size* of coup — spending one Op where two or three buys the chance
of the bigger result. That is a different defect from the one this
decision was chosen to test, and it is not visible in a target ranking at
all.

## 3. Decision 8 — `action_round_play`, US, seed 4001 T7 AR3

DEFCON **2**, VP **−15**. Hand: OPEC, Romanian Abdication, OAS Founded,
Arms Race, Nuclear Subs, NORAD.

```
 1. OAS_Founded            35.71   <- the bot plays this
 2. Arms_Race              35.40
 3. NORAD                  35.40
 4. Nuclear_Subs           25.00
 5. Romanian_Abdication     3.32
 6. OPEC                  -14.16
```

**Verdict: correct.** "OAS into Chile is the obvious decision" — and the
bot does play OAS Founded.

Two things remain. **Where does the influence go?** OAS Founded places in
Central or South America, and the card being right does not mean the
placement is; Chile is the answer and the bot's target is unverified.
And look at 2 and 3: **Arms Race and NORAD score 35.40 to the bit.** Both
3-Ops US cards whose events the US can play safely, so the score
collapses to the Ops and the engine's list order decides. The
indifference pathology is visible in the same position that the bot gets
right.

---

## Decided: `ops_value` should be influence only

Your call, and it settles the yardstick question. `ops_value` is
currently `max(best placement, best coup)`, and the coup wins at every
Ops level — 1.11 VP against 0.24 at one Op. Since `vp_value` is
`vp_era * ops_value(1)`, the price of a VP, and therefore every
VP-denominated term in the bot, is anchored to **whichever cheap African
coup happens to be available**. It moves when DEFCON changes or a
1-stability country fills.

Pricing it on placement only makes the yardstick a property of the
position rather than of one opportunistic target. Queued, and it needs a
gate.

## Pending measurement: how full is the board by turn 8?

Your expectation: **90-95% of battlegrounds controlled at the start of
turn 8**, and anything under 80% means something is wrong. Running.

The prediction behind it is that the bot "doesn't fill empty BGs enough
and gets into BG ops wars" — so if the number comes in low, the two are
the same defect seen from opposite ends.

---

## What three correct answers tell us

The bot chose correctly in all three, which is not the null result it
looks like. These were picked as the closest calls in the corpus, so they
are where the ranking is working hardest — and it is getting them right.

That relocates the problem. The defects are **not** in choosing between
the options a decision offers. They are in:

- the **size** of a coup, not its target (Decision 10),
- the **placement** after a card is chosen, not the card (Decision 8),
- the **ties**, where the ranking expresses no preference at all
  (Arms Race and NORAD, visible in Decision 8),
- and the **strategic** level a single decision cannot show — filling
  empty battlegrounds, and not fighting break wars you lose.

None of those is visible in "which option did it pick". Which argues the
next pack should ask about *sequences* rather than single choices.
