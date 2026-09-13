---
name: queue
description: Build a queue of work to run unattended -- overnight, while the maintainer sleeps, or across any stretch where nobody is watching. Use when the user asks to "queue up" work, "run the full queue", asks what could run "while I'm sleeping" / "without me", or approves a batch of experiments to run back to back.
---

# Building a queue that survives the night

A queue is not a to-do list. It is a program that runs for hours with
nobody watching, on a machine that may not survive, and every property
below exists because the obvious version fails silently.

**Split it first: CI for games that have a workflow, one local script for
the rest.** The local half is serial and commits as it goes. It is not a
plan to execute step by step: the session cannot orchestrate between
steps unattended, so anything not written into the script will not
happen.

## First: which items go to CI

The repo dispatches three game workflows. Each is a matrix with one
isolated runner per entry (4 workers, 300-minute timeout, artifacts kept
30 days):

| Workflow | What it runs | Dispatch |
| --- | --- | --- |
| `gate` | `scripts/gate.sh` against each base | `gh workflow run gate -f bases='["<sha>","<sha>"]'` (optional `-f seeds=`, `-f held=`) |
| `experiments` | weight A/Bs, one arm per job, `--decide` on | arms in `.github/experiments.json`, or one `-f inline='{"slug":..,"weights":..,"seeds":..,"held":..}'`; `held` is required |
| `drift` | `scripts/drift_check.sh` per anchor | `gh workflow run drift -f anchors='["v0.1.0"]' -f seeds=6000-6127`; also a weekly cron |

**Send an item to CI** if it is a gate, a weight A/B or a drift run. The
arms run at the same time and never compete with each other or with this
machine. So three of the local rules below stop applying to them:
- Order by value: every arm starts at once.
- The machine may die: a runner dying loses one arm, not the night.
- Run one item at a time: runners do not share cores.

**Keep an item local** in any of these cases:
- There is no workflow for it: diagnostic scripts, self-play tracers,
  corpus captures.
- It measures *this machine*: timings, or replicating a CI result here.
- It needs code that is not on `origin`.

**Rules that only exist because of CI:**

- **CI runs what is on `origin`, not what is on disk.** A dispatch checks
  out the pushed branch tip. Local commits ahead of `origin` do not exist
  there, and a gate dispatched without them measures the previous code.
  Check `git status -sb` for `ahead N` before dispatching. If the code under
  test is not pushed, ask: pushing is outward-facing and the maintainer's
  call. Dispatching a workflow on this repo is not.
- **Pass SHAs in `bases`, never the default `HEAD~1`.** On a runner it is
  the parent of whatever tip was dispatched, which is a docs commit as
  often as not. That is shape 3 again.
- **A dispatch can fail in seconds.** Gate run 34730247700 died in 17s.
  Check `gh run list --workflow <name> --limit 3` a minute after
  dispatching, not in the morning.
- **Quote a runner's verdict, never its wall-clock.** The hardware is
  shared and its load is unknown.
- **Nothing lands in git by itself.** The workflows have `contents: read`
  and cannot commit, and artifacts expire after 30 days. Collect every run:
  `gh run download <id> -R JamesYouL2/struggler` into gitignored `logs/`,
  then commit a generated note of the numbers, the same as a local item. A
  result that lives only in an artifact is a result that disappears. An
  unattended CI batch therefore still needs a local last step. Either
  leave collection for the morning and say so in the report, or put a
  waiter at the end of the local script (`gh run watch <id>`, then
  download, note, commit), under every local rule.
- **Size against the runner, not this machine.** A runner has 4 workers,
  not 8. Take the arm's time from a finished CI run of the same shape, and
  check it fits inside 300 minutes with room to spare. The upload steps
  run `if: always()`, so a timed-out job still uploads something. What it
  uploads is partial, and nothing in the report says so (audit F4,
  `docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md`). Count the
  games against the plan before quoting any score.

## The rules (local script)

**Commit after every item.** A machine that dies at 3am must leave every
finished result in git. Check what is gitignored first: if reports land
in `logs/`, the commit is a *generated note of the numbers*, not the
report. `scripts/report_note.py` is the worked version.

**Never `set -e`.** A failed item must not abandon the queue. Record the
failure, continue. The one exception is a setup step whose failure makes
everything after it meaningless -- a failing test suite must stop the
queue before it commits anything.

