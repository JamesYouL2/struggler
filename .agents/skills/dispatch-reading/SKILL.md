---
name: dispatch-reading
description: Dispatch a gate, an experiment arm or a drift run on CI, and read its verdict against a rule written before the number was visible. Use when the user asks to gate a change, run an A/B or an ablation, price a weight grid, dispatch experiments, or read and interpret a run's result.
---

# Dispatching a reading, and reading it

The `queue` skill (`../queue/SKILL.md`) owns unattended batches and has
the workflow table. This skill owns the single question: what shape the
dispatch takes, and what the number that comes back may be quoted as.

## Before dispatching

- **Gates need the maintainer's explicit approval** (standing pref).
  Dispatching a workflow on this repo is not outward-facing; pushing code
  is (`../queue/SKILL.md`).
- **CI runs what is on `origin`.** `git status -sb` for `ahead N` first;
  a gate dispatched without the commits under test measures the previous
  code.
- **Pass SHAs in `bases`, never the default `HEAD~1`** -- on a runner it
  is the parent of whatever tip was dispatched, often a docs commit.
  Shape 3 in `docs/notes/claude/bug-shapes.md`.
- **One verdict per branch, no bundling.** A gate reads one change
  bundle; two unrelated changes measured together cannot be attributed.

## The question decides the inputs

| Question | Dispatch |
| --- | --- |
| Is this change bundle a regression? | `gh workflow run gate.yml --ref <branch> -f bases='["<SHA>"]' -f vary=0` |
| What is a weight/feature worth? | `experiments.yml`, arms in `.github/experiments.json`, `-f only=<slug>[,<slug>...]` (or `-f inline='{...}'` for one-off) |
| Where are the anchors now? | `drift.yml` -- every anchor as an anchored arm, level reading, no waves |

- **`decide=1` is the default** and curtails ~15% once the verdict is
  stable; pass `decide=0` when the precise score is the result.
- **Waves are on by default**: an arm stops at half its seeds if the look
  settles the question. A question being asked wants waves; a LEVEL
  reading wants `waves: false` and `no_cache: true` (what `drift.yml`
  passes).
- **Shards are cached on arm identity** (`scripts/arm_identity.py`): a
  re-dispatched unchanged arm replays nothing. The corollary that bites:
  **do not edit an arm's entry -- its `context` included -- while any run
  is quoting it**, or its identity moves and the cache stops matching.
- **A `compare_to` arm must be dispatched in the same run as its
  target**: `only=hold-option-base,hold-option-025,...`, one dispatch.
  One dispatch per arm is the natural reading of `experiments.json`'s
  "one entry per arm" and it fails at plan time --
  `AssertionError: ...: compare_to '...' is not in this run`. Three
  dispatches lost 15 s each finding this on 2026-09-22
  (`docs/notes/claude/2026-09-22-status-the-grid-in-flight.md`).
- **Smoke the machinery before a real run rides on it**: a 4-seed
  dispatch finds in ten minutes what a 1024-seed one finds two hours in,
  or not at all.

## The rule comes before the number

Write the decision rule into the arm's `context` (or the gate question)
before dispatching. Once the number is visible, **the rule does not
move**. It read -0.001 against a pre-registered line once and the weight
stayed -- not because a thousandth means anything, but because a rule
that moves once you can see the number is not a rule. The temptation is
strongest exactly when the gap is smallest. If a reading lands and the
rule says stop, stop; record the disappointment in the note instead.

## Reading it

- **Quote the pooled interval** (`scripts/pool_reports.py`), never one
  shard's number. A wave-stopped arm reports on half its seeds
  deliberately; the run summary says which.
- **Paired reads use `compare_to`'s seed-by-seed difference** -- two
  overlapping independent intervals are not a comparison.
- **Levels are not comparable across blocks**; only paired differences on
  one block are.
- **The verdict is the log line, not the exit code.** Confirm the
  ACCEPTED / REJECTED line in the collect or summ step before acting on
  it. Workflow `success` is the ACCEPT for a gate; the run's verdict for
  an experiment is the summarise step's artifact.
- **A dispatch can fail in seconds** -- check `gh run list --limit 3` a
  minute after dispatching -- and a dispatch can fail while the status
  page is green (`../queue/SKILL.md`, and
  `docs/notes/claude/2026-09-13-github-dispatch-degradation.md`).
- **Quote a runner's verdict, never its wall-clock.** Shared 4 vCPU;
  `gate.yml`'s own header says the timings do not survive the move.
  Timing results stay local and alone.

## Waiting is sometimes the action

Before cancelling a slow or stalled run, ask what the surviving data
would say and whether that is already in hand. A job timeout destroys
exactly what a cancel does. A shard at 141 minutes was nearly cancelled
once; the run it belonged to read on 15 of 16 shards and the cancelled
one was the only shard that could still have moved the number.

## Reporting the reading

Mean with its interval, the run id, the seed block, the opponent or
anchor, and **what it does not settle** -- in that order, one paragraph.
Do not restate ACCEPTED as a strength claim: the gate accepts what it
cannot show to be a regression (`../status/SKILL.md`).
