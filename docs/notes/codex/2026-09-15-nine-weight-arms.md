# 2026-09-15 — Nine weight arms: re-runs plus six halvings (readings, do not ship)

Run 35022058789, all nine arms `success`, 128-seed main + 64-seed held each
(256 + 128 games). Logs: `logs/exp-20260915-nine-arm/`. Pooled is
games-weighted (2x main + held). Halfwidths ~+/-0.04 main, ~+/-0.06 held:
nothing here is significant; these are evidence, never calibration.

| Arm (weight) | Main | Held | Pooled | Prior read |
| --- | --- | --- | --- | --- |
| region-par-rerun (1.0) | 0.498 | 0.535 | 0.510 | 0.523/0.496 -> 0.514 |
| access-contested-off-rerun (0.0) | 0.539 | 0.492 | 0.523 | 0.498/0.539 -> 0.512 |
| coup-discount-flat (1.0) | 0.516 | 0.422 | 0.485 | wide, inconclusive |
| access-half (0.75) | 0.479 | 0.484 | 0.481 | first reading |
| control-half (0.75) | 0.502 | 0.449 | 0.484 | first reading |
| margin-bg-half (0.125) | 0.553 | 0.508 | 0.538 | first reading |
| margin-country-half (0.025) | 0.484 | 0.539 | 0.502 | first reading |
| progress-half (1.4) | 0.547 | 0.434 | 0.509 | first reading |
| scoring-rival-half (0.5) | 0.490 | 0.570 | 0.517 | first reading |

## Reading

- **access-half: do not shrink.** Both halves below par (0.479/0.484),
  the only arm with agreeing negative halves. Keep 1.5.
- **margin-bg-half: most promising shrink.** Both halves above par
  (0.553/0.508, pooled 0.538). Candidate next bisect at 0.0625 -- but
  the rebuild computes this credit per future scoring turn anyway, so
  the buyer for this result is the rebuild, not a weight commit.
- **region-par, access-contested-off: second consistent reads.** Pooled
  0.510 and 0.523 with halves flipping between runs -- free, not better.
  Feeds the rebuild (par factor-1, contested-zero) and the bisect
  follow-up, respectively.
- **coup-discount-flat, progress-half: halves violently disagree**
  (0.516/0.422, 0.547/0.434). No conclusion; do not act. A 256-seed
  re-run could settle coup-discount if the question matters.
- **control-half, margin-country-half, scoring-rival-half: inconclusive
  leans** (pooled 0.484/0.502/0.517, halves split). No action.

## Ship decisions

None. No arm ships as calibration; the factor-1/margin questions belong
to the rebuild, and the shrink candidates need their next bisection
before anyone quotes them.
