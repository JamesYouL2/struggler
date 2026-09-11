# Part B: the three worth doing first

Of the twelve in `docs/POSITION_PACK.md`, these three each answer a
question that is currently blocking something. The other nine are useful
but redundant with work already in progress.

---

## 1. Decision 7 — `ops_type`, 4 Ops, US, seed 4001 turn 7 AR1

**Influence, Coup or Realignment with a 4-Ops card.**

The highest-value question in the pack, because this decision *defines the
bot's exchange rate*. `ops_value` is the max of the best placement and the
best Coup, and it is the denominator of every VP figure in the project —
`vp_value`, `game_value`, the sentinel bounds, `military_credit`, the
region calibration you just supplied. On the measured board the Coup wins
at every Ops level (1.11 VP against 0.24 at one Op), so **a systematic
bias toward Coups here silently reprices everything.**

If the bot is taking Coups where you would place, the yardstick is wrong
and so is every number I have measured against it tonight.

## 2. Decision 10 — `coup_target`, 1 Op, USSR, seed 4002 turn 7 AR6

**Which country to Coup with a single Op.**

You said the 1- or 2-Op Coup into Nigeria, Angola or Zaire is often the
best play on the board — and that is exactly the play that sets
`ops_value(1)`, and therefore the price of a VP, for every other decision
in the position. One cheap African target anywhere on the map moves the
whole exchange rate.

So this asks two things at once: is the *target* right, and is a 1-Op Coup
really worth what the bot thinks (1.11 VP, against 0.24 for the best
placement)?

## 3. Decision 8 — `action_round_play`, US, seed 4001 turn 7 AR3

**Which card to play.**

The most frequent decision in the game, and the one with the worst known
pathology: **19 of the 26 positions where the bot scores its top two
identically are card plays.** It spends equal-Ops own-side cards in
whatever order the engine lists them, rather than burning its least
valuable event first.

This one is close rather than tied, so it tests the ranking where the
ranking is actually doing work — and it is the decision kind the tie-break
fix will land in, so it doubles as a before-picture.

---

**If you only do one, do Decision 7.** It is the only one that can tell me
the measurements themselves are mis-denominated, and everything else in
the queue is calibrated against them.
