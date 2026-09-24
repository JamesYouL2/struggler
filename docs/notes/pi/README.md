# Pi working notes

Sessions running under the pi harness keep their notes here. Each agent
has its own tree -- Claude's is `docs/notes/claude/`, the audit's is
`docs/notes/codex/` -- and they are kept separate on purpose
(maintainer's rule, 2026-09-22). One file per topic; recent entries sit
here, older ones under `archive/`. `bug-shapes.md`, the defect registry
a test parses, stays at its stable path in `docs/notes/claude/`
regardless of who records a new shape.

## Contents

- [Drift panel 2026-09-24: every anchor is behind us now](2026-09-24-drift-panel-all-five-behind-us.md) — 2026-09-24
- [The ablation sweep: which live variables earn their keep](2026-09-23-the-ablation-sweep.md) — 2026-09-23
- [Handoff, 2026-09-23: what landed tonight, the arm in flight, and what to pass on](2026-09-23-handoff.md) — 2026-09-23 (three verdicts read by their rules -- hold-option stays 0, the refit LOST, the potential term stops -- the assignment planner built behind its gate, run 35814771005 in flight with its rule quoted; and the session's five mistakes in the order a weaker model will remake them) -- since read: paired -0.240 [-0.262, -0.218], the gate stays shut, the loss diagnosed as a tie-break in `docs/notes/claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md`

- [The assignment planner: tail reads before the number, and the arm in flight](2026-09-23-assignment-planner-tail-reads.md) — 2026-09-23 (USSR tail at 0.25 halves 6/32 -> 3/32 under the planner and its closings come later (turn 6 -> 9) -- direction and story at 32 seeds, not measurement; run 35814771005 is the measurement) -- since read: paired -0.240 [-0.262, -0.218], the gate stays shut, the loss diagnosed as a tie-break in `docs/notes/claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md`; plus the two defects the played-game smoke caught: the SEA scoring card has no Region, and the table carried flags into pure arithmetic until the sentinel refused

- [The potential verdict: +0.021 [-0.000, +0.042], and the rule says stop](2026-09-23-the-potential-verdict.md) — 2026-09-23 (run 35790097695, 1023 paired seeds: the lower bound is at or below 0, so `potential` does not earn its place and stays 0 -- VP-rebuild step 5 CLOSED, and with it the plan. The +0.021 matching the 512-seed reading exactly is the temptation the pre-registered line exists for; one shard lost a seed and its cause is unrecovered)

- [The refit at current main: candidate, audit, and the rule before the number](2026-09-22-the-refit-at-current-main.md) — 2026-09-22, read 21:21 UTC (**the refit LOST: 0.483 [0.468, 0.498]** over 1152 paired seeds, upper bound below 0.500 -- the rule's third branch, shipped weights stand at 2.795, PR #41 closed and dropped; seats 0.556/0.410 say the loss is mostly the USSR seat; matched_scale 2.793341679085859 CHAINS; the auditor could not rank the fits and play did; and how `uv run pytest` tested the wrong tree)
- [The hold-option grid: nothing above 0 anywhere, and 1.0 costs](2026-09-22-the-hold-option-grid.md) — 2026-09-22 (run 35753235236, 1024 paired seeds: 0.25 -0.004 [-0.012, +0.005], 0.5 -0.005 [-0.018, +0.007], 1.0 **-0.031 [-0.047, -0.016]**; the pre-registered rule's third branch fires, `hold_option` stays 0 in the live hold pricings, and step 3 is told to price flexibility nowhere near a full card's Ops)
- [Status, 2026-09-22: the hold-option grid is in flight, and a `compare_to` arm cannot run alone](2026-09-22-status-the-grid-in-flight.md) — 2026-09-22 (run 35753235236 is the verdict run; the orphan's wave 2 and the two readings of it; three dispatches failed in 15 s on `compare_to 'hold-option-base' is not in this run`, and the fix waits until the grid lands because arm identity is the shard cache's key)
- [The assignment planner: step 3's design](2026-09-22-assignment-planner-design.md) — 2026-09-22 (shape (a): separable prices, exact constraints, solved by DP over subsets; rulings 1/4/5 carried; slices 1-2 BUILT -- `hand_planner.py` + policy's per-turn price table + the ranking lead behind `hand_assignment` at 0, parity oracle green unchanged; and the wiring finding: the space double-attempt is granted by a game effect nothing in `src/` writes)
- [The pi harness, and what to ask of it](2026-09-22-the-pi-harness-and-what-to-ask-of-it.md) — 2026-09-22 (edits are a tool now, not a heredoc; the three skills are BUILT -- `dispatch-reading`, `write-note`, `handoff` -- and the build surfaced four drifts of one shape: skill mirrors, the contract pair, eighteen unindexed notes, and a skill's stale credential claim, all now gated by `tests/test_agent_files.py`. Plus `ci-watchdog`: watch files wake the agent when a CI run lands, and its smoke test caught an uncaught async rejection that killed pi and an error message that named the wrong option)
