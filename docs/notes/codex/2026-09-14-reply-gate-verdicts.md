# 2026-09-14 — Reply-gate verdicts: B ships, the fixes stay

## Verdicts (all PASS, pooled arm score vs base over 128 seeds)

Pass = one-sided 95% upper bound >= 0.500 (not measurably worse).
Gate logs: `logs/gates-20260914/<run>/`.

| Arm | Run | Score | Upper bound | Halves (base/held) |
| --- | --- | --- | --- | --- |
| B coup-only | `34913877037` | 0.498 +/-0.026 | 0.541 | 0.539 / 0.457 |
| no-q1 | `34913881138` | 0.492 +/-0.028 | 0.538 | 0.461 / 0.523 |
| no-q2 | `34913885256` | 0.492 +/-0.025 | 0.534 | 0.504 / 0.480 |
| no-f5 | `34913888786` | 0.498 +/-0.002 | 0.501 | 0.500 / 0.496 |

Nuclear losses at the usual rate in all four (31-37 of 256).
The maintainer's worry -- that the gate would push reply down while reply
is really underestimated -- did not materialise: nothing failed.

## Reading

- **B is a dead heat.** The halves point opposite ways (0.539 vs 0.457),
  which is noise, and the pool says "not worse". No strength gain is
  claimed; the case for B was always the behaviour (coup answers priced),
  and the gate clears it as free.
- **no-f5's interval is the finding: +/-0.002.** The horizon fix barely
  moves any self-play outcome -- the positions where it bites (final
  action, extra round) are rare in self-play but real. That cuts both
  ways (see below).
- The reply-model-0 experiment (0.431, FAIL) remains the evidence the
  reply search matters; these four arms only say no single piece of it
  is load-bearing for strength.

## Ship decisions

- **B ships.** Pre-approved, gate shows no regression. Rebased onto main
  (clean: no `src/` delta between `930dfdc` and main), merged, corpus
  recaptured (the arm changes rankings), full suite green.
- **no-q1 / no-q2 / no-f5 do NOT merge.** A passing ablation means the
  fix is *free*, not that it is *useless*. Q1 (unreachable/prohibited
  replies), Q2 (doubling-rule cost arithmetic) and F5 (replies after the
  last move) are rules-correctness fixes; self-play strength cannot
  validate correctness, and no-f5's +/-0.002 is exactly why -- the gate
  cannot see the positions the fix is for. The fixes stay; the ablation
  branches close.
