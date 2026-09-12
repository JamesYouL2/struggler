---
name: status
description: Report what is running, what is blocked on the maintainer, and what is ready but needs the maintainer to execute. Use when the user asks for status, "what's running", "what's in the queue", "anything you need from me", "status check", or asks what is next -- and at the end of any long autonomous stretch.
---

# Status check

Open with **the top three priorities overall, ranked** -- across all
three sections, one line each, hardest-first by what it unblocks rather
than by what is easiest to finish. Then the three sections below, always
these three, always in this order, always all three even when one is
empty. The order is by what costs the maintainer time: what they must
decide, then what they can ignore, then what they must do.

The ranking is the part that takes judgement. It is not the queue in
queue order: a blocked decision that gates three items outranks a
finished-but-ungated change, and a measurement that would tell us
whether a whole line of work is worth anything outranks both. Say what
each one unblocks, or it is a list rather than a ranking. Three, not
five -- if everything is a priority the ranking has said nothing.

## 1. Things needed from you

Judgement, domain knowledge, or a decision. Things only the maintainer
can supply -- a Twilight Struggle valuation, a call on whether a feature
ships, whether a documented simplification should stay.

Each item: **the question, the options, and my recommendation.** Never
just the question. A bare question makes the maintainer do the framing
work; state which way I would go and why, so the reply can be one word.

Mark each one with what it blocks. "Blocks nothing, answer whenever" and
"blocks the next three items" are different asks and should not look
alike.

## 2. Things I'm running without you

Work in flight or queued that needs no input. For anything *running*,
say how it is running and how I know it is alive -- a pid, a worker
count, the step it is in. "The gate is running" is not a status; it is a
belief, and it has been wrong (see the failure modes below).

Give the expected wall-clock so the maintainer knows whether to wait.

For anything *queued*, one line each, in the order I will do them.

## 3. Things you're waiting on me to run

Ready work I cannot execute in this environment. Distinct from section 1:
nothing is being *decided*, the maintainer is the only one with the
credential, the machine, or the authority.

Standing members of this section:

- **`git push`** -- no credentials here. `git push` cannot read a
  username for the HTTPS remote and `gh` is not logged in. Before
  listing it, check whether it is actually still outstanding:
  `git ls-remote origin refs/heads/main` against `git rev-parse HEAD`.
  The maintainer has pushed on their own before, and reporting an
  already-landed push as outstanding is noise.
- **MCP connector auth** (Gmail, Google Calendar) -- needs the OAuth
  flow in an interactive session.

## Checking before claiming -- the failure modes this exists for

Every line in section 2 is a claim about the world, and each of these
has been wrong at least once here:

- **`nohup ... &` inside a backgrounded Bash call.** The harness watches
  the wrapper, which exits at once, so a "completed" notification
  arrives seconds after launch for a job that runs for forty minutes.
  Background the job directly instead, and treat any suspiciously fast
  completion as a wrapper exit until the log says otherwise.
- **`pgrep -f 'gate.sh'` matches itself** and reports a finished gate as
  running. Four times now, and the advice that used to sit here -- read
  `pgrep -af`, or bracket the pattern as `[g]ate.sh` -- failed too: the
  bracket protects the pattern from itself and does nothing about the
  rest of your own command line, so a guard also containing
  `bash -n scripts/gate.sh` still matched. **Do not ask `pgrep`.** Use
  `scripts/gate_running.py`, which walks `/proc` and excludes the whole
  ancestor chain, or `flock`. Shape 9 in
  `docs/notes/claude/bug-shapes.md`, gated by
  `tests/test_process_checks.py`.
- **Exit code 0 from the launcher is not the job's verdict.** The gate's
  verdict is its own exit status, and the log's last line. Read the log.
- **A gate that "passed" may have crashed.** `summ` reports a step that
  produced no result as a failure with exit 3, but only if the log is
  actually read to the end.

So: before writing section 2, check each running item and say what the
check returned. Before writing section 3, check whether the blocker is
still real.

## What does not belong

- Work already finished. Status is what is open; a finished item goes in
  the prose, once, and never appears again.
- Anything the maintainer said not to do. Dropped is dropped -- do not
  re-list it as "not queued", which reads as a nudge.
- Restating a gate result as a strength claim. The gate accepts what it
  cannot show to be a regression; "ACCEPTED" means *not measurably
  worse*, and section 1 is where the ship/no-ship call goes.
