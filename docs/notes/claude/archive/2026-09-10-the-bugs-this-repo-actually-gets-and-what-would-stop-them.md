# 2026-09-10 — The bugs this repo actually gets, and what would stop them

Read back over every `fix(...)` commit and the incidents in this file. The
defects are not random: eight shapes account for nearly all of them, and
every one of the eight has now recurred. Listed by how often they have
bitten, with the practice that would have caught each. This is the list to
design against, not a generic checklist.

**Every shape here is gated.** `tests/test_recurring_defects.py` is the
index: it names the tests that make each shape fail, checks those tests
still exist, and reads the counts below -- so recording a new recurrence
here makes the suite ask for the gate. The shapes that had no home
anywhere else are gated in that file too (the sentinel, interleaved
timing, the characterisation-test convention); the rest are listed and
live beside their subject.
