# Pi working notes

Sessions running under the pi harness keep their notes here. Each agent
has its own tree -- Claude's is `docs/notes/claude/`, the audit's is
`docs/notes/codex/` -- and they are kept separate on purpose
(maintainer's rule, 2026-09-22). One file per topic; recent entries sit
here, older ones under `archive/`. `bug-shapes.md`, the defect registry
a test parses, stays at its stable path in `docs/notes/claude/`
regardless of who records a new shape.

## Contents

- [The refit at current main: candidate, audit, and the rule before the number](2026-09-22-the-refit-at-current-main.md) — 2026-09-22 (branch `exp/refit-country-weights` at cec39ca + the candidate; run 35777206185 = `refit-vs-shipped`, 1152 seeds; matched_scale 2.793341679085859 CHAINS; the auditor cannot rank the two fits on identical positions so play decides; pre-registered rule quoted; and how `uv run pytest` tested the wrong tree)
- [The hold-option grid: nothing above 0 anywhere, and 1.0 costs](2026-09-22-the-hold-option-grid.md) — 2026-09-22 (run 35753235236, 1024 paired seeds: 0.25 -0.004 [-0.012, +0.005], 0.5 -0.005 [-0.018, +0.007], 1.0 **-0.031 [-0.047, -0.016]**; the pre-registered rule's third branch fires, `hold_option` stays 0 in the live hold pricings, and step 3 is told to price flexibility nowhere near a full card's Ops)
- [Status, 2026-09-22: the hold-option grid is in flight, and a `compare_to` arm cannot run alone](2026-09-22-status-the-grid-in-flight.md) — 2026-09-22 (run 35753235236 is the verdict run; the orphan's wave 2 and the two readings of it; three dispatches failed in 15 s on `compare_to 'hold-option-base' is not in this run`, and the fix waits until the grid lands because arm identity is the shard cache's key)
- [The pi harness, and what to ask of it](2026-09-22-the-pi-harness-and-what-to-ask-of-it.md) — 2026-09-22 (edits are a tool now, not a heredoc; the three skills are BUILT -- `dispatch-reading`, `write-note`, `handoff` -- and the build surfaced four drifts of one shape: skill mirrors, the contract pair, eighteen unindexed notes, and a skill's stale credential claim, all now gated by `tests/test_agent_files.py`)
