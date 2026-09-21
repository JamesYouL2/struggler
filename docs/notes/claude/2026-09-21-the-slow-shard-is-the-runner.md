# The slow shard is the runner, not the seeds

2026-09-21. Experiments run 35614516089 (`fit-fresh-base` / `fit-fresh-on`
against `bc5ef93`, 1024 seeds each, eight 128-seed shards, wave 1 = shards
0-3) had both arms' **shard [1/8]** still running at two hours while every
sibling had finished between 32 and 71 minutes. `fit-fresh-on [1/8]` took
1h52m; `fit-fresh-base [1/8]` ran 2h14m and then exited on the stall
timeout.

This is the second time. `fit-fresh-base`'s own `context` records the first:
on the 64000-65023 block, `fit-bc-base` shard **5** of 8 ran 1h51m on one
dispatch and hit the runner's 180-minute ceiling on the next, leaving that
paired reading stuck at 896 seeds.

The natural reading -- and the one the earlier note's phrasing invites, by
calling it "that block's slice" -- is that some seed ranges contain long
games. That reading is wrong, and this is the measurement that says so.

## The seeds do not explain it

Every seed of all four wave-1 blocks, played locally as a whole self-play
game, timed, seven at a time on an idle 8-core box:

| shard | seeds | local total | local mean | local max | CI `base` | CI `on` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `[0/8]` | 68000-68127 | 4910 s | 38.4 s | 83.6 s | 31.8 min | 43.7 min |
| `[1/8]` | 68128-68255 | **4168 s** | 32.6 s | 93.2 s | **134+ min** | **112.6 min** |
| `[2/8]` | 68256-68383 | 5539 s | 43.3 s | -- | 70.9 min | 54.8 min |
| `[3/8]` | 68384-68511 | 4990 s | 39.0 s | -- | 48.8 min | 60.8 min |

The shard that took two hours on CI is **the lightest of the four**. The
heaviest, `[2/8]` at 5539 s, finished mid-pack. Local work spans 1.33x
between the best and worst block; CI duration spans 4.5x, and the two
orderings are not merely uncorrelated, they are inverted at the extreme.

There is also no pathological game hiding in the block. All 128 seeds
reached turn 10, the slowest took 93.2 s, and the distribution is the
ordinary long tail -- no hang, no search blow-up, nothing that a prune would
catch.

## So it is the runner

A hosted runner's speed is not a constant. The same nominal `ubuntu-latest`
varies by CPU generation and by whatever else shares the host, and a 4.5x
spread across eight jobs doing near-identical work is what that looks like.
Nothing in the repository can make a slow runner fast.

**Both arms drawing a slow runner on the same index is the part that looks
like a pattern, and one run cannot tell coincidence from cause.** The
evidence against "index 1 is cursed" is that the previous incident was index
**5**, on a different block. Two incidents, two different indices, in each
case both arms of the pair: more consistent with a slow host being shared by
the jobs scheduled together than with anything about the index. Not proven.

## What already protects against it, and what does not

The `run-shard` action already carries `--stall-timeout 1200 --max-seconds
9000`, both added after the first incident. They worked: `base [1/8]` exited
on the stall rather than being killed at the job's 180-minute ceiling, so a
partial report exists and the shard's finished games still count. That is
the designed degradation and it is the reason this cost a slice rather than
a dispatch.

What they do not do is make the reading complete. A stalled shard is a
PARTIAL reading, so the arm lands short of 1024 seeds again -- which is
exactly the failure that made this fresh block necessary in the first place.
Guarding the blast radius is not the same as not being hit.

## The lever is shard size, and it is the only one

Per-shard work is the one term this repository controls. At 128 seeds the
median wave-1 shard took ~55 minutes and the worst took 134+; the ceiling is
180 and the stall abandons at 150. There is no headroom for a 3x runner.

At **64 seeds** the same 3x-slow runner finishes in ~70 minutes, comfortably
inside both limits, and the median shard drops to ~27. The price is 16 jobs
an arm instead of 8, which the 256-shard matrix cap accommodates for a
two-arm run.

That is a knob the arms already have (`"shard": 64`), so this needs no code
-- it needs the default reconsidered for anchored arms against slow anchors,
where a game costs more than self-play does. It is deliberately not changed
here: one run is not enough to retune a default, and the next anchored arm
should set `shard: 64` explicitly and see whether the tail disappears.

## What NOT to do

Do not go looking for slow seeds. That hypothesis has now been tested
directly and the lightest block was the slowest shard. Do not add a prune
for long games either -- every seed finished, and the 2026-09-20 note
already established that the stall timeout measures the gap between finishes
at the drain rather than any one game's length.
