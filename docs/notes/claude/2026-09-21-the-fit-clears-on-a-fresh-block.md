# The fit clears on a fresh block: +0.054 [+0.031, +0.078]

2026-09-21. Run 35614516089, `fit-fresh-base` / `fit-fresh-on`, block
68000-69023 against `bc5ef93`, paired, waves on. The independent reading
the old block could no longer give
([why](2026-09-21-fit-vs-bc5ef93.md)).

| arm | score | one-sided 95% | seeds | US seat | USSR seat | signed VP | nuked US/USSR |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `fit-fresh-base` (fit off, as shipped) | 0.480 | [0.463, **0.497**] | 1021 | 0.539 | 0.422 | -2.37 | 20/26 |
| `fit-fresh-on` (`country_vp_scale` 2.795) | **0.534** | [**0.517**, 0.551] | 1023 | 0.580 | 0.489 | -2.37 | 22/24 |

**Paired: +0.054 [+0.031, +0.078] over 1020 shared seeds.**

**The lower bound is +0.031, which is above zero.** The rule
pre-registered in the arm's own `context` before dispatch says that makes
this a measurable gain and step 4 a normal change.

Seed counts are stated rather than rounded: four shards lost exactly their
last game to the gap detector, so the arms are 1021 and 1023 of 1024 and
the paired reading is over the 1020 seeds **both** arms finished. No shard
is MISSING -- every stall still wrote and pooled its partial report, which
is the machinery working.

## The base arm is measurably WORSE than the anchor, and that is the story

`fit-fresh-base` reads 0.480 [0.463, 0.497]: its upper bound is **below**
0.500, so the bot as shipped is measurably weaker than `bc5ef93` on this
block. `fit-fresh-on` reads 0.534 [0.517, 0.551], measurably stronger.

**The fit moves the bot from measurably worse than the strongest anchor to
measurably better than it.** Both seats gain (US +0.041, USSR +0.067) and
the USSR gains more, the same pattern both earlier readings showed.

## The two blocks agree

| block | paired | seeds | SE |
| --- | --- | ---: | ---: |
| 64000-65023 | +0.023 [-0.001, +0.047] | 896 | 0.0146 |
| 68000-69023 | **+0.054 [+0.031, +0.078]** | 1020 | 0.0146 |

The difference between them is 0.031, which is **1.5 SE** -- ordinary
sampling error. Both point positive; the fresh block clears the line and
the old one missed it by a thousandth. Inverse-variance pooled over both
blocks: **+0.038 [+0.022, +0.055]**.

That is the shape you want from a replication. It is worth saying what it
is *not*: the old block is not evidence against, and this one is not a
lucky draw. They are two samples of the same quantity, 1.5 SE apart, and
the pooled estimate is what either alone was estimating.

## What this unblocks

Step 4 of [the VP rebuild plan](2026-09-20-finishing-the-vp-rebuild.md) --
delete `importance`'s un-fitted branch, `country_value`'s un-fitted half,
and the `battleground` / `control` fields, and default `country_vp_scale`
to 2.795. The board-value layer goes from 10 live weights to 8 and loses a
whole parallel implementation of the same four terms.

Two things that change are worth stating before anyone starts:

- **The parity corpus WILL change.** It is the exactness oracle for a bot
  whose value function is being replaced, so it has to be regenerated, and
  the commit doing it should say so plainly rather than let a 401-record
  diff look like an accident.
- **The gate will NOT be a dead heat.** Every gate in this session's
  earlier work was `WARN identical`. This one moves play by design. The
  anchored arms above are the evidence, not the corpus and not the gate.

**Not done here.** The evidence is sufficient; whether to spend it is the
maintainer's call, and the change is one-way in a way the deletions before
it were not -- `battleground` is not inert, it is the current pricing.

## Footnote: `--max-seconds` still has not fired

Four shards stopped early in this run and **all four were the gap
detector**, at 113-134 minutes, under the 150-minute ceiling. Each lost
exactly its last game, which is the failure `benchmark.py`'s own comment
describes: with four workers and one game left, the gap between finishes
is one whole game.

So the wall-clock ceiling added in PR #32 remains **untested in anger**.
It cost nothing and it is still the right backstop -- a job timeout writes
no report at all -- but nobody should cite this run as having exercised
it.

What did pay off immediately is the smaller change beside it: the log now
names the abandoned games. `STALLED: 1 game(s) never finished: 68226/USSR`
is the whole diagnosis, free, in the job log.
