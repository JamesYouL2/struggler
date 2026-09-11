# Where this stands: one failing test, one uncommitted slice

### The failing test

`tests/test_parity_corpus.py::test_evaluator_and_planner_reproduce_the_corpus`
**passes on its own (2 tests, 120 s) and fails inside the full suite**
(`1 failed, 489 passed, 3 skipped`). Same six records every time: indices
121, 122, 130, 131, 135, 136, all reported as `ranking order`, all seed
4000 turn 9 placement decisions with a cluster of candidates whose value
is 2.4668 to fourteen significant figures.

Verified facts:

- pytest 9.1.1 with no random-ordering plugin, so collection order is
  deterministic and this is a real state leak from an earlier test file,
  not flakiness.
- The reordering is confined to candidates whose values agree to ~1e-14;
  no value moves by more than that.
- Run alone, those six records reproduce the corpus exactly.

Not yet established: which test leaks. `Board.__init__` copies the
country mapping (`dict(countries)`) and `CountryInfo` is frozen, so a
per-board battleground promotion cannot leak, but `_adjacency` is the
shared dict from the `lru_cache`d `_static_map()` and is only shallow
referenced, so a test that assigns `board._adjacency['US'] = ...` would
leak globally. `RULES` and the module-level `CARDS` are the other shared
mutables worth checking.

Next diagnostic, cheapest first:

1. `pytest tests/<file>.py tests/test_parity_corpus.py` bisected over the
   test files that run before it alphabetically, to name the leaking file.
2. In that file, look for assignment to anything reached through
   `_static_map()`, `RULES`, or `CARDS`.
3. Fix the leak in the test (or make the shared structure defensively
   copied), rather than loosening the parity assertion.

Do not weaken the checker to make this pass. It is reporting a real
cross-test dependency.

### The uncommitted region-margin slice

Working tree (uncommitted): `src/struggler/bots/strategic.py`,
`scripts/capture_corpus.py`, `tests/test_parity_corpus.py`,
`tests/test_strategic.py`, `tests/corpus/positions.json.gz`.

This is Option C step 3's first evaluator slice (Astra's recommendation:
region-margin work before a broad indexing rewrite). What it does:

- `_margin_basis(board, region)` caches the region margin's aggregates
  per region for the life of one ranking, under the same contract as
  `_base_regions` (cleared wherever that is cleared, including both
  commit points inside `ops_value`). The hot path no longer builds an
  influence-keyed cache entry per trial placement.
- `_margin_swapped(basis, ...)` swaps one country's contribution into
  those aggregates. The fractional battleground total is rebuilt by
  re-summing the per-member fractions **in member order**, which is
  bitwise identical to the full walk because `x + 0.0 == x`. The old
  `a[1] - o[1] + n[1]` was only close, and that was enough to reorder
  near-ties and flip `_investment`'s strict `>`.
- `region_margin_after` is kept for callers that hold no basis.

Measured on an idle machine, best of three (rankings) and best of two
(game):

| | old | new |
| --- | ---: | ---: |
| 40 placement rankings | 0.34 s | 0.30 s |
| strategic full game, seed 4000 | 7.4 s | 6.3 s |

About 15 % on both. Note the full game is 6-7 s here, not the 13.4 s in
the baseline table above: that earlier figure was taken with a gate
running concurrently, exactly as Astra warned.

The existing incremental-vs-full test now asserts **bitwise** equality
rather than a 1e-9 tolerance.

Not committed because the suite is not green. Commit it only once the
leak above is fixed and the parity test passes in the full suite, then
gate it: it is a behaviour change (it removes six near-tie reorderings
and changes some `_investment` point counts), not a no-op.

### Finding worth telling Astra: `delta` is not a pure function of the board

Chasing the last parity mismatch turned up something more important than
the mismatch. `StrategicPlayer.delta` returns values that differ in the
last bit depending on what was computed before it on the same instance,
because it reads per-decision caches (`_base_regions`, `_base_margins`,
`_country_cache`, `_region_cache`). Concretely, on corpus record 381
(seed 4002 T5 AR6 USSR), `delta(France, own=1)` is 3.6977777777777776
during the generator's delta pass and 3.697777777777777 when called
after a different warm-up. `_investment` compares gains with a strict
`>`, so a one-ulp difference silently flips the chosen point count
between 1 and 2.

Consequences:

- The corpus now records the per-point gains alongside the chosen point
  count, and the checker enforces the point count only where the best two
  gains differ by more than 1e-12. Where they do not, either answer
  reproduces the same value per Op.
- This is a direct argument for the plan's pure-function evaluator step:
  a kernel that reads no caches cannot have this property, and until it
  exists, "identical rankings" is only reproducible for a fixed call
  sequence. Astra's insistence on recording query order was right for the
  planner and turns out to apply to the evaluator too.

### Next steps, in order

1. Find and fix the cross-test state leak; get the suite green.
2. Gate the region-margin slice (behaviour change, 15 % faster).
3. Report the slice on its own, per Astra: isolated snapshot, repeated
   unprofiled timings, fixed ranking statistics, no other work running.
4. Then either the next evaluator slice (`_access`, 11-16 % of profiled
   time) or the pure-function extraction, which the finding above makes
   more valuable than it looked.

Steps 1-3 are done. Step 4 was settled by measurement in favour of the
extraction; see the 2026-09-09 section at the end of this file.
