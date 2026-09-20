# Profiling whole games: three exact speedups, and one false reading

2026-09-20. The planner hot spot
([note](2026-09-19-planner-hot-spot.md)) was found on corpus positions.
This profiles whole self-play games, which weight the mix differently: the
reply look-ahead and the event sandbox only appear in real play.

## The profile (two games, seeds 4000 and 4002, 44.0 s unprofiled)

| | calls | self |
| --- | ---: | ---: |
| `country_value` | 8,592,650 | 15.2 s |
| `delta` | 1,902,105 | 11.2 s |
| `max` / `min` (builtins) | 66.8M | 11.4 s |
| `place` | 5,800,517 | 5.5 s |
| `region_vp` | 1,585,533 | 4.8 s |
| `access` | 9,454,057 | 3.5 s |
| `_shuttle_region` | 1,574,296 | (3.2 s cumulative) |

Entry points by cumulative time: `_investment` 62.8 s, `_after_reply`
41.4 s, `_coup_reply` 29.4 s. The ranking's cost is the placement search and
the reply look-ahead, both of which reach the board through `delta`.

## What changed

1. **The clamps in `country_value` are comparisons.** Five `max`/`min`
   builtin calls per call, 8.6 million calls: 66 million builtin calls, a
   tenth of the profile. Identical arithmetic. Self time 15.2 s -> 9.1 s.
2. **`_shuttle_region` is cached with the urgency vector.** It reads that
   vector and the terrain and *nothing about the board*, so a trial
   placement cannot move it -- and `_overrides_for` asked it 1.57 million
   times.
3. **`delta` is memoised on `Position.digest`**, which turns the digest on
   by default.

**On the digest.** It was off because maintaining it costs 6.4% and the memo
it enabled was worth 2.3% -- but that memo covered `delta`'s base-board
*half*, which repeats 1.7 times. Whole `delta` repeats 3.4 times a game.
The honest caveat: **most of those repeats are across decisions, and the
cache is per decision.** Within one decision the hit rate is 22.7%, so this
change is worth about 4% net of the digest's cost, not the 70% the raw
repeat rate suggests. Caching across decisions would capture the rest and
needs `delta`'s dependence on the prepared context (urgency, masses, flags)
enumerated exactly first -- which is bug shape 1, the defect this codebase
has hit seven times.

## Measured, interleaved, committed (four seeds)

| seed | main | this branch | |
| --- | ---: | ---: | ---: |
| 4000 | 23.62 s | 20.28 s | -14.1% |
| 4002 | 20.86 s | 17.85 s | -14.4% |
| 4006 | 27.81 s | 24.73 s | -11.1% |
| 4008 | 19.55 s | 17.22 s | -11.9% |
| **total** | **91.84 s** | **80.08 s** | **-12.8%** |

Every seed ends on the same turn with the same VP in both arms, which is
the check that this is the same bot. Exactness is also pinned by the parity
corpus (every recorded value unchanged) and the suite (1004 passed).

## The false reading, recorded as bug shape 3's ninth instance

The first run of this A/B read **49.98 s against 50.20 s: no speedup.** The
harness ran `git stash` before switching branches to keep the tree clean,
the branch's work was uncommitted, and the stash took it -- so both arms
ran `main`. The tell was there and I ignored it: timings identical to 0.4%
across three seeds is the "standard error of exactly zero" alarm wearing a
different hat. Commit first, and print what each arm is actually running.

## What is left

- `_after_reply` and `_coup_reply` (485k and 364k calls, 34 s and 23 s
  cumulative) are the next target. `_coup_reply` already takes a caller's
  memo; the question is what it misses.
- `place` at 5.8 million calls is the trial-placement loop itself. Fewer
  candidates, not faster placement, is the lever there.
- The planner's hand canonicalisation from the previous note (25,122 ->
  7,317 states) is still unbuilt and is the largest single item known.
