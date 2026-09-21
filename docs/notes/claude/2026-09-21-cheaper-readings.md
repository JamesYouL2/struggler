# Cheaper readings: a shard cache, sequential waves, and 6% off the bot

2026-09-21. Three ways to get the same answers for less, asked for
together and worth reading together because they buy different things:
the cache removes **repeated** work, the waves remove **unnecessary**
work, and the profile removes **wasted** work. Only the first two are
large.

| | what it removes | typical saving | what it costs |
| --- | --- | ---: | --- |
| shard cache | replaying a shard already played | **up to 100%** of a re-dispatch | a stale reading if the key is wrong |
| sequential waves | the second half of a decided arm | **~50%** of arms that were never close | final interval 1.645 -> 1.678 (+2.0%) |
| the three exact speedups | Python call overhead in the hot loop | **5.9%** of a game | nothing; bit-identical |

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

## 3. `delta` and `country_value`: 5.9%, and where the rest is

Profiled, one strategic self-play game (seed 4000, italy/austria), on an
otherwise idle box. Absolute times are this machine; the proportions are
the point.

| | before | after |
| --- | ---: | ---: |
| wall | 54.0 s | **50.8 s** |
| function calls | 85.4 M | **79.8 M** |

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

4. **The one structural saving left is the four-point repeat.**
   `_placement_ops_value` asks `delta` for one country at one, two, three
   and four points, and `_delta`'s own docstring says so: "this half is
   computed four times for one answer". The base half is already cached
   (`_base_country`, `_base_regions`); what is **not** shared across the
   four is the `place`/restore pair and the whole neighbour sweep. The
   `delta` memo hits only 27% (792,908 calls, 581,687 misses) because
   `(digest, cid, own, opp)` makes those four legitimately distinct keys.

   Doing all four points in one pass -- one `place` per point but one
   neighbour set, one urgency vector, one region lookup -- is worth
   attempting and is **not** a micro-optimisation: it changes an interface.
   It is also exactly the kind of change that has inverted a sign in this
   codebase before (`tests/test_base_cache_discipline.py` exists because
   moving the board mid-ranking made breaks *more* attractive). It should
   be done against the parity corpus, on its own, and not bundled.

5. **Not taken: inlining `importance` into `access`'s loop.** It would save
   3.1 M calls, and it would put the battleground/control rule in a second
   place. That is the bug shape that has cost this repo the most, and step 4
   of the VP rebuild is about to delete that branch anyway.

**The honest summary of part 3: 5.9% is real and free, and it is not the
answer to "make experiments cheaper."** A 6% faster bot turns a 40-minute
shard into a 38-minute one. The cache turns a re-dispatched shard into
zero, and the waves turn half of a settled arm into zero. Spend attention
there.

## The measurement discipline, restated

Every number above is from an idle box, as `CLAUDE.md` requires after that
entry was wrong twice in one day. The profile is one game, which is enough
for *proportions* and not for a quotable wall time; the parity corpus is
what makes "bit-identical" a claim rather than a hope.
