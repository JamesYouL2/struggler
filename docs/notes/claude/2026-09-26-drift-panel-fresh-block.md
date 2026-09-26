# Drift panel on a fresh block: region 2.6 and military 2.0 hold up

Run 36219208156 (`drift.yml` on `main@72b070a`): the five-anchor panel,
1024 seeds each, level readings, no waves, italy/austria books, on the
**fresh block 130000-131023**. It is the first panel since region 2.6
(#50) and military 2.0 (#51) shipped, and the first one off the default
6000-7023 block that every earlier drift run shared (shared seeds link
the series by shared luck). It is also the first drift pooled against
the plan manifest (#55).

| anchor | 2026-09-26, fresh block | 2026-09-24, block 6000 (pre-#50/#51) |
| --- | --- | --- |
| `v0.1.0` | 0.606 [0.590, 0.622] | 0.582 [0.565, 0.599] |
| `07d553a` | 0.580 [0.563, 0.597] | 0.562 [0.545, 0.579] |
| `v0.3.4` | 0.576 [0.560, 0.592] | 0.547 [0.531, 0.563] |
| `v0.2.1` | 0.566 [0.549, 0.583] | 0.538 [0.520, 0.556] |
| `bc5ef93` | 0.562 [0.545, 0.579], 1023 seeds, SHORT | 0.529 [0.512, 0.546] |

**Every verdict is `ok`**: all five lower bounds sit above 0.500, so the
canary has nothing to flag. The run's `failure` status is one bc5ef93
shard (5 of 16) that lost a game. Drift arms carry no reserve, so there
is no spare to backfill it, and the reading is 1023 of 1024. The new
pooling prints that as SHORT instead of passing it silently.

What it does not say: the two columns are on different blocks and a
different main, so their differences (+0.02 to +0.03 against every
anchor) are consistent with the two shipped gains but are not a paired
measurement of them. The gains' own measurements are their gates.

`logs/ci-36219208156/pooled.json`.
