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

Three workflows earn one, in order of how much damage doing them wrong
does here:

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
2. **`write-note`** -- one file per topic in `docs/notes/claude/`, an
   entry in its `README.md`, and the house conventions: a title states
   only what the body defends (the retracted intransitivity note is the
   cost of getting that wrong); one measurement has one telling (the
   fresh-block note cut its own copy rather than keep it "for
   completeness"); corrections go in place with the corrected number
   recomputed from published halfwidths, not from impression.
3. **`status-and-handoff`** -- what is running, what is blocked on the
   maintainer (the `EXPERT_ASKS.md` list, the 403 push items), what is
   ready to dispatch, and the session's own mistakes in the order the
   next model will remake them. The 2026-09-21 handoff's third section
   is the template.

Build them as `SKILL.md` + `scripts/` where a script earns its place
(the polling loop, the note scaffolding), with relative paths per the
skill structure. Keep the skills thin and point at the docs for depth --
the binding contracts stay in `docs/`, and a skill that starts
*restating* `docs/ARCHITECTURE.md` becomes a second source of truth,
which is bug shape territory (`bug-shapes.md`).

## What not to move into a skill

Anything a test can enforce. The rule stands: a workflow step that can
be a test must be a test, and `tests/test_recurring_defects.py` parsing
`bug-shapes.md` is the proof of the pattern. Skills carry the steps
between the tests -- judgement, ordering, and the reading discipline --
not the invariants.
