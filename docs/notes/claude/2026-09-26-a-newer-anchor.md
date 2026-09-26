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

**Faster: yes, 3.2x** (local, idle 6-core box, 2026-09-26, nothing else
running).

- **Identical work.** The same 133 parity-corpus positions (every 4th
  record) were ranked by each snapshot, each in its own process so two
  snapshots never share module state, alternating A, B, A, B:
  - `v0.6.0`: 4.98 s and 4.95 s;
  - `bc5ef93`: 16.05 s and 16.18 s.

  That is `bc5ef93` / `v0.6.0` = **3.24**, repeatable to 1%. It is the
  number to quote.
- **Self-play games**, seeds 4100-4107, one game per snapshot per seed:
  94.1 s against 192.7 s. The two play different games of different
  lengths, so this is confounded; per turn played it is 1.7 s against
  3.1 s. It is shown only because it agrees in direction. One pair ran
  while a pre-push hook held the cores for about 40 s.

An anchor is half of every experiment game, so a bot near `v0.6.0`'s cost
should play its shards in roughly half the time against it.

**Better: yes** (run 36261552485, 1024 seeds each, both complete).

| arm | score | stalled games |
| --- | --- | --- |
| `v0.6.0-vs-bc5ef93` | **0.556 [0.539, 0.573]** | 3 (all bc5ef93's helper-chain hang; backfilled) |
| `main-vs-v0.6.0` | **0.509 [0.497, 0.521]** | **none** |

- v0.6.0 is clearly stronger than `bc5ef93`, and main plays level with it
  (only #61 changed play in between).
- The old anchor lost **216 games to DEFCON 1 as the opponent in 2048**;
  v0.6.0 lost 59. `bc5ef93` destroys itself about 3.7 times as often, and
  that accounts for part of every "main beats bc5ef93" margin.

**All three criteria are met, so the switch is made.**

- New arms play `v0.6.0`. The registry's `_schema.anchor` says so.
- `v0.6.0` joins the drift panel's default anchors (`drift.yml`), and
  `bc5ef93` stays there for continuity.
- The arms already in flight or read against `bc5ef93` keep it:
  `oldw-*`, `rc-*` and `ee-*`, dispatched before this reading.
