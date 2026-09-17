# 2026-09-17 — The descope gate, and the CI-red pin note that merged with it

Two verdicts, one note.

## Run 35263393016 (gate, `51d9dfb` -- the descope -- vs `18abdba`)

```
full-vs-base: 38 seeds, score 0.572, signed VP 1.57, nuclear losses 12
full-vs-held: 37 seeds, score 0.514, signed VP 1.73, nuclear losses 5
ok strength: pooled score 0.543 +/- 0.036 over 75 seeds,
   one-sided 95% upper bound 0.602, needs 0.500
ACCEPTED
```

Identical numbers to the factor-2 verdict (35240944246) -- which is the
point: the descope's ranking path is bit-for-bit the factor-2 consumer's
shape, so the gate replayed the same games. Branch merged with this
verdict as the branch-approved strength number.

## The CI red that hid under it

`tests.yml` had been failing since `5cf67af` and nothing noticed: three
number-pins in `test_board_potential.py` (41.10647617222223,
11.569636205555554, 4.132012930555556) were hard-pinned to the
retention-urgency dating; the factor-2 masses moved the model, the
properties (delta == board difference exactly, order invariance) never
moved, and `test_scale_discipline`'s AST scanner flagged the naked
`total += mass` additions. The local suite that day was parity-only
full-suite never re-run -- CI caught it, and the lesson is recorded in
commit `7031963` and re-derives the pins per "the property carries, not
the number":

- 14.05555555555555 (Nigeria access charge)
- 39.355555555555554 (order sums)
- 22.494949494949488 (regional urgency equality)

`KNOWN` in test_scale_discipline gains the `total += mass` lines with
the reason attached: a probability is dimensionless, so mass x E[payout]
is scale-carrying by construction.

Full local suite after the re-pins: 897 passed in 4:09.

## Standing

The factor-2 masses are the branch's measured strength advantage over
main (0.543 +/- 0.036; upper bound 0.602). Next work: buy back the DP
cost (design note 2026-09-17-potential-delta-design.md), then the
common-units step, then the residual discount measurement.