**Nothing may depend on an earlier verdict.** This is the property that
makes a queue safe to run unattended, and it is a real constraint on
what can go in one. If item 4's result would change how item 5 should be
run, they cannot both be in the same queue -- the queue will run item 5
the wrong way and the night is wasted. Ask of every item: *if the one
before it fails, or comes back surprising, is this still the right thing
to run?*

**Pin every comparison base before the first commit.** The queue commits
as it goes, so `HEAD~1` means something different by item 6 than it did
at launch. A gate written against `HEAD~1` compared a change against a
docs commit that already contained it -- the change on both sides,
reporting a dead heat by construction. That is shape 3 in
`docs/notes/claude/bug-shapes.md`, six recurrences. Capture the SHA
first and pass it explicitly.

**Order by value, not by dependency.** The machine may die. Put the item
you would most regret losing first, not the one that unblocks the most
-- unblocking assumes a tomorrow the queue may not reach.

**Size each sample from the effect you expect, and check it is
resolvable at all.** Running several underpowered experiments produces a
pile of null results that teach nothing, at full cost. Two checks before
sizing:

- *What fraction of decisions does this change touch?* A change confined
  to 1.6% of plays cannot move a final score at any affordable sample
  size. That is not a reason to skip it; it is a reason to run it as a
  no-regression check and let its tests be the evidence.
- *What half-width do I actually get?* Fit it from a completed run of
  the same shape, not from another measurement's constant. A mirror
  gate's half-width does not transfer to an unmirrored A/B -- assuming
  it did made a precision table 30% optimistic.

**Make the runner refuse to interpret.** Generated notes state what was
measured and say plainly that they do not say what it means. A script
cannot tell a real effect from a null dressed as one, and an overnight
note that reads like a conclusion will be quoted as one.

## Before launching, verify every dependency

A typo costs the whole night, and the queue will not tell you until
morning. Run each of these by hand first:

- the interpreter path the script uses (`.venv/bin/python -m pytest`,
  not the `uv run` you have been typing)
- every key the script reads out of a report or JSON
- every helper script, on real input, at least once
- `bash -n` on the script, which catches syntax but *not* a function
  used above its definition -- that is a runtime error and has shipped
- what is gitignored, before writing a commit step

## Things that have gone wrong here

- **Editing a running bash script.** Bash reads scripts incrementally by
  file offset, so an edit mid-run can make it execute garbage. Guard the
  edit, and do not trust yourself to remember.
- **Asking `pgrep` whether something is running.** Four recurrences,
  including a guard written specifically to prevent it: `pgrep -f` matches
  the asking process's own command line, and bracketing the pattern does
  not help when the command line contains the plain string elsewhere. Use
  `scripts/gate_running.py` -- walk `/proc`, exclude the whole ancestor
  chain -- or `flock`. Shape 9.
- **`nohup ... &` inside a backgrounded call**, which reports completion
  seconds after launch for a job that runs for hours.
- **Running measurements alongside the queue.** The machine's timings are
  part of the result; contending with your own queue corrupts them. One
  item at a time, and if something must be checked, check it read-only.

## While the queue runs

**A queue that commits with `git add -A` will sweep up anything you
create while it runs**, and file it under that item's message. Writing a
note, a skill or a scratch script during a queue puts it in the next
experiment's commit, where nobody will look for it. Either commit your
own work before the queue's next commit lands -- check how far off that
is -- or have the runner stage explicit paths instead of `-A`.

Checking on a queue is fine, but read-only: reading logs, `git log`,
`ls`. Anything that runs games or tests contends with the queue and
corrupts the timings that are part of its result.

## What does not belong in a queue

- **Anything needing judgement.** Deleting code on an ambiguous
  "ACCEPTED", choosing between two results, deciding whether to ship.
  Leave the decision; queue the measurement.
- **Anything irreversible.** A queue cannot notice it was wrong.
- **Anything that can conflict** -- a rebase, a merge, a force-push.
- **Anything outward-facing.** Publishing, pushing, sending. Unattended
  is exactly when nobody can catch it. That includes the push a CI
  dispatch would need: if the code is not on `origin`, the item waits
  for the maintainer or runs locally.

## Reporting it back

End with the queue as a table giving, per item:
- where it runs: local, or the CI run id
- its state and ETA
- who collects it, if it runs on CI

Then say how the local half is verified alive (the STATUS file,
`scripts/gate_running.py`) and how the CI half is (`gh run list`). Then use the `status` skill's shape -- the
ranked top three first. A finished queue item belongs in the prose once;
it does not stay on the list.
