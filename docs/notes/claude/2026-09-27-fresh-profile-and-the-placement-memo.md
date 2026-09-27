# A fresh profile, and the placement memo (-19% a game, exact)

> **Correction (2026-09-27, Astra's audit F5):** the memo as merged in
> #79 was NOT exact. Its key dropped the whole pending decision on the
> claim that nothing on the placement path reads it. But `_after_reply` ->
> `rules_math.next_move` -> `phasing_side` reads the decision's
> `phasing_player`. Astra's constructed turn-10 AR7 pair reused 19.22
> where a fresh player computes 25.26. My check had grepped `policy.py`
> only, and the read was in `rules_math.py`. The six matching games never
> reached that late-game case. Fixed in `fix/astra-caches-f3-f5`: the key
> now carries the phasing player, and a full game through turn 10 and
> Astra's pair are both tests. Re-measured on the fixed memo: identical
> moves in the same six games, 108.5 s -> 85.0 s (-21.7%).

The maintainer (2026-09-27): "do a fresh profile and see what we can do
about removing redundant work in the sandbox" -- step 1's baseline for the
Rust port plan (docs/RUST_PORT_PLAN.md) was from 2026-09-25, before
`potential`, the hand planner and the event-discount stack left.

## Whole games, no profiler (the numbers to quote)

Main at `b4ecd1d`, idle 6-core box, strategic vs strategic, seeds
4100-4105, one game at a time: **11.0-27.1 s a game**, 105.3 s for the
six. (The 09-25 audit read 47-50 s on seed 42000 in its own container;
not comparable machine to machine.)

## The profile (to rank, not to quote)

Two games (seeds 4100-4101) under cProfile, 116.8 s profiled. Cumulative
shares overlap:

| path | share | calls |
| --- | ---: | ---: |
| `event_value` -> `_public_event_value` -> `_resolve_sandbox` | 53% / 47% | 1,716 sandbox runs |
| `ops_value` -> `_placement_ops_value` -> `_investment` | 52% | 13,095 -> 6,713 uncached |
| `delta` / `_delta` | 45% | 1.75 M |
| `DefconPlanner._solve` | 28% | 1.42 M |
| `evaluator.country_value` | 24% | 5.3 M |

## Where the redundant work is

Each `_public_event_value`, `_placement_ops_value` and planner `risk` call
was keyed on its FULL input (the observation minus its pending decision,
plus arguments), and the time spent on inputs already computed that game
was counted. Two games, instrumented:

| call | calls | repeats of an identical input | share of its time |
| --- | ---: | ---: | ---: |
| `_placement_ops_value` | 6,713 | **3,088 (46%)** | **41.8%** |
| (the same, keyed per player instance + board as it stands) | 6,713 | 3,018 (45%) | 41.2% |
| `_public_event_value` | 1,716 | 228 (13%) | 12.4% |
| planner `risk` | 2,315 | 217 (9%) | 35% of 2.4 s |

**The biggest redundancy was not the sandbox but the Ops placement
search.** A card play is a chain of decisions (card, mode, Ops type, each
point placed), each one a fresh ranking that cleared the per-decision
cache and ran the same search on the same board again. That includes
inside the sandbox's helper players.

## The placement memo

`StrategicPlayer._placement_ops_value` keeps its results across decisions,
per player instance. The key is everything the search reads (bug shape
1):

- the observation it is asked about, and the one the player is prepared
  on, both minus `pending_decision` (nothing on the path reads it --
  checked for `_investment`, `delta`, `_delta`, `_after_reply`,
  `_coup_reply`, `_reply_budgets` and the board helpers);
- the board as it stands (the snapshot's influence arrays, since callers
  move it for trial placements);
- the Ops, and the weights.

It is bounded at 50,000 entries; a full game peaks at 1,801 across both
players and their sandbox helpers, +12 MB. `StrategicPlayer.PLACEMENT_MEMO`
switches it off.

**Exact:** six full games (seeds 4100-4105, 4,916 steps) made identical
moves with the memo on and off. `tests/test_placement_memo.py` pins it on
two games to turn 3, and pins that the memo does hit (under 80% of the
`_investment` evaluations). The parity corpus passes unchanged. It cannot
see the memo at all: it builds a fresh bot per record.

**Faster: 105.3 s -> 84.9 s over the six games, -19.4%**, whole games, no
profiler, alternating order, idle box.

## What is left, ranked by what it could save

1. **The sandbox's event value, across decisions** (`_public_event_value`
   repeats: 13% of calls, about 6% of a game). Its key is harder: the
   sandbox reads the helper's `_outer_events` and `_choice_stack` (the
   recursion guards) as well as the observation. It is the next exact
   memo, and it must key on those.
2. **The planner's `risk`** repeats (about 1.6% of a game): small. The
   planner already memoises `solve` within an instance; one planner is
   built per decision (`planner_for`), so repeats across decisions are
   rebuilt from scratch.
3. **Inner loops:** `delta` (1.75 M calls) and `country_value` (5.3 M) are
   the evaluator the Rust kernel targets. The memo cuts how often they
   run; the kernel would cut what each costs.

With the memo in, a fresh profile should be taken before the port's step 4
decision: the shares above move once the repeated placement searches are
gone.
