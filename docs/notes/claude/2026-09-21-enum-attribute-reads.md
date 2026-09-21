# `Enum.value` is a descriptor, and the engine read it 3.2 million times a game

2026-09-21. The 2026-09-20 baseline profile put `enum.py:202(__get__)` at
3.2 million calls with 0.72 s of own time -- fourth by call count in a
self-play game, and the same shape already fixed once inside `defcon.py`
during the hot-spot work. This is that finding chased down.

## What it actually costs

The profile's own-time column overstates it about three times, because
cProfile's per-call overhead is large relative to a function this small.
Timed outside the profiler:

| | per read | x 3,172,738 |
| --- | ---: | ---: |
| `.value` / `.name` (`DynamicClassAttribute`) | 82 ns | **0.24 s** |
| `._value_` (the storage behind it) | 9.4 ns | 0.03 s |
| a plain attribute set once | 9.7 ns | 0.03 s |
| a module dict keyed on the member | 14.1 ns | 0.04 s |
| `.opponent.value` (property, then descriptor) | 115 ns | -- |
| one plain attribute holding the opponent's key | 9.8 ns | -- |

So the ceiling on the whole hot spot is about 1.5% of a 16.5 s game, not the
4% the profile implies. Worth having, not worth a campaign -- which is what
decided the scope below.

`Enum.value` is a `DynamicClassAttribute` so that a member named `value`
cannot shadow the property. It is a DATA descriptor, so an instance
attribute cannot shadow it either: the fast spelling has to have a different
name.

## What was done

`Side` and `Region` carry `key`, the member's own string, and `Side` carries
`opp_key`, the opponent's. Both are plain attributes set once at import, in
the same spirit as the `__hash__ = object.__hash__` lines that were already
there for the same reason.

Eight sites were converted -- the ones holding 73% of the reads -- and only
those. Cold paths keep `.value`.

CHANCE deliberately has no `opp_key`, so asking for one raises AttributeError
the way `Side.opponent` raises ValueError. It has no opponent either way;
what it must not do is quietly answer.

**Three of the eight were doing more than an attribute read**, and that is
where most of the gain is:

- `defcon_allows_coup` walked `RULES["coup_min_defcon"]` by `region.name`,
  273,000 times a game, to look up one of six fixed numbers. It is now a
  dict on the Region member, built once at import.
- `DefconPlanner.__init__` rebuilt its opponent-event set by walking every
  card and reading `CardSide.value` -- constant data, re-derived 5,984 times
  a game. Now `_EVENTS_BY_SIDE`, partitioned at import.
- `attempts_allowed` read both Space Race boxes off the observation, which
  is frozen for the planner's life, on each of 342,000 calls. Hoisted to
  `__init__`. `allowed` still asks the engine, because it reads
  `game_effects` and this is not the place to assume that cannot move.

## The result

Lookups, counted (deterministic, so no noise): **3,172,738 from 112 sites ->
188,658 from 97**. A 94% cut from eight sites, because the sites were the
loops.

Time is the harder number. The first A/B said 2.4% faster in round one and
1.1% SLOWER in round two -- the box's run-to-run spread is larger than the
effect, and round two was uniformly slower than round one on both arms. The
readable version is two worktrees, runs alternated arm by arm, five each,
minimum per arm (the minimum is what the machine can do; the rest is
whatever else it was doing):

| | seed 4000, whole game |
| --- | ---: |
| main | 17.45 s |
| this branch | **17.14 s** |
| | **-1.8%** |

Four of five paired runs favour the branch. That matches the ceiling plus
the three sites that removed real work rather than a descriptor call.

**Do not quote the single-round A/B.** It is in this note only as the record
of why the alternating form exists: one round of one seed cannot resolve 2%
on this machine, and the first attempt reported the wrong sign.

## Every game is identical

Same turn reached, same final VP, every seed, and the whole suite passes
including the parity corpus -- which is the point. This is a speed change
with no behavioural content, so the corpus is the oracle that says so, and
`test_the_fast_attributes_are_the_slow_ones` holds every member's `key`
against its `value` and `opp_key` against `opponent`. Two copies of one fact
is the shape that keeps biting this codebase; the copy here is deliberate and
measured, and that test is what keeps it honest.

## What is left

188,658 reads remain across 97 sites, none of them hot, worth about 0.015 s.
Also unconverted: 82,662 `Side(...)` constructions a game (`enum.py:1128`),
mostly `phasing_side` turning a context string back into a member. That is a
different fix -- caching the construction, not the read -- and at 0.025 s of
profiled time it is below the noise floor measured above.
