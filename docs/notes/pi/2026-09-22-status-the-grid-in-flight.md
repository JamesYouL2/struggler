# Status, 2026-09-22: the hold-option grid is in flight, and a `compare_to` arm cannot run alone

Written 16:45 UTC to answer three questions at once: what is running,
what the failed dispatches just taught, and what to run next. Nothing
below is a reading -- the grid has not produced one yet.

## What is running

**Run 35753235236 -- the hold-option grid, and the run that counts.**
All four arms (`hold-option-base`, `-025`, `-05`, `-10`) in one dispatch,
block 74000-75023 against `bc5ef93`, the three grid arms paired to base,
wave 1 shards [0-3/8] of 8 per arm in flight since 16:18 UTC at `7976bd9`.
The decision rule is pre-registered in each arm's own `context` in
`.github/experiments.json` and must not move once numbers are visible.

**Run 35752606270 -- the orphan, and the one to decide about.**
`only=hold-option-base`, dispatched 16:12 as "grid round 2". Its wave-1
base [0-3/8] were cancelled at ~16:19, one minute after the four-arm
dispatch started the identical shards. The `interim` look then ran on
empty data and, fail-open as designed ("THE LOOK MUST NEVER ABORT THE
STEP"), launched wave 2: **base [4-7/8] `w2`, playing now** since 16:20.

Two ways to read the orphan's wave 2, and the choice is the maintainer's:

- **Not worthless.** It is the base half of the paired block beyond
  [0-3/8]; shards are cached on identity, so if the four-arm run's own
  look sends base to wave 2, those shards restore rather than replay.
  Cancelling destroys work half-done for nothing -- handoff item 8's
  question ("what would the surviving data say?") answers: exactly what
  the four-arm run would have had to play itself.
- **Not a reading.** Its `collect` pools only its own run's artifacts and
  it has no grid arm paired against it, so at best it is a half-block base
  *level*, and levels are not comparable across blocks. It cannot
  contribute to the pre-registered paired verdict either way. If both
  runs reach base [4-7/8] the work is duplicated in wall-clock (the cache
  saves at completion, so it buys nothing twice), not the verdict.

My reading: leave it running. The verdict comes from 35753235236
regardless; the orphan is at worst a warm cache and a half-block level.

Also in flight: `tests` on `7976bd9` and the PR gate both green (runs
35742943187 / 35742946843), PR #40 open on `exp/hold-option-value`.
Local box idle -- nothing local should start while the grid is the
question.

## The shape the plan step enforces: `compare_to` runs with its target or not at all

Three of the four "grid round 2" dispatches (35752610122 / 1389 / 17789,
one `only=` per grid arm) failed in the `plan` step in 10-15 s, each on
the same assertion:

```
AssertionError: hold-option-10: compare_to 'hold-option-base' is not in this run
```

"One entry per arm; every entry runs as its own job" is `_what`'s own
wording in `experiments.json`, and the natural reading of it -- dispatch
each arm separately -- is wrong the moment an arm carries `compare_to`:
the paired difference is collected *within* a run. The dispatch that
works is one `only=base,<grid arms>`, which is what 35753235236 is.

The guard did its job: it caught the assumption in fifteen seconds, at
plan time, before a single runner minute. What is missing is the
constraint written where the assumption is formed. The fix is one line in
`_schema.compare_to` ("must be dispatched in the same run as its target;
`only=` them together") and half a line in the `only` input's
description. **Not done here on purpose**: `experiments.json` arm entries
carry the pre-registered `context` the in-flight grid will be read
against, and the shard cache is keyed on arm identity
(`scripts/arm_identity.py`). Edit the registry after the grid lands, not
while four arms are quoting it.

Once so far, so a note is what the rule asks for. If a second session
dispatches a `compare_to` arm alone and hits the same assert, that is the
recurrence signal: gate it then.

## Next, roughly in order

1. **Read the grid** when 35753235236 collects: across the three points,
   paired to base on one block. The pre-registered outcomes -- a peak
   with its paired lower bound above 0 ships that value (gate first, then
   a MINOR bump); monotone rise through 1.0 asks for a grid above 1.0;
   everything at or below 0 says the next-turn price already carries the
   flexibility and ruling 3's term stays at 0 in the live hold pricings.
2. **Decide the orphan** (35752606270), from the two readings above.
3. **Registry touch-up after the grid**: the `_schema.compare_to` and
   `only` lines above.
4. **Hand planner step 3**, the assignment planner (step 2 dropped on the
   maintainer's ruling, 2026-09-21). `value_as_held` delegates to
   `hold_value` for exactly this, so step 3 prices its hold slot at
   whatever the grid just settled.
5. **VP-rebuild step 5**: the `potential` term and the sandbox gap in
   `_delta`'s contract
   ([the fresh-block note](2026-09-21-the-fresh-block-answers-the-fit.md)
   lists it under what this does NOT settle). Its own 1024-seed verdict,
   its own branch.
6. **The refit at current main** -- now a potential gain on top of a
   shipped one rather than a rescue, and better posed for it. Below 5.
7. The `FURB136` cleanup stays undone by the maintainer's ruling. The two
   human-only write-path items from the 2026-09-21 handoff -- pushing
   `anchor-2026-09-12` and deleting `exp/access-leak-isolation` -- were
   done by the maintainer and verified on 2026-09-22: the tag is on
   origin (`5859063`), the branch is gone.

Harness habits for this session's shape -- what to run where, what the
skills can carry -- are in
[the pi harness note](2026-09-22-the-pi-harness-and-what-to-ask-of-it.md).
