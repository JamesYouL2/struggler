# The pi harness, and what to ask of it

2026-09-22. This session runs in pi rather than the Codex CLI the
"Session environment" entries in `AGENTS.md` describe. The project rules
do not change with the harness -- but the failure modes do, and the
harness can carry more of the recurring workflows than we currently ask
of it. Read `AGENTS.md`'s session-environment sections alongside this;
where they disagree on a mechanism, this note is the pi-side correction.

## What changes mechanically

- **Edits are a tool, not a heredoc.** `AGENTS.md` warns about editing
  via `python` + quoted heredocs and a stray backslash having shipped a
  bug. pi has a targeted `edit` tool (exact-match replacements) and a
  `write` tool. Use them. The heredoc class of defect simply does not
  exist here -- which is worth saying in the other direction too: a
  habit worth encoding because the *old* warning is still in the file
  and a weaker model may follow it under a harness where it is moot.
- **Long runs**: `bash` takes a timeout; commands can run long directly
  and log to `logs/<topic>/...` per the standing rule. No `&`
  backgrounding anywhere -- that rule is harness-independent.
- **Notes are per-agent.** This tree is `docs/notes/pi/`; Claude's is
  `docs/notes/claude/`, the audit's `docs/notes/codex/`, and the
  maintainer keeps them separate on purpose (2026-09-22). `write-note`
  has the list; the shared note generators take `NOTES_DIR`.
- Everything else in `AGENTS.md` holds verbatim: `uv run` for all
  Python, gates need explicit maintainer approval before dispatch, logs
  under `logs/`, docs commit+push unasked.

## Skills: the part worth using

pi loads skills (Agent Skills standard) as progressive disclosure -- only
names and descriptions sit in context; the full instructions load when a
task matches, via `read`, or on demand as `/skill:name [args]`. Project
skills live in `.pi/skills/` or `.agents/skills/` (after the project is
trusted), global ones in `~/.pi/agent/skills/` or `~/.agents/skills/`;
Claude Code / Codex skill directories can be mounted through settings, so
none of this is pi-only.

The value for this repo is not the mechanism, it is **where the
discipline lives**. The 2026-09-21 handoff's ten items are exactly the
knowledge that keeps getting re-taught to each new session; a skill is
read every time the workflow triggers, and `AGENTS.md` is read once at
startup and competes with everything else in the window. The rule "twice
means a test" is about code. For workflow, the equivalent of a test is a
skill that fails to load the wrong habit because the right one is written
into its steps.

Three workflows earned one, in order of how much damage doing them wrong
does here -- and all three are built (`.agents/skills/`, mirrored to
`.claude/skills/`): `dispatch-reading`, `write-note` and `handoff`,
alongside the three that already existed (`queue`, `status`,
`analyze-llm-game`).

1. **`dispatch-reading`** -- dispatch a gate or an `experiments` arm and
   read its verdict. It should carry: the `compare_to` same-run shape
   (today's [status note](2026-09-22-status-the-grid-in-flight.md) has
   the fifteen-second assertion that found it); `decide=0` whenever the
   precise score matters; waves on for a question, `waves: false` +
   `no_cache: true` for a LEVEL reading; quote the pooled interval, not
   a shard's; poll `gh run view --id --json status,conclusion` and
   confirm the verdict line in the log rather than trusting the exit
   code; **and the pre-registered rule discipline** -- the decision rule
   is written in the arm's `context` before dispatch and does not move
   after the number is visible. That last item is where the temptation
   lives (handoff item 7), so it belongs in the checklist the agent
   reads, not in a note it may not open.
2. **`write-note`** -- one file per topic in the writing agent's own
   tree (the maintainer's rule, 2026-09-22: notes are per-agent;
   pi's is `docs/notes/pi/`), an entry in its `README.md`, and the house
   conventions: a title states
   only what the body defends (the retracted intransitivity note is the
   cost of getting that wrong); one measurement has one telling (the
   fresh-block note cut its own copy rather than keep it "for
   completeness"); corrections go in place with the corrected number
   recomputed from published halfwidths, not from impression.
3. **`handoff`** -- what landed with its measured size, what is in
   flight with its pre-registered rules quoted as written, what is open
   (dropped is dropped), and the session's own mistakes in the order the
   next model will remake them. The 2026-09-21 handoff's third section
   is the template. **`status` already covered the live report and was
   left alone** -- a second status skill would itself be the shape this
   repo warns about.

Each is one `SKILL.md` and no scripts. The polling loop is `gh run
watch`; the note scaffolding is the `write` tool; and the one piece of
machinery this work actually needed went to `scripts/index_note.py`
(below) rather than into a skill. Keep skills thin and point at the docs
for depth -- the binding contracts stay in `docs/`, and a skill that
starts *restating* `docs/ARCHITECTURE.md` becomes a second source of
truth, which is bug shape territory (`bug-shapes.md`).

## What the build found (2026-09-22)

Building the three surfaced four drifts of the exact shape this repo
keeps a defect registry for -- two copies of one rule, one of them
stale. All four are gated now by `tests/test_agent_files.py`, and every
one of its gates was checked by putting its defect back:

- **The skill mirrors had drifted.** `.agents/skills/` and
  `.claude/skills/` carry one tree under two roots (each harness hardcodes
  one), and the `.claude` half had learned that `docs/notes/Codex/` is now
  `docs/notes/claude/` while the `.agents` half still linked a directory
  that no longer exists. The trees are byte-identical or the suite fails.
- **`AGENTS.md` and `CLAUDE.md` had drifted the same way** -- one carrying
  the CI workflows section and current timings, the other a broken notes
  path and the Logs bullet. They are one byte-identical document under two
  names now, and their own tail says so.
- **Eighteen notes were never indexed** -- sixteen of them generated by
  `scripts/collect_ci.sh` and `scripts/queue_*.sh`, which wrote the note
  and never its index line. The index gate found all eighteen on its
  first run. They are indexed retroactively at the README's tail; every
  writer now calls `scripts/index_note.py` before its commit.
- **The `status` skill claimed `git push` is impossible** ("no credentials
  here") -- true of one sandbox, false under pi on this box. What
  actually needed a human here was tag creation and branch deletion (403
  on the write path). It now says check, do not assume.

- **And two drifts the build made in itself.** The skill mirror was run
  in the same tool batch as edits to its source tree; the copy executed
  first, and a later restore-from-mirror clobbered the edits.
  `git status` disagreeing with what was believed written is what
  caught it -- and the mirror test passed throughout, because both trees were
  identically wrong. Identity is not correctness. Sequence-dependent
  steps (edit, then copy) do not belong in one parallel batch. Then the
  fix was committed by chaining `pytest | tail -2 && git commit`: `tail`
  exits 0, so the red gate could not stop the commit, and a broken
  citation (`scripts/queue_*.sh` parses as the path `scripts/queue_`)
  went out in `149efb8`. Read the gate's exit code on its own before
  any step that must not follow a failure -- piping it into anything
  makes the pipe's status the gate's.

The lesson to keep is the third one. The gate was written to prevent
future drift and found eighteen past ones on its first run. A convention
that is not a test is a convention nobody has checked lately.

## What not to move into a skill

Anything a test can enforce. The rule stands: a workflow step that can
be a test must be a test, and `tests/test_recurring_defects.py` parsing
`bug-shapes.md` is the proof of the pattern. Skills carry the steps
between the tests -- judgement, ordering, and the reading discipline --
not the invariants.
