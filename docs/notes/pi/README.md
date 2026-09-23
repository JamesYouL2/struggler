# Pi working notes

Sessions running under the pi harness keep their notes here. Each agent
has its own tree -- Claude's is `docs/notes/claude/`, the audit's is
`docs/notes/codex/` -- and they are kept separate on purpose
(maintainer's rule, 2026-09-22). One file per topic; recent entries sit
here, older ones under `archive/`. `bug-shapes.md`, the defect registry
a test parses, stays at its stable path in `docs/notes/claude/`
regardless of who records a new shape.

## Contents

- [The potential verdict: +0.021 [-0.000, +0.042], and the rule says stop](2026-09-23-the-potential-verdict.md) — 2026-09-23 (run 35790097695, 1023 paired seeds: the lower bound is at or below 0, so `potential` does not earn its place and stays 0 -- VP-rebuild step 5 CLOSED, and with it the plan. The +0.021 matching the 512-seed reading exactly is the temptation the pre-registered line exists for; one shard lost a seed and its cause is unrecovered)

- [The refit at current main: candidate, audit, and the rule before the number](2026-09-22-the-refit-at-current-main.md) — 2026-09-22, read 21:21 UTC (**the refit LOST: 0.483 [0.468, 0.498]** over 1152 paired seeds, upper bound below 0.500 -- the rule's third branch, shipped weights stand at 2.795, PR #41 closed and dropped; seats 0.556/0.410 say the loss is mostly the USSR seat; matched_scale 2.793341679085859 CHAINS; the auditor could not rank the fits and play did; and how `uv run pytest` tested the wrong tree)
- [The hold-option grid: nothing above 0 anywhere, and 1.0 costs](2026-09-22-the-hold-option-grid.md) — 2026-09-22 (run 35753235236, 1024 paired seeds: 0.25 -0.004 [-0.012, +0.005], 0.5 -0.005 [-0.018, +0.007], 1.0 **-0.031 [-0.047, -0.016]**; the pre-registered rule's third branch fires, `hold_option` stays 0 in the live hold pricings, and step 3 is told to price flexibility nowhere near a full card's Ops)
- [Status, 2026-09-22: the hold-option grid is in flight, and a `compare_to` arm cannot run alone](2026-09-22-status-the-grid-in-flight.md) — 2026-09-22 (run 35753235236 is the verdict run; the orphan's wave 2 and the two readings of it; three dispatches failed in 15 s on `compare_to 'hold-option-base' is not in this run`, and the fix waits until the grid lands because arm identity is the shard cache's key)
- [The pi harness, and what to ask of it](2026-09-22-the-pi-harness-and-what-to-ask-of-it.md) — 2026-09-22 (edits are a tool now, not a heredoc; the three skills are BUILT -- `dispatch-reading`, `write-note`, `handoff` -- and the build surfaced four drifts of one shape: skill mirrors, the contract pair, eighteen unindexed notes, and a skill's stale credential claim, all now gated by `tests/test_agent_files.py`. Plus `ci-watchdog`: watch files wake the agent when a CI run lands, and its smoke test caught an uncaught async rejection that killed pi and an error message that named the wrong option)
