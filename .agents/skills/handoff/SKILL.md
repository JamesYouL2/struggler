---
name: handoff
description: Write the end-of-session handoff note -- what landed with its measured size, what is in flight with its pre-registered rules intact, what is open, and the session's own mistakes for the next model. Use when the user says "handoff", "write this up for the next session", "I'm done for now", or asks what to pass on.
---

# The handoff

A handoff is written for a model that was not here. It is a note like any
other -- follow `../write-note/SKILL.md` for the file, the index entry
and the commit -- with a fixed shape. The template this shape comes from
is `docs/notes/claude/2026-09-21-handoff-and-what-to-hand-a-weaker-model.md`.

## 1. What landed

A table: the change, what it does, and its measured size. The measured
number comes from the run that produced it (run id, block, interval) or
says plainly that it is unmeasured. "Merged as `<sha>`" is the anchor
everything else hangs on.

## 2. What is in flight

Run ids and what each will decide -- with **the decision rule quoted as
pre-registered**, verbatim, because a rule re-typed from memory after the
number is visible is not the rule that was registered. Then the two or
three things to check when it lands, **in order** (did the ceiling fire?
did the interim stay its hand?). A finding already visible in a running
run earns its own paragraph.

Also say what a running run cannot settle -- the question the next
session should not expect answered.

## 3. Open, not started

One line each, in the order they should be taken. Include only what is
still live:

- What the maintainer has ruled on goes in as ruled: **dropped is
  dropped** -- do not re-list it as "not queued", which reads as a nudge.
- Anything only the maintainer can do (credentials, write-path 403s,
  expert valuations) -- after checking it is still outstanding
  (`../status/SKILL.md`'s section 3).

## 4. What to pass to a weaker model

**The section worth reading.** The session's own mistakes, ordered by
how much damage getting them wrong does here -- not hidden, not hedged.
Each with the practice that stops it recurring. What belongs here is
what surprised the session: profile to find the work but time unprofiled
to price it; a test that passes with the defect present gates nothing;
verify the way the consumer reads, not the way your tool reads; put the
guard in the path that actually runs; do not move a pre-registered rule
after seeing the number.

If the session made no mistakes that a successor could repeat, say that
too -- do not pad with generic advice.

## Standing discipline

- **One measurement, one telling** across notes; link the earlier one.
- **Correct your own numbers plainly and in place**, recomputed from
  published halfwidths.
- **A title states only what you would defend without the paragraph
  under it.**
- **Waiting is sometimes the action**: before cancelling a run, state
  what the surviving data would say and whether it is already in hand.
- End with where things are verified alive: which CI run ids, which local
  logs under `logs/<topic>/...`, and how to check a local runner
  (`scripts/gate_running.py` -- never `pgrep`, shape 9).
