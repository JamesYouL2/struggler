# 2026-09-09 — The pure-function extraction, and the bug that forced it

Two commits. The first is a behaviour change and the second is provably
not, which is the only reason the second is safe to review by its diff.

### What the choice actually turned on

The overnight handoff offered `_access` precomputation or the pure-function
extraction and said to revert the former if it did not pay. Measured on its
own workload (the first 40 placement corpus records, five unprofiled
passes), the uncommitted precompute slice was inside run-to-run noise:
medians 0.418 s and 0.366 s at HEAD against 0.422 s and 0.421 s with it.
`_access` was also 7% of cumulative time on that workload, not the 10-16%
the handoff carried forward. So it was reverted, per the handoff's own rule.

The profile said the cost was elsewhere: `Board.control` at 398,622 calls
in one pass of 40 rankings, 20% of self time, with `region_tier` and its
`controller` closure another 35% cumulative on top of it. No `_access`
micro-slice touches that. A snapshot that derives control once and updates
it incrementally does.

### `_access` was returning stale numbers, and it changed moves

Bypassing the `_access` memo reordered **39 of the previous corpus's 598
rankings** and moved the values of 85 more. Not last-bit drift: a different
chosen move in 6.5% of captured positions, decided by what the player had
evaluated first. The memo was keyed `(board, cid, side)` while the function
reads influence two hops out, so a trial placement made and unmade inside
`_investment` left it describing a board that no longer existed.
`country_value` had a weaker version of the same defect (keyed on the
country's own `(own, opp)` while its access, wipe-backing and first-mover
terms read neighbours), and `_coup_targets` a third, keyed on
`(board, holder, defcon)` while counting influence.

This is the same finding as "`delta` is not a pure function of the board"
above, with the mechanism identified. It is not fixable with a better key:
a sound key covers the whole two-hop neighbourhood, which costs about what
the walk costs.

`7cb9fbe` deletes all three memos. It costs 26% (median 0.361 s to 0.454 s)
and regenerates the corpus, which drops from 598 to 514 records because the
games now diverge. Its 32-seed gate is a wash, as a correctness fix in
near-ties should be: turn-3 checkpoint mean signed VP +0.22, full games
score 0.484 with mean signed VP +0.38, no nuclear losses. The expert check
moved 24 -> 26 misses. **Completing is not passing** (Codex is right about
that): read this as neutral within the noise of 64 games, not as a win.

### The extraction

`bots/evaluator.py` holds the country, access, wipe, region-score and
margin terms as functions of `(Terrain, Position, weights, urgency,
defcon)`. `Terrain` is the static map indexed by country, built once per
process. `Position` is one board's influence plus derived control,
reachability, and the neighbour counts reachability needs, with
`place` updating all three in time proportional to one country's
neighbours. Scoring urgency became a vector computed once per decision,
which is what let `_scoring_weights` go.

Bitwise identical, and checked three ways before landing:

- Every term against the method it replaced, on all 514 corpus records:
  `country_value`, `_access`, `region_score`, `region_margin` and `value`
  for every country and region. The only mismatch found was `board_value`,
  by one ulp, because CPython compensates float summation inside `sum()`
  and an accumulator loop does not. The pure version now uses `sum()`.
- The parity corpus, the hash-seed regression and the full suite.
- Fixed 24-simulation MCTS searches on the opening, scoring and hazardous
  corpus records: identical chosen action, node count, and every root
  edge's visits and value.

Speed, same workload, against the corrected baseline: medians 0.471 s and
0.514 s at `7cb9fbe` against 0.285 s and 0.303 s after. About 40% faster
than the fix, and about 20% faster than the stale-memo code it replaces.
The full suite went 93 s -> 70 s, the parity test 129 s -> 59 s.

### The invariant this buys, and its price

The board and the snapshot must describe the same position, so every write
goes through `_set_influence`, `_add_influence` or `prepare`. That is a
real obligation with about ten write sites, so it is machine-checked rather
than trusted: `CHECK_SNAPSHOT` rebuilds the snapshot from the board on
every `delta` inside a ranking and compares. Two tests turn it on, and both
were confirmed to fail when a write site is deliberately broken.

