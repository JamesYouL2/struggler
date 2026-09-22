---
name: write-note
description: Write a working note under docs/notes/claude/ -- one file per topic, indexed in its README -- to the house conventions. Use when recording a finding, a run's verdict, a correction, a defect shape, a plan, or any session record the next model will read.
---

# Writing a note

The notes are the memory of this project. Their conventions exist
because each one was once violated in a way that cost something.

## Where and what

- **`docs/notes/claude/`** for strategy and process work.
  `docs/notes/codex/` is the audit's -- do not write there. Older
  entries live under `archive/`; their index lines stay where they are.
- **One topic per file.** `YYYY-MM-DD-<slug>.md`. If a draft covers two
  findings, it is two notes.
- **One measurement has one telling.** A second note that quotes a
  reading the first already reported links to it instead -- a second
  telling is the shape this repo keeps getting bitten by. (A landing
  record may describe *what shipped* around a measurement whose *reading*
  lives elsewhere; name which is which.)

## Index it

Add a bullet at the top of the Contents list in
`docs/notes/claude/README.md`, with the date and one parenthetical of
what the note actually established. **The suite fails on an unindexed
note** (`tests/test_agent_files.py`), so this is not a convention one may
forget. A note a script wrote (`scripts/report_note.py`,
`scripts/collect_ci.sh`, `scripts/queue_*.sh`) is already indexed -- the
writers call `scripts/index_note.py` before committing -- so this is
only a hand step for hand notes.

## House rules

- **The title states only what the body defends.** A title that outran
  its evidence -- *The intransitivity was the access scale leak*, whose
  own body said the inference was confounded -- needed RETRACTED in the
  title a day later. State in a title only what you would defend without
  the paragraph under it.
- **Quote what was measured**, with run ids, commits and the seed block;
  say when a number is arithmetic over two runs rather than a paired arm.
- **Corrections go in place**, with the corrected number recomputed from
  published halfwidths, not from impression -- and the correcting note's
  index line says what it corrects. Retracted notes are kept for the
  record (paths get cited from `.github/experiments.json`), with
  RETRACTED in the title.
- **State plainly what a reading does not settle.** That paragraph is
  what the next session plans from.
- **Say when a win is marginal.** "2.1%, and one revert undoes it" is a
  different sentence from "18% fewer calls", and the first one is the
  honest one.
- English, ISO dates, and the evidence links as inline code paths.

## Adjacent registries

- **`docs/notes/claude/bug-shapes.md`** is the defect registry at a
  stable path (`tests/test_recurring_defects.py` parses it). Add a shape
  when something recurred -- twice is the signal -- with the practice
  that stops it. The suite then asks for the gate that makes the shape
  fail if it comes back. Never move the file; never renumber shapes in
  prose that tests cite.
- **`docs/EXPERT_ASKS.md` / `docs/EXPERT_STRATEGY.md`** change only with
  the maintainer's input.

## Mechanics

- Commit and push docs unasked (standing pref); the commit message is in
  English and says what the note establishes, not that a note was added.
- What goes in git is the note; the raw report or run output goes in
  gitignored `logs/<topic>/...`.
- **Do not reformat a file you are appending to.** A `json.dumps(indent=1)`
  round-trip once rewrote 700 lines of `.github/experiments.json` and
  buried a 21-line change. Insert by text (`edit` tool), verify with a
  read.
