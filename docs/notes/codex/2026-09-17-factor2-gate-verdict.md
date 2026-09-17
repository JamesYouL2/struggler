# 2026-09-17 — Factor-2 consumer gate: the real masses are ACCEPTED

Run `35240944246`, decide=1 vary=0, `5cf67af` vs `18abdba` (main tip).

```
== 4. acceptance
acceptance:
  full-vs-base: 38 seeds, score 0.572, signed VP 1.21, nuclear losses 12
  full-vs-held: 37 seeds, score 0.514, signed VP 1.73, nuclear losses 5
  ok strength: pooled score 0.543 +/- 0.036 over 75 seeds,
     one-sided 95% upper bound 0.602, needs 0.500
ACCEPTED
```

The first VERDICT-bearing gate of the rebuild: every earlier slice was a
dead-heat safety check, and this one carries a favourable point estimate
for the schedule's real masses (the must-play certainty, the recycle walk,
the loss of the retention double-count) against the old two-state model.

**Correction (2026-09-17, from the correctness/speed audit).** The title
said STRONGER and the body read the run as "the masses model won". Neither
follows from this line. Rule 3 of the acceptance is *not measurably worse*:
it accepts when the one-sided 95% **upper** bound reaches 0.500
(`benchmark.py`, `confidence = 1.645`), and 0.602 clears it easily. The
bound that would establish superiority is the lower one, 0.543 - 1.645 *
0.036 = **0.484**, which does not reach 0.5 -- and early stopping gives a
second reason not to read a point estimate as a result. What this run
says is: the factor-2 consumer passed the project's regression screen with
a favourable point estimate. It neither proves improvement nor validates
the schedule's probability accounting -- and the accounting was in fact
wrong in two places the audit found afterwards (the Southeast Asia
one-shot counted twice, the exhausting deal dropped from both walks; see
2026-09-17-correctness-speed-audit.md F2/F3).

Per region and quirk: Blockade priced 43/43 in the [0.92, 1.00] band
(never for Ops), Socialist_Governments 43/75; nuclear losses 17/150 at
the usual rate. DEFCON-1 losses excluded per the usual 21 games.

Gate discipline: ACCEPT at decide=1 -- no further confirmation needed
for the factor-2 consumer; the calibration contingency from the goal
does not trigger. Next slice proceeds: the potential-delta rewrite
(design in 2026-09-17-potential-delta-design.md).
