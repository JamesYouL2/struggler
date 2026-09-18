# 2026-09-17 — Audit F1–F5 gate: correcting the consumer is a wash

Run `35289152196`, decide=1 vary=0, `0e65f1e` vs `d541db2` (main before the
audit fixes). Candidate and base differ in exactly the five correctness
fixes and the schedule masses they change.

```
  full-vs-base: 57 seeds, score 0.518, signed VP 0.85, nuclear losses 22
  full-vs-held: 56 seeds, score 0.446, signed VP 0.04, nuclear losses 20
  ok strength: pooled score 0.482 +/- 0.028 over 113 seeds,
     one-sided 95% upper bound 0.528, needs 0.500
ACCEPTED
```

**The corrected masses are not measurably different from the wrong ones.**
Point estimate a hair below par, the two samples disagreeing in direction
(0.518 against 0.446) at a size where that is noise. ACCEPTED here means
what it always means: not measurably worse.

## What this settles about the wrong-consumer question

The maintainer's reading of the earlier factor-2 verdict was that a buggy
consumer measuring as a gain is a *better* sign than a correct one, because
an effect that survives a corrupted carrier is in the structure rather than
in the details. This run supports that, and bounds it.

It supports it because the alternative was live. If the bugs had been
load-bearing -- the China phantom pattern, where the rules-correct version
is 2.5 points worse than shipping nothing and the rules-incorrect one is
5.5 better (`../claude/2026-09-13-the-phantom-beats-the-correct-china-card.md`)
-- then removing them would have taken the gain with them. It did not. What
carried the factor-2 reading was the structure: real occurrence
probabilities replacing the flat 0.5/0.5/1.0 assumptions, and the loss of
the retention double-count. Both survive being implemented correctly.

The measurement says WHY it survived, too. The fixes left the total
occurrence mass where it was -- 8.696 to 8.693 per position over 70 corpus
positions -- and moved 0.39 of it from bucket 3 to bucket 2:

| bucket | before | after |
| --- | ---: | ---: |
| 1, this turn | 0.9202 | 0.9202 |
| 2, this cycle | 1.8866 | 2.2728 |
| 3, next cycle | 3.8172 | 3.4272 |
| 5, final scoring | 2.0722 | 2.0722 |

The factor-2 gate compared against a model with **no bucket-2/bucket-3
distinction at all**. The bugs lived in a dimension the comparison could
not see, which is exactly the condition under which "the buggy version won"
is good news rather than a warning.

It bounds it because the two readings do not compose into a result.
Wrong-vs-old was +0.043 and corrected-vs-wrong is -0.018, so
corrected-vs-old is something near +0.025, and neither leg is significant
on its own sample. The defensible sentence is: **the factor-2 rebuild is
not measurably better than the two-state model it replaced, nor worse, and
it is correct, which the old one was not.** The last clause is why it
ships; F1 alone (Yuri never paying its VP in ordinary play, including the
20th point that ends the game) is a rules defect whatever the gate says.

## What it does not settle

- Which of F2 and F3 moved the number. They pull opposite ways -- F2 takes
  mass off South East Asia, F3 puts it into the near term -- and a pooled
  0.482 is consistent with both being small and with the two cancelling.
  Separating them needs one branch per fix and is only worth it if
  something downstream depends on the answer.
- Whether the knobs that multiply the moved mass are still set right.
  `scoring_rival` multiplies buckets 1+2, whose base grew 16% for a card we
  do not hold, and `scoring_hand` multiplies the same term for one we do,
  whose mass did not move at all. Three arms are running
  (`scoring-rival-half`, `scoring-rival-quarter`, `scoring-hand-premium`).
- Anything about accumulated drift, which is a different instrument and is
  reading measurably behind v0.2.1. See the drift note.

## Clock

`took 69m58s`, against 50m17s and 53m11s for the two earlier CI gates. Do
not read that as "the fixes made games longer": those runs had a different
base AND a different candidate, so the comparison is not controlled. The
corpus growing 385 -> 485 records on the same recapture is suggestive of
longer games and is the thing to measure if anyone wants the answer.

The run also printed `budget: under 60m; OVER` and a WARN asking whether
anything else was using the cores, while the contention check said the
clock was clean. Both lines were right about what they measured and the
comparison was meaningless: four vCPU against a budget set on eight. Fixed
in `f6cda64` so the log says so instead of gate.yml's header saying it.
