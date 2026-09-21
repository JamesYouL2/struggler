# Handoff, 2026-09-21: what landed, what is in flight, and what to tell the next model

Written at the end of a long session. The first two sections are ordinary
handoff. The third is the one worth reading: the mistakes this session
actually made, in the order they are likely to be made again.

## What landed (PR #32, merged as `ee17511`)

| | what it does | measured |
| --- | --- | ---: |
| shard cache | a re-dispatched shard replays nothing | 12 s against 115 s |
| sequential waves | a decided arm stops at half its seeds | final interval +2.0% |
| wall-clock ceiling | a doomed shard reports instead of vanishing | — |
| three exact speedups | `place` written out, two clamp sites | **-6.1%** |
| neighbour-diff cache | the four-point repeat in `_delta` | **-2.1%** |

Detail in [the cheaper-readings note](2026-09-21-cheaper-readings.md). The
gate on that PR is the strongest evidence in it: **150 games, pooled score
0.500 +/- 0.000, and the gate's own `WARN identical: every game was a dead
heat`** -- which is what a bit-identical optimisation should produce, and a
stronger statement than the parity corpus, since the corpus ranks one
decision per record and cannot see compounding.

## What is in flight

**Run 35614516089**, `fit-fresh-{base,on}`, block 68000-69023 against
`bc5ef93`, paired, waves on. The decision rule is pre-registered in the
arm's own `context` in `.github/experiments.json` and must not move once
the number is visible.

Two things to look at when it lands, in this order:

1. **Did `--max-seconds` fire?** At 16:27 UTC both `[1/8]` shards were at
   100 minutes against siblings' 32-71m, so the 150-minute ceiling was
   about to get its first real test. If a shard reports `expired`, its log
   names the abandoned seeds and its partial report still pools -- which
   would mean the `fit-bc-base [5/8]` class of total loss is now
   recoverable. If a shard instead reaches the 180-minute JOB timeout, the
   ceiling is set wrong and that is a defect.
2. **Did the interim stay its hand?** Expected NOT decisive: ~+0.023 at 512
   paired seeds is about z = 1.2, well under the 2.373 bar. An early stop
   means the boundary is wrong and nothing downstream should be trusted.

**A finding already visible in it:** both arms are slow on the SAME shard
index, and the two arms are different bots (fit off against fit on) playing
the same seeds. So the slow slice is a property of the DEALS, not of the
configuration -- the same conclusion the old block's shard 5 pointed at,
now with a control.

## Open, not started

- The `ruff FURB136` cleanup (3 findings where ruff argues to restore the
  `max`/`min` builtins that were deliberately removed; the fix is
  statement-form clamps, which is `country_value`'s existing house style and
  does not trip the rule). **The maintainer said leave it.**
- The refit at current main, if the fresh block also reads at or below zero.
  `fitted_country_weights.json` has `source_revision` `598e4d1`, two
  structural changes stale.
- `git push origin anchor-2026-09-12` and
  `git push origin --delete exp/access-leak-isolation`: the proxy denies
  tag creation and branch deletion (403 on the write path), so these need a
  human.

---

# What to pass along to a weaker model

Ordered by how much damage getting it wrong does here.

## 1. Profile to find the work; time without the profiler to price it

cProfile charges roughly a microsecond per call, so it **systematically
over-rewards any change that removes calls** -- which is most optimisations.

This session reported "5.9%" for three speedups from a profiled run. Timed
unprofiled it was 6.1%, which is fine; but the next change read **18% fewer
`country_value` calls and 0.8% of wall under the profiler, and 2.1%
unprofiled**. Quoting the profiled number would have overstated it 3x.

**This was discovered twice on the same day by two separate pieces of
work** -- see [the enum note](2026-09-21-enum-attribute-reads.md), which
found the profile's own-time column overstating a hot spot "about three
times" for the same reason. Two independent discoveries is the recurrence
signal this repo acts on.

Practice: profile once to rank the work. Then change one thing, and time
`N` whole games with no profiler attached, best-of-two, on an idle box.
**Report the unprofiled number.**

## 2. Float regrouping is not a refactor

Made **twice in one sitting**, both times while removing builtin calls from
a hot loop:

```python
(1 + 3 - 4) + 0.1     # 0.1
1 + ((3 - 4) + 0.1)   # 0.09999999999999998
```

with an `int()` truncation immediately downstream. And separately: caching
`sum(diffs)` where the caller adds each diff into a running total is a
different float from adding them in sequence.

Rankings here are decided by strict comparison, so one ulp is a changed
move. `evaluator.py`'s header says this about multiplication; it is just as
true of addition, and **a profile is exactly the context that invites it**.
Cache the addends, never the sum. The gate is
`tests/test_parity_corpus.py`; run it before believing any optimisation.

## 3. A test that passes with the defect present gates nothing

Every gate written this session was checked by putting the defect back:

- removing the ceiling's clamp fails 5 of 9 stall tests;
- shrinking the neighbour cache key fires the `CHECK_SNAPSHOT` recompute;
- re-adding the duplicate `env:` fails the YAML test **naming line 146**,
  the same line GitHub named.

If you cannot make your new test fail, you have not written a test.

## 4. Verify the way the consumer reads, not the way your tool reads

A duplicate `env:` key parsed fine under PyYAML (which silently keeps the
last) and passed every assertion in the workflow tests. GitHub refused the
whole file and the shard job never ran.

**Your parser is not the runner's parser.** The tests now load workflows
with a loader that refuses repeated keys.

## 5. Put the guard in the path that actually runs

`wave_verdict.py` fails open on every unreadable path -- a careful design,
thoroughly unit-tested. It never ran: `pool_reports.py` exited 2, `set -e`
killed the step first, and `run2` was skipped. **A total wave-1 failure
silently cancelled wave 2, the one outcome the design forbids.**

The guard was in the script and the script never ran, which is the worst
place for a guard to be. Check the calling context, not only the callee.

## 6. Smoke the machinery before a real run rides on it

A 4-seed dispatch found both of the above in about ten minutes. A
1024-seed dispatch would have found them two hours in, or not at all.

Then prove the thing you cannot prove from one run: a **third**,
byte-identical dispatch confirmed the cache actually *restores* (12 s
against 115 s, no save step). A cache that saves and never hits looks
identical to a working one from a single run.

## 7. Do not move a pre-registered rule after seeing the number

The fit-vs-`bc5ef93` reading came back **+0.023 [-0.001, +0.047]**. The
rule, written before the number was visible, was "lower bound above 0
deletes `battleground`; at or below, do not." It read **-0.001**.

So `battleground` stayed -- not because a thousandth means anything, but
because a rule that moves once you can see the number is not a rule. The
temptation is strongest exactly when the gap is smallest.

## 8. Waiting is sometimes the action, and a cancel can teach nothing

I told my future self to cancel a shard that had run 141 minutes, then
reversed it: the previous 15-of-16 pooling already read
+0.023 [-0.001, +0.047], and cancelling would reproduce **that exact
number** while losing the only shard that could change it. A job timeout
destroys the same data a cancel does, so acting early bought nothing.

Before killing a run, ask what the surviving data would say -- and whether
you already have it.

## 9. Correct your own numbers plainly, and do not let a title outrun the evidence

Two corrections this session, both to things already merged:

- a note claimed "three independent demonstrations" that seed blocks move a
  level 0.02-0.03. Recomputed from the published halfwidths: the two gaps
  are **1.7 and 1.2 SE** -- ordinary sampling error, in a note whose
  subject was that exact failure;
- `CLAUDE.md`'s suite timing now records the CORE COUNT, because 3:49 on 4
  cores and 5:30 on 8 do not divide into a speedup.

The related failure, one day earlier, was a note titled *The intransitivity
was the access scale leak* whose own body said the inference was
confounded. The disambiguating arm returned +0.011 [-0.007, +0.029]. State
in a title only what you would defend without the paragraph under it.

## 10. Small, cheap habits that repeatedly mattered

- **Check whether the optimisation is already taken.** `route_weight` and
  `route_decay` were already `lru_cache`d; `VALUE_RADIUS` was already 2.
  Both were nearly claimed as findings.
- **Do not reformat a file you are appending to.** A `json.dumps(indent=1)`
  round-trip rewrote 700 lines of `experiments.json` and buried a 21-line
  change. Insert by text.
- **A cache in a hot path needs the key to carry everything the value
  reads.** That is shape 6 in `bug-shapes.md`, shipped twice. The neighbour
  cache is keyed on exactly the three facts `access` reads, and
  `CHECK_SNAPSHOT` recomputes every hit to prove it.
- **Say when a win is marginal.** The neighbour cache is 2.1% for a ninth
  cache in the most defect-prone function here. It was reported that way,
  with "one revert undoes it", rather than as "18% fewer calls".
