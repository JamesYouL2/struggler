# How to look at things

The gate for any value-function change is `scripts/gate.sh [base-ref]`
(runs from a snapshot of HEAD; base defaults to HEAD~1; the anchor run
needs GATE_ANCHOR=1 and is parked until the Rust speed-up lands).

**Its exit status is the verdict.** It used to print numbers and exit 0
whatever they said, so "the gate passed" only ever meant "the gate ran",
and these notes have used the word wrongly more than once. The rules are
in `benchmark.acceptance` and are deliberately asymmetric: no more nuclear
losses than chance explains, two samples over disjoint seeds and 150+
finished games, and a pooled score whose one-sided 95% upper bound reaches
0.500. A change is blocked only when the games say it is *worse*. At 32
seeds most real changes are not measurable in either direction, and a rule
that demanded proof of improvement would block all of them.

Mind the exit status when you invoke it: `scripts/gate.sh | tail` gives you
tail's status, not the gate's. Read the printed verdict.
