# A newer anchor: v0.6.0 in place of bc5ef93

Weight and deletion arms have played against `bc5ef93` since 2026-09-20.
It is time to replace it (maintainer, 2026-09-26: "a faster and better
newer version"). The reasons:

- **It hangs.** `bc5ef93` is dated 2026-09-12, the day before `48007da`
  fixed the sandbox helper-chain recursion. About one game in 700 against
  it never ends: seeds 132008 and 132709, then 140565, 140591 and 141179.
  Every hung game costs a stalled shard and a backfill. This was traced
  on 2026-09-26; the trace is in
  [the hand planner close-out](2026-09-26-the-hand-planner-stays-off.md).
- **It is slow.** It predates every exact speedup since: the forecast DP
  (7.45x), the enum attribute reads, and the planner predicates. Half of
  every experiment's compute is the anchor.
- **It is far from the bot under test.** Main beat it 0.562 on the fresh
  block (drift run 36219208156). An opponent that plays like the current
  bot is the more relevant one.

## The candidate

**`v0.6.0` (`9c59650`, 2026-09-25).** It is the newest tag and it has the
fix. Since then, the only merged change to play is #61 (event choices by
board value, gate ACCEPTED). The deletions in #62 were exact, so they do
not change play.

## The measurements, and the rule, before the numbers

1. **Faster** (local, idle 6-core box). Eight self-play games per
   snapshot, seeds 4100-4107, with each seed's pair run concurrently so
   load falls on both alike. Output: `logs/anchor-timing/`.
2. **Better** (CI, 1024 seeds each, block 143000-144023, reserve
   144100-144227, waves off):
   - `v0.6.0-vs-bc5ef93`: the candidate against the current anchor;
   - `main-vs-v0.6.0`: main against the candidate. It is expected near
     0.5, and it checks that the tag runs clean as a baseline.

**Switch** the default anchor for NEW arms to `v0.6.0` if:

- `v0.6.0-vs-bc5ef93` is not measurably below 0.5;
- `main-vs-v0.6.0` has no stalled game that traces to the anchor;
- the timing does not make `v0.6.0` slower.

Arms already read against `bc5ef93` keep it, including the access
deletion in flight (run 36253272931). Paired differences are
anchor-relative, and changing an arm's anchor after its reading would
split a telling. `bc5ef93` stays in the drift panel for continuity, and
`v0.6.0` joins it.

What it does not settle: a reading against `v0.6.0` and one against
`bc5ef93` are not level-comparable. Only paired differences within one
run are.

## The readings

(Filled in at read time.)
