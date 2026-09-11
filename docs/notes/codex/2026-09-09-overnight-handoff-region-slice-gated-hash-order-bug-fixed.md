# 2026-09-09 — Overnight handoff: region slice gated, hash-order bug fixed

Scope so far: finish the four next steps in `docs/notes/claude/`, run the
full 32-seed gate, make atomic conventional commits, then continue with one
more evaluator/MCTS improvement. The tree was clean at this handoff. The
remaining optimization work should start from `a84593a`.

### Commits made

- `c24c531 perf(bots): cache regional margin aggregates`
- `b0db60d test(corpus): preserve investment tie context`
- `ee66cce docs(notes): rename Astra audit to Codex`
- `696294c fix(profiling): select hazards from ordered probes`
- `7d820de fix(profiling): force hazardous MCTS searches`
- `a84593a fix(bots): stabilize access ranking across hash seeds`

The two profiler fixes were necessary because corpus v3 replaced the old
`planner.hazardous` mapping with ordered `planner.probes`, and none of the
natural hazardous action-round records contains a scoring card. The
hazardous profile now selects from the ordered probes and deliberately uses
`MCTSPlayer(search_all=True)`. A direct smoke run on seed 4000, turn 5,
action round 1 completed 24 simulations over 18 nodes.

### The reported cross-test leak was hash-order nondeterminism

The current full suite initially passed unchanged (`490 passed, 3 skipped`,
134.16 s), which contradicted a persistent leak. No test writes the shared
adjacency dictionary, `RULES`, or the module card tables, and the adjacency
values are immutable `frozenset`s. Fresh-process probes then reproduced the
six affected corpus records under some `PYTHONHASHSEED` values without
running any earlier tests.

Root cause: `_access()` accumulated floats while iterating a first-hop
`set` and second-hop adjacency `frozenset`s. Hash-dependent addition order
moved values by one ulp; strict ranking then reordered candidates around
2.4668. This looked like test pollution because the isolated and full-suite
pytest processes happened to receive different hash seeds.

`a84593a` walks both additive neighbor loops in sorted order and adds a
three-process regression covering hash seeds 0, 1 and 2. Manual probes of
all six reported records (121, 122, 130, 131, 135, 136) matched the corpus
under seeds 0 through 5. The full suite under `PYTHONHASHSEED=5` passed:
`491 passed, 3 skipped in 151.91s`. The corpus did not need regeneration;
the canonical order reproduces its captured values and rankings.

### Region-margin gate: passed over 32 seeds

Ran the isolated snapshot gate at `ee66cce` against the pre-slice revision
`1291064`, seeds 4000-4031, both seats, 8 workers:

| Check | Result |
| --- | --- |
| Turn-3 checkpoint | score 0.500, mean signed VP 0.00, mean total 0.00, 0 nuclear losses |
| Full games | score 0.500, mean signed VP +0.27, mean total +0.55, 0 nuclear losses |
| Existing expert check | 24 misses; two ordering and placement warnings remain, not introduced by this slice |

Raw gate artifacts are in `logs/game-check/gate-ee66cce/` (gitignored).
The gate exited successfully. Because `a84593a` is a later behavioral
determinism fix, the final overnight candidate still needs its own 32-seed
gate after the next slice is selected and landed.

### Isolated region-slice timing and fixed-search evidence

Compared detached, clean snapshots `1291064` (before) and `7d820de` (after;
the only `strategic.py` change is `c24c531`) on Linux/WSL2, Python 3.12.13,
8 logical CPUs. The same current corpus supplied serialized positions to
both. No other benchmark or repository process was running.

For the first 40 `place_influence` corpus positions, five unprofiled passes
took:

- Before: 0.150938, 0.178106, 0.168382, 0.206434, 0.176398 s
- After: 0.125992, 0.141635, 0.137464, 0.125678, 0.147990 s
- Median: 0.176398 -> 0.137464 s, **22.1% faster**

Ten process-isolated strategic-vs-strategic seed-4000 games were run in
alternating order to reduce time-of-run bias. Every game ended identically:
USSR, -20 VP, turn 10, VP victory.

- Before: 8.390106, 7.833148, 8.760186, 8.837293, 8.647347,
  7.565142, 8.768050, 8.582119, 8.775470, 8.642374 s
- After: 6.947339, 7.728132, 7.639097, 7.689720, 7.675124,
  6.927435, 7.384989, 7.716984, 7.634510, 7.627454 s
- Median: 8.644861 -> 7.636804 s, **11.7% faster**

Three repeated 24-simulation MCTS searches on fixed corpus records retained
identical action/root-stat digests before and after (including move order,
visits and values): opening record 6 chose East European Unrest with 11
nodes; scoring record 35 chose Formosan Resolution with 15 nodes; hazardous
record 58, forced with `search_all`, chose the China Card with 18 nodes.
Wall-time medians were noisy and mixed:

| Fixed MCTS case | Before median | After median | Change |
| --- | ---: | ---: | ---: |
| Opening | 6.320 s | 6.559 s | 3.8% slower |
| Scoring | 9.395 s | 8.948 s | 4.8% faster |
| Hazardous | 28.259 s | 29.771 s | 5.4% slower |

Do not claim a general MCTS speedup from three repetitions. The direct
placement workload and ten alternating full games support the region slice;
the fixed-search digests support unchanged behavior on these MCTS cases.
Temporary full JSON reports are `/tmp/region-before-1291064.json` and
`/tmp/region-after-7d820de.json`; the raw durable values are copied above.

### Next action

Take `_access` as the next evaluator slice before attempting the broader
pure-function extraction. It is 10-16% of the measured path and the
determinism fix now sorts adjacency on every call. Precompute canonical
first/second-hop adjacency tuples once and reuse them in `_access`, while
preserving its current duplicate counting, reachability, contested and
chain semantics. Measure this slice independently against `a84593a`; require
the parity corpus, the hash-seed regression, the full suite, fixed MCTS root
statistics, and a fresh 32-seed gate before landing it. If precomputation
does not beat the new sorted implementation end to end, revert that slice
and proceed to pure-function extraction instead.
