# Correction: the turn-10 worst card is about one Op, not eight

The −8.55 Ops reported above was a mean over ten observations dragged by a
single one. Over 20 turn-10 hands:

| | Worst card in hand |
| --- | ---: |
| **Median** | **−1.26 Ops** |
| Mean | −5.33 Ops |

The outlier is **Duck and Cover at −77.97 Ops**, held by the USSR at
DEFCON 2, where playing it degrades DEFCON to 1 and loses the game. Not a
sentinel leak -- `is_certain` is False on all 20 -- but the planner
pricing a near-certain loss at about 78 Ops, which is defensible.

So the earlier claim that turn-10 China clears the maintainer's 8-Ops
crossover was an artifact. On the median the gap is about **4.3 Ops**,
which does not clear it.

What is actually there is more useful than the number that was wrong.
**China's late value is bimodal.** Usually the worst card costs about an
Op and China beats it by a few; occasionally the worst card loses the
game and China is worth almost anything. A mean over those two regimes
describes neither, and the bimodality is exactly the safe-window
structure: China's worth at the end is *insurance against being forced to
play a trap*, which explains "100% of the time" better than an expected
value does.

**The safe-window list is confirmed from play, not from theory.** The most
frequent worst turn-10 holdings are Duck and Cover (3), Lone Gunman (2)
and Grain Sales to Soviets (2) -- three of the eight cards the maintainer
named -- then Marine Barracks Bombing, Aldrich Ames Remix, Che, OPEC and
The Voice of America. Their verdict on the list: "these are all basically
unplayable. I think Marine is the only one that isn't just dreadful, and
it's still bad."

Caveat on the measurement: 24 seeds gives only 20 turn-10 observations,
because most games end earlier. Enough to see the shape and to kill the
mean, not enough to pin either mode.
