# Pi working notes

Sessions running under the pi harness keep their notes here. Each agent
has its own tree -- Claude's is `docs/notes/claude/`, the audit's is
`docs/notes/codex/` -- and they are kept separate on purpose
(maintainer's rule, 2026-09-22). One file per topic; recent entries sit
here, older ones under `archive/`. `bug-shapes.md`, the defect registry
a test parses, stays at its stable path in `docs/notes/claude/`
regardless of who records a new shape.

## Contents

- [Status, 2026-09-22: the hold-option grid is in flight, and a `compare_to` arm cannot run alone](2026-09-22-status-the-grid-in-flight.md) — 2026-09-22 (run 35753235236 is the verdict run; the orphan's wave 2 and the two readings of it; three dispatches failed in 15 s on `compare_to 'hold-option-base' is not in this run`, and the fix waits until the grid lands because arm identity is the shard cache's key)
- [The pi harness, and what to ask of it](2026-09-22-the-pi-harness-and-what-to-ask-of-it.md) — 2026-09-22 (edits are a tool now, not a heredoc; the three skills are BUILT -- `dispatch-reading`, `write-note`, `handoff` -- and the build surfaced four drifts of one shape: skill mirrors, the contract pair, eighteen unindexed notes, and a skill's stale credential claim, all now gated by `tests/test_agent_files.py`)