Codex's concurrent audit caught one I had missed:
`RolloutPolicy._placement_plan` writes influence directly *and* sets
`_base_regions` itself, so the "outside a ranking, re-read the board"
fallback did not cover it. Fixed, with the rollout test that pins it.
`EventValuePlayer` had two more. That audit point was correct and worth the
interruption: a pure kernel does not make its stateful wrapper correct.

### Gate isolation, which this change broke and then fixed

`gate.sh` used to extract only the baseline's `strategic.py`. Once that file
imports `struggler.bots.evaluator`, a standalone load binds the
**candidate's** evaluator and the gate reports the candidate playing itself.
`benchmark.load_module` now binds an `evaluator.py` sitting beside the
baseline file for the duration of that load, and `gate.sh` snapshots both
files per revision into `$OUT/base/` and `$OUT/old/`. Two tests cover it.
This does not bite gates whose baseline predates the split, including the
one run for `7cb9fbe`.

### The event basis, the third instance of the same defect

Codex's audit was right and the reproduction is exact: `_resolve_sandbox`
re-valued only the countries whose own influence the event changed, while
`country_value` reads its neighbourhood. Nasser priced at -67.8296875
against -65.8890625 for a full pass, the whole 1.940625 being Israel.

`9d9890f` fixes it. The first attempt used a radius of two hops and still
mispriced Brush War and The Voice of America: `access` walks a neighbour's
neighbours and then asks whether *those* are reachable, which is a third
hop. `evaluator.VALUE_RADIUS` now lives beside the terms that set it, and a
test moves one country and checks that nothing outside the claimed set
moved with it. It fails at two.

This is a real pricing change: 408 of the previous corpus's 514 records
moved. It costs nothing measurable -- 87 events on a fixed position, 0.066 s
-> 0.059 s, because one snapshot per sandbox beats one per recomputed
country.

Its gate needed a second sample to read at all:

| Seeds | Games | Score | Mean signed VP | Nuclear losses |
| --- | ---: | ---: | ---: | ---: |
| 4000-4031 (gate) | 64 | 0.469 | -2.55 | 0 |
| 5000-5063 (held out) | 128 | 0.555 | +1.13 | 0 |
| combined | 192 | 0.526 | | 0 |

The gate seeds alone read as a strength loss. The held-out seeds read as a
gain of similar size, which is what noise looks like at 64 games; expert
misses went 26 -> 25. Kept on the strength of being correct, not on the
strength of that table. Codex's warning about selecting successive changes
on the same seeds is the reason the second sample was run at all, and it
should be routine, not exceptional.

### Next steps, in order

Codex reassessed the audit through `9d9890f` (see `docs/notes/codex/`) and
confirmed the three concrete findings this session addressed are closed.
What it still lists, in its order:

1. `_event_helper` keeps the weights it was built with when the parent's
   are replaced; `event_value` swallows every exception into a
   plausible-looking estimate, so a defect reads as an approximation.
2. Explicit gate acceptance thresholds. "Exited 0" is not "passed", these
   notes have used the wrong word before, and the table above is exactly
   the case where a threshold would have decided instead of judgement.
   Held-out seeds belong in the same rule.
3. Scoring horizon: `scoring_schedule` has no turn-10 cap and no final
   scoring, so late-game investments are priced against scorings that never
   happen. This is the largest remaining valuation error and it is
   systematic, not a tie-break.
4. Flag-only events (NATO, Formosan Resolution, Shuttle Diplomacy) still
   value 0 because the sandbox measures influence and immediate VP.
5. Align the two Ops estimates: `ops_value` plans a greedy multi-country
   spend, the `OPS_TYPE` influence branch extrapolates one country.
6. Only then the indexing measurement (C step 3). The evaluator is already
   the data layout a native kernel would receive, so that measurement is
   about whether the boundary pays, not about restructuring.
