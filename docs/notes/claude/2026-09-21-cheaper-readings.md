# Cheaper readings: a shard cache, sequential waves, and 8% off the bot

2026-09-21. Three ways to get the same answers for less, asked for
together and worth reading together because they buy different things:
the cache removes **repeated** work, the waves remove **unnecessary**
work, and the profile removes **wasted** work. Only the first two are
large.

| | what it removes | typical saving | what it costs |
| --- | --- | ---: | --- |
| shard cache | replaying a shard already played | **up to 100%** of a re-dispatch | a stale reading if the key is wrong |
| sequential waves | the second half of a decided arm | **~50%** of arms that were never close | final interval 1.645 -> 1.678 (+2.0%) |
| the three exact speedups | Python call overhead in the hot loop | **6.1%** of a game | nothing; bit-identical |
| the neighbour-diff cache | the four-point repeat inside `_delta` | **2.1%** of a game | a ninth cache in the riskiest function |

## 1. The shard cache

A benchmark game is `Engine.new_game(seed=...)` driven by two
deterministic players, with chance as a logged CHANCE decision (mandate
#3). So a shard's report is a pure function of the code, the weights, the
opponent, the openings and the seeds -- and replaying it is guaranteed to
reproduce it.

The occasion was concrete. On 2026-09-21 one shard of `fit-bc-base` hung,
and recovering that single 128-seed slice meant re-dispatching all sixteen:
**fifteen shards replayed answers already known to the thousandth**, about
eleven runner-hours. With the cache that re-dispatch is one shard.

`scripts/arm_identity.py` computes the key. The design decision worth
stating is what goes in it:

> THE KEY HAS TO COVER EVERYTHING THAT CAN CHANGE PLAY, or the cache serves
> a stale reading, which is worse than no cache at all.

So it hashes the tree of **`src/`**, not of `src/struggler/bots`. The
gate's notion of "the bot" is the bots package alone -- that is what
`git archive <base> src/struggler/bots` snapshots -- but the **engine**
decides what a play does and `src/struggler/data` holds the cards. A key
on the bots package would survive a rules change and hand back a reading
from a different game. The interpreter version is in the key too, for the
same reason: nothing here has measured float arithmetic across CPython
versions, and leaving it out would be assuming an answer.

`slug`, `shard`, `of` and `compare_to` are deliberately **out** of the key,
which is not merely tidiness: it means an arm can reuse a shard a
*differently named* arm already played. `leak-iso-fixed` and
`fit-intransitive-on` are the same bot on different blocks; had they
shared a block, the second would have been free.

Three things the cache will not do, each gated by
`tests/test_experiment_workflow.py`:

1. **It never restores for an arm with `"logs": true`.** Logs change the
   artifact without changing the report, so they are not in the key -- and
   a hit would therefore serve the report with no logs attached. The key
   cannot express that; the workflow can, and does.
2. **It never saves a shard whose benchmark exited nonzero.** A stall is
   exit 6, which still writes a report -- a *partial* one, over the seeds
   that finished. Caching that would serve half a shard under this shard's
   key forever, and nothing downstream could tell it from a whole one. The
   guard is `if: success()`, and the test asserts it is not `always()`.
3. **It never falls back to a key prefix.** `restore-keys` would serve a
   different shard's report under this shard's name. That is one line away
   at all times, which is why there is a test for it rather than a comment.

`no_cache: true` on dispatch replays everything while still saving, which
is how you check that a replay reproduces a cached reading.

**One hole is known and open**: `arm.json` is now written *outside* the
benchmark step, because `pool_reports.py` reads it for `compare_to` and the
anchor, and a cached shard skips the benchmark. Folding it back in would
silently cost every cached run its PAIRED readings -- the pooled table
would print one fewer section rather than failing. That is the second test
above.

## 2. Sequential waves

Half the seeds, a look, and the other half only for the arms the look did
not settle.

**The look is not free, and that is the whole design problem.** Two chances
to clear a bar are easier than one, so stopping when the data happens to
look good inflates the false positive rate. This repo has already measured
its own version of that: `scripts/validate_early_stopping.py` found the
gate's predictive stop accepts **9.7%** of gates it should reject in the
0.03-0.06 band, and named it correctly as "the optimism inherent to
stopping when the data looks decisive, not a defect in the code".

So the boundary is pre-declared and paid for up front:

| design | interim bar | final bar | cost to the final interval |
| --- | ---: | ---: | ---: |
| one look (today) | -- | 1.645 | -- |
| **O'Brien-Fleming, 2 looks** | **2.373** | **1.678** | **+2.0%** |
| Pocock, 2 looks | 1.875 | 1.875 | +14.0% |

O'Brien-Fleming spends almost no alpha at the interim, so the final
reading is very nearly the unsequential one. Pocock stops more arms early
and pays 14% of the final interval for it. **This repo quotes its final
intervals in notes; it does not want them 14% wider.** Two per cent is the
price of looking, and it is worth it for arms that were never close.

`scripts/wave_verdict.py` computes the boundary by numerical integration
rather than quoting a table, and the tests check it three ways: against the
published O'Brien-Fleming pair (2.373, 1.678), against the published
Pocock pair (1.875, 1.875), and against the alpha the pair actually spends.

Three rules that matter more than the arithmetic:

- **Both directions count.** An arm measured decisively *worse* is a
  result. The rule is on `|z|`.
- **It fails open.** Every unreadable path -- a crashed wave-1 shard, an
  arm with no finished pairs, a partner that never reported, a corrupt
  pooled file -- plays wave 2. A broken interim must cost a wave of runner
  time, never half an experiment's seeds reported as a whole one.
- **A `compare_to` pair is judged on the pair, and moves together.** The
  paired difference is the number the dispatch exists to produce; the two
  arms' own levels are not it. `fit-bc-base` can sit anywhere against its
  anchor while the difference it is the base of is decisive, or the
  reverse. And stopping one end at 512 while the other runs to 1024 would
  leave the comparison on 512 and the arm's own line on 1024 -- two numbers
  in one table, measured on different samples.

**`drift.yml` does not take waves**, and that is deliberate. A drift arm is
a **level** whose number gets quoted ("0.505 [0.489, 0.521], 1024 seeds");
an experiment arm is a **comparison** that stops when the comparison is
decided. Halving a canary's seeds doubles the interval that ends up in a
note. The seeds are the point of the canary.

### What this does not do

It does not make a *close* arm cheaper, and close arms are where this
project keeps finding itself. `fit-intransitive` came back +0.038 [+0.015,
+0.061] -- z = 2.7, which would have stopped -- but `leak-iso` came back
+0.011 [-0.007, +0.029], z = 1.0, which would have run to the full 1024 and
should have. **The saving is concentrated exactly where the question was
easy**, which is the right place for it and also the reason it will not
feel dramatic.

## 3. `delta` and `country_value`: 8.0%, and where the rest is

Timed on an otherwise idle 4-core box, **unprofiled**, best of two over
three self-play games (seeds 4000-4002, italy/austria). Absolute times are
this machine; the proportions are the point.

| | wall | vs baseline |
| --- | ---: | ---: |
| `7929eb5`, before any of this | 64.40 s | -- |
| + the three exact speedups below | 60.50 s | **-6.1%** |
| + the neighbour-diff cache | **59.22 s** | **-8.0%** |

**Unprofiled on purpose.** cProfile charges about a microsecond per call,
so it over-rewards every change here -- all of them remove calls. Under it
the same three speedups read 54.0 s -> 50.8 s and 85.4 M -> 79.8 M calls,
which is the right shape and the wrong size. Profile to find the work;
time without the profiler to say what removing it was worth.

**Three exact changes**, all of them the same shape the repo already took
in `country_value` ("Clamped with comparisons, not `max`/`min`. Identical
arithmetic"), and all of them verified bit-identical by the parity corpus:

1. **`Position.place` written out instead of looped.** It ran 2.3 M times
   in one game -- `_delta` calls it twice per trial placement, once to move
   the board and once to put it back -- and the two-element loop it
   replaced built a tuple of tuples on every one. `_rehash` is inlined into
   it, removing a second Python call per placement. `place`'s subtree:
   5.92 s -> 4.24 s.
2. **`_delta`'s influence clamps.** 1.06 M `max` calls in one game, all of
   them `max(0, was + own)`.
3. **`rules_math.coup_outcomes`.** 1.10 M `max`/`min` calls: the DEFCON
   planner prices every roll of every coup either side could make.

**One of these was nearly a bug, and it is the useful part of the story.**
The first attempt at (3) hoisted `ops - 2 * stability + modifier` out of
the six-roll loop. That is the obvious optimisation and it is **wrong**:
`modifier` is a float, float addition is not associative, and the regrouped
expression differs in the last bit --

    (1 + 3 - 4) + 0.1  ->  0.1
    1 + ((3 - 4) + 0.1) -> 0.09999999999999998

-- with an `int()` truncation immediately downstream, so a margin sitting
exactly on an integer would flip. `evaluator.py`'s header says this in as
many words about multiplication; it is just as true of addition, and a
profile is exactly the context in which someone reaches for it. Reverted,
and the reason is now a comment at the site.

### What is left, ranked

| | share of the game | why it is not taken |
| --- | ---: | --- |
| `_delta` itself | **41%** cumulative | the structural fix is (4) below |
| `country_value` | 4.4 s exclusive, 2.9 M calls | 2.88 M of them come from `_delta` |
| `region_vp` | 2.1 s, 549 k calls | already cached per region per decision |
| `access` | 1.8 s, 3.3 M calls | already cheap per call; the early exits work |
| `route_weight` / `route_decay` | -- | **already `lru_cache`d**; this was checked, not assumed |

### The four-point repeat, measured and taken: 2.1%

Asked again directly, so measured rather than estimated.
`_investment` asks `delta` for one country at one, two, three and four
points. Every neighbour's value reads `cid` through `access` alone, and
`access` reads exactly three things about it -- who controls it, and
whether each side holds ANY influence there. `_delta`'s docstring already
says so, and the skip above the sweep already turns on those three. So two
trials that agree on the triple leave every neighbour on the same float.

Instrumented over one self-play game:

| | |
| --- | ---: |
| `_delta` calls | 531,901 |
| neighbour sweeps run | 402,097 |
| sweeps repeating a triple already computed | **179,754 (44.7%)** |
| `country_value` calls inside sweeps | 1,476,826 |
| **saveable** | **621,346 (42.1%)** |

Cached, per decision, beside `_base_country` and dropped by the same
`_invalidate_base`. What it buys:

| | before | after |
| --- | ---: | ---: |
| `country_value` calls | 2,916,018 | **2,382,145** (-18%) |
| `access` calls | 3,268,642 | **2,639,747** (-19%) |
| **wall, unprofiled, 3 games** | **60.50 s** | **59.22 s (-2.1%)** |

**Report the 2.1%, not the 18%.** Under cProfile the same change reads
50.8 -> 50.4 s. The honest number is the unprofiled one, best-of-two:
**2.1%**. The bookkeeping -- a
five-tuple key built on every sweep, a dict lookup, a diffs tuple -- eats
most of what the removed calls give back.

**Two things went in the way they did for exactness, not neatness.**

- The cache holds the per-neighbour DIFFS, not their sum. `change` is
  accumulated one neighbour at a time and float addition is not
  associative, so a cached total added in one step is a different float.
  The first draft cached the sum; it would have changed rankings. This is
  the same mistake as the `coup_outcomes` regrouping above, made twice in
  one sitting, which is why both now carry the reason at the site.
- `CHECK_SNAPSHOT` recomputes every hit and asserts it matches, so any run
  with the checker on is itself a proof that the key is big enough.
  `tests/test_neighbour_cache_discipline.py` checks the property directly
  (sweep every influence pair at a country; two that agree on the triple
  must leave every neighbour identical), checks a negative control (they
  do move when the triple moves), and shrinks the key in a subprocess to
  confirm the recompute catches it.

**Is 2.1% worth a ninth cache in the most defect-prone function here?**
Marginal, honestly. It is exact, corpus-verified and gated, and it
compounds with the 12.8% and 5.9% before it -- but in the currency that
matters for experiments it is ten minutes off an eight-hour arm, against a
shard cache that removes whole re-dispatches. Kept on those terms; one
revert undoes it.

### What is left after that

4. **Batching the four point-counts at the call site.**
   The neighbour sweep is now shared; the `place`/restore pair is not.
   `_investment` does four places per point -- restore, trial, untrial,
   commit -- so sixteen for a four-Op spend where a single pass that walks
   1 -> 2 -> 3 -> 4 and restores once would do five. `place` is still 2.32M
   calls and 4.2 s of the profile, so this is the largest single item left.

   It changes an interface rather than an expression, and it is exactly the
   kind of change that has inverted a sign here before
   (`tests/test_base_cache_discipline.py` exists because moving the board
   mid-ranking made breaks *more* attractive). Against the parity corpus,
   on its own, not bundled.

5. **Not taken: inlining `importance` into `access`'s loop.** It would save
   3.1 M calls, and it would put the battleground/control rule in a second
   place. That is the bug shape that has cost this repo the most, and step 4
   of the VP rebuild is about to delete that branch anyway.

**The honest summary of part 3: 8% is real, and it is not the answer to
"make experiments cheaper."** An 8% faster bot turns a 40-minute shard
into a 37-minute one. The cache turns a re-dispatched shard into
zero, and the waves turn half of a settled arm into zero. Spend attention
there.

## The shard that cannot be measured

Worth recording here because it is the thing the cache was built in
response to, and because it has now happened twice.

`fit-bc-base [5/8]` -- seeds 64640-64767 of block 64000-65023, against
`bc5ef93` -- ran 1h51m on its first dispatch and passed 2h21m on its
second, against siblings that finished in 28-67 minutes. **Two
independent dispatches, the same arm, the same shard index, therefore the
same 128 seeds.** Shards are deterministic, so that is not runner luck: it
is a reproducible slow slice, and a reproducible slice is findable.

The mechanism is not a mystery either. `benchmark.py`:

```python
floor = stall_timeout
if floor is not None and games:
    floor = max(floor, 8 * max(g['seconds'] for g in games))
```

So the hang detector's floor is **eight times the slowest game seen so
far**: one ten-minute game lifts it to eighty minutes. That is deliberate
and well argued where it stands -- six shards of the 2026-09-19 bisect
each lost their last game to a fixed gap, because with four workers and
two games left the gap between finishes IS one whole game -- but it has no
ceiling, and an earlier note filed it as a hypothesis about PR #21. It is
not a hypothesis; the code says it.

**The costly part is what happens at the other end.** `--stall-timeout` is
a gap-between-finishes detector, not a wall clock. When the 180-minute job
timeout fires, the runner kills the benchmark before it writes its report,
so the shard yields **nothing** -- where a benchmark-side stall (exit 6)
writes a partial report that pools. The asymmetry is worth closing: a
wall-clock cap inside the benchmark, set below the job timeout, converts
"lost shard" into "partial shard" for free. Not built; it should be the
maintainer's call, because it changes what a timed-out arm reports.

Bisecting the slice is cheap and decisive whenever someone wants it: four
inline arms of 32 seeds over 64640-64767 against `bc5ef93`. Three finish,
one does not, and the one that does not names the seed.

## The measurement discipline, restated

Every number above is from an idle box, as `CLAUDE.md` requires after that
entry was wrong twice in one day. The profile is one game, which is enough
for *proportions* and not for a quotable wall time; the parity corpus is
what makes "bit-identical" a claim rather than a hope.
