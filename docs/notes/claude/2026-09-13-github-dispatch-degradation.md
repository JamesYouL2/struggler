# GitHub Actions dispatch failed while the status page said it was fine

The maintainer's report: GitHub has been degraded lately. This is what it
looked like from here on 2026-09-13, and what it does and does not mean for a
queue that runs its games on CI.

## What happened (UTC)

- **08:30** -- the last `workflow_dispatch` that went through
  (`34747874545`, the Blockade fix's gate).
- **From ~08:45** -- every `gh workflow run` for `drift` and `gate` failed
  with `could not create workflow dispatch event: HTTP 500`. The raw call,
  `gh api -X POST repos/JamesYouL2/struggler/actions/workflows/<id>/dispatches`,
  returned `502 Bad Gateway` with body `{"message": "Server Error"}`. The rate
  limit was nowhere near (74 of 5000 used).
- **Throughout** -- githubstatus.com reported *All Systems Operational*, with
  Actions and API Requests green and no incident open. Reading runs, listing
  them, downloading artifacts and `git push` all kept working, and every run
  dispatched before 08:30 kept running to completion.
- A background loop retried both dispatches every two minutes. At 09:08 none
  had gone through.

- **Later, a second symptom.** Dispatch came back (the gate ladder went
  through on the retry loop's sixth try, 09:09; the drift matrix on its
  tenth, 09:17). But the gate run `34749029077` never started: for over an
  hour `gh run list` showed it `queued`, while runs dispatched after it --
  including a gate on another branch -- were assigned runners and finished,
  and nothing else in the repo was in progress. Asked to cancel it, the API
  answered "Cannot cancel a workflow run that is completed"; `gh run view`
  then showed it with no conclusion, no jobs, and an `updatedAt` equal to its
  `createdAt`. A ghost: accepted, listed, never run, and reported in two
  contradictory states. It was re-dispatched as `34753464219`, whose four
  jobs started normally. A run that is accepted is not a run that will
  start, and a run's reported status is not proof it exists.

So the failure was narrow -- the dispatch endpoint, then the queue -- and
invisible to the status page. Anything that reads "is GitHub up" from the status page, or
from the fact that `gh run list` works, would have concluded nothing was
wrong.

## What it was not

Every *failed run* in the repo's last ~40 was ours, checked step by step, not
GitHub's:

| run | workflow | failing step | cause |
| --- | --- | --- | --- |
| 34736918880 | gate | gate against c0ccd95 | a real rejection (0.447) |
| 34730247700 | gate | gate against f492dc3/c7ed9f5 | the `advisory_count` set -e bug, fixed in fd713f1 |
| 34724172492 | tests | pytest | `test_stakes.py:29`, a real test failure |
| 34719667354 | tests | pytest | `access_redundant` passed to `StrategicWeights`, a retired field |
| 34718579739 | drift | drift vs 3955b3e / 05b6690 | a real drift verdict |

No earlier note records a GitHub-side failure either. Today's dispatch errors
are the first here with evidence; "lately" is the maintainer's wider
experience, recorded as theirs.

## The practice

1. **The status page is not evidence.** Check the endpoint you need. A
   dispatch that fails with 500/502 while reads work is a dispatch outage,
   whatever the page says.
2. **Retry dispatches in the background, with a cap, and say when the cap is
   hit.** A queue that dispatches and immediately waits on a run id it never
   got will wait on nothing -- `queue_coup_discount.sh` looks the run up after
   dispatching and logs `gate run: NOT FOUND` rather than hanging.
3. **Classify a failed run by its failing step before blaming GitHub.** All
   five failures above looked like "CI failed" from the run list; none was
   infrastructure.
4. **What is already running is safe.** Dispatch failing does not touch runs
   in progress, their artifacts, or collection -- only new work waits.
5. **Local is the fallback for the items that do not need a runner.** The
   pre-split drift queue went local for this reason; the post-split drift
   matrix and the iran/austria ladder could not, and wait for dispatch.

The queue skill carries the rule (`.claude/skills/queue/SKILL.md`, "A dispatch
can fail while the status page is green").
