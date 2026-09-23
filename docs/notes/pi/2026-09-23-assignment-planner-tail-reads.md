# The assignment planner: tail reads before the number, and the arm in flight

Run **35814771005** (`hand-assignment-{base,on}`) is playing block
78000-79023 + held 89000-89127 against `bc5ef93`, paired. The decision
rule is pre-registered verbatim in `hand-assignment-on`'s `context` and
will be applied here when the number lands. What follows is the
*before-the-number* evidence, written now so the verdict cannot
retro-fit it.

> **RESOLVED, read by a later session.** The number landed: paired
> **-0.240 [-0.262, -0.218]** at 1152 shared seeds, so the rule's second
> branch fired and **the gate stays shut**. The USSR tail shape below did
> not translate into play strength; the reason is
> [the planner plays its hand in alphabetical order](../claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md) --
> a tie-break defect in how the plan is read, not a verdict on allocation.

## The tail at 0.25, before and after (`scripts/measure_last_exit.py`)

Same 32 seeds (42000-42031), cornered = whole-hand risk >= 0.25, run
2026-09-23 before dispatch (full outputs in `logs/hold-planner/`,
gitignored -- the numbers live here):

| seat | shipped (`hand_assignment` 0) | planner on (1.0) |
| --- | ---: | ---: |
| US touching 0.25 | 4/32 (0.125) [0.050, 0.281] | 5/32 (0.156) [0.069, 0.318] |
| USSR touching 0.25 | 6/32 (0.188) [0.089, 0.353] | **3/32 (0.094)** [0.032, 0.242] |
| USSR median round / turn of the closing | 31 / 6 | **55 / 9** |

Read honestly: **the intervals overlap heavily and 32 seeds decides
nothing.** What is visible is the shape the design predicted -- the
design said the gain should show "where a third of USSR seat-games touch
0.25 whole-hand risk", and the USSR tail halves in exactly that seat
while the US tail ticks up. The cornered USSR cases also close *later*
under the planner (median turn 6 -> 9): the same cards, allocated
together, defer the closing. That is a direction and a story, not a
measurement; the paired arm is the measurement.

## The arm

`hand-assignment-base` / `hand-assignment-on`, one dispatch (the
`compare_to` rule), `hand_assignment` 1.0 -- a **gate, not a dial**. The
rule as registered: paired lower bound above 0 means the allocation
beats per-card pricing and the planner ships (gate first, then the
default flips and step 4 asks the DP question); at or below 0 means it
does not, at a sample that can say so. The honest prior is in the
context too: the last three measured wins here were +0.039, +0.031 and
+0.043, and none was a search.

## Two defects the played-game smoke caught first

Recording them because the fixtures could not have: `_plan_gain` keyed
`SCORING_CARD_REGION` on Southeast Asia Scoring, which has no `Region`
(fixed by letting unmapped scoring cards shape no gain -- the right
degenerate answer); and the price table carried the scorer's
certain-outcome **flags** into the solver's sums, where the sentinel
refused the arithmetic and named its own fix (`priced()` at the
boundary). Both are in the wiring test now, which also learned that the
optimal disposal of a certain-defeat opponent card is the **space**
slot -- the test expectation was wrong there, not the plan.

## When the number lands

Apply the rule as quoted. If it clears: the default flips and the note
records what the allocation bought beyond the tail read. If it does not:
the gate stays shut, the tail read stands as an unconfirmed direction,
and step 4 (does it reproduce the DP's risks?) is not reached.
