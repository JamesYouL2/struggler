# Working on struggler

Project documentation lives in `docs/`. Read the relevant document before
changing the area it covers — they are the binding contract, not background
reading, and a change to what they specify should update them in the same
commit.

| Document | Read it before touching |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The decision stack, the public API, `Engine`, core types |
| [docs/CARDS.md](docs/CARDS.md) | `events.py`, `cards.json`, anything card-related |
| [docs/BOTS.md](docs/BOTS.md) | `bots/`, the `Player` protocol, physical mode |
| [docs/STRATEGIC_AI.md](docs/STRATEGIC_AI.md) | `bots/strategic/policy.py`, `bots/strategic/evaluator.py`, the value function and its snapshot contract |
| [docs/TESTING.md](docs/TESTING.md) | Adding or changing any test |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Before "fixing" something that may be a documented simplification |
| [docs/RULES_SOURCES.md](docs/RULES_SOURCES.md) | Any rules question: the card face, the rulebook, the FAQ, and the rulings this engine rests on |
| [docs/notes/claude/](docs/notes/claude/) | Bot strategy work: one file per topic, indexed by its `README.md`, older entries under `archive/`. `bug-shapes.md` is the defect registry and has a stable path because a test parses it. (Each agent keeps its own notes tree -- pi's is `docs/notes/pi/` -- and Codex's audit is `docs/notes/codex/`; the Rust plan is `docs/RUST_PORT_PLAN.md`.) |
| [docs/EXPERT_STRATEGY.md](docs/EXPERT_STRATEGY.md) | Outside strategy references (Sankt, Ziemowit) before calibrating a weight to "what strong players do" -- including what those sources do *not* say |
| [.github/workflows/](.github/workflows/) | Running a gate, a drift check, a weight A/B or the full suite. Each workflow's header says what a hosted runner does that the one local box cannot, and `gate.yml`'s says which readings survive the move (the verdict) and which do not (the clock). Prefer CI; it is why these exist. |
| [docs/EXPERT_ASKS.md](docs/EXPERT_ASKS.md) | What the maintainer still needs to price, ranked by what it unblocks, with current coverage per period |

The five architectural mandates in `docs/ARCHITECTURE.md` are
non-negotiable. Code referring to "mandate #3" means that list. An
implementation that violates one is wrong regardless of whether it passes
the tests.

## Conventions

- **Python**: 3.12+.
- **Environment**: `uv` (`uv.lock`, `.venv/`). Run everything through it --
  `uv run pytest`, `uv run python ...`. The system `python3` has none of the
  dependencies, so a bare `python3 -m pytest` fails with `No module named
  pytest`; that is a missing `uv run`, not a broken checkout. `environment.yml`
  (conda) and `pip install -e ".[test]"` still work but are not what this
  repo is developed against.
- **CI runs the expensive things; read `.github/workflows/` before starting
  one locally.** Four workflows, each with a header explaining what it is
  for and what a hosted runner can do that the one local box cannot:
  `tests.yml` (the full suite, on every push and PR), `gate.yml`
  (`workflow_dispatch` with a JSON list of `bases`, one job per base -- the
  local `gate.sh` holds a machine-wide lock, and that lock is a property of
  having one machine, not of the gate), `drift.yml` (every anchor as an anchored
  `experiments.yml` arm, 1024 seeds sharded, with the canary's verdict on
  the pooled readings) and
  `experiments.yml` (arms from `.github/experiments.json`, cut into
  128-seed shards so an arm can be 1024+ seeds, played against HEAD's
  defaults or an `anchor` revision, pooled by `scripts/pool_reports.py`).
  Two things make a dispatch cheaper than it looks and both change what a
  reading means, so read them before quoting one: shards are **cached** on
  their identity (`scripts/arm_identity.py`), so re-dispatching an unchanged
  arm replays nothing; and arms run in **two waves**, with the second played
  only where the first did not settle the question
  (`scripts/wave_verdict.py` -- an arm that stopped early reports on half
  its seeds, deliberately, and the run summary says which). `no_cache: true`
  replays anyway and `waves: false` plays everything, which is what a LEVEL
  reading wants; `drift.yml` passes it. Push and dispatch instead of occupying the
  maintainer's cores for an hour. The exception is anything whose RESULT is a
  wall-clock number: `gate.yml`'s own header says the verdict survives the
  move and the timings do not, because a shared 4 vCPU runner's clock means
  nothing. Verdicts, suites and A/Bs go to CI; quotable timings stay local
  and alone.
- **Tests**: `uv run pytest`, plus `hypothesis` for property-based tests. Run
  the full suite before committing -- push and let `tests.yml` do it, or run
  it locally if you are not pushing yet. ALWAYS RUN THE WHOLE THING.
  Last timed at **3:49 for 1121 tests on an idle 4-core box (2026-09-21)**,
  of which `test_parity_corpus.py` is 2:02 at 401 records -- 53% of the
  suite -- and `test_poke_rate.py` 0:28.

  **That is not faster than the 5:30 below; it is a different machine.**
  The previous reading was 915 tests at 5:30 on an idle *8-core* box
  (2026-09-17), `test_parity_corpus.py` 3:41 of it. Four cores against
  eight, 1121 tests against 915: the two numbers do not divide into a
  speedup and nobody should try. `sample_machine` exists for exactly this,
  and the core count is now part of the reading for the same reason the
  idleness is.

  `test_parity_corpus.py` was 4:41 of a 6:10 suite on 2026-09-12 at 401
  records, and
  1:26 the afternoon before that at 344: the corpus grows when the bot's
  games last longer, because turn-9 positions are the most expensive there
  are to rank, and the record count moved 344 -> 401 -> 485 without anyone
  editing a test. (It reads 401 again on 2026-09-21.) Expect it to move
  again, and expect any CI number to be larger for the runner alone.
  This entry was wrong twice on 2026-09-12. It said three and a half minutes
  from before the tests that make up the difference existed, and was then
  "corrected" to eleven minutes from a run taken while a 128-seed gate held
  all eight cores -- contention recorded as fact, in the file that documents
  `sample_machine` and `contention_verdict` for exactly that reason. Time the
  suite on an idle machine or do not time it, and never quote a CI clock as
  the suite's speed.

  **The same applies to the profiler, and harder.** cProfile charges about a
  microsecond per call, so it systematically over-rewards any change that
  removes calls -- which is most optimisations. Two separate pieces of work
  found this on 2026-09-21: a change reading 18% fewer `country_value` calls
  was 0.8% of wall under the profiler and **2.1% without it**, and the enum
  descriptor hot spot's own-time column overstated it about threefold
  (docs/notes/claude/2026-09-21-enum-attribute-reads.md). **Profile to rank
  the work; time N whole games with no profiler attached to say what
  removing it was worth, and quote that number.** `test_parity_corpus.py` (a bot rebuilt per
  record) and `test_poke_rate.py` (four played games) are the largest
  single files; both earn it -- one is the exactness oracle, the other the
  only behavioural rate the suite measures -- but run a subset while
  iterating.
- **License**: MIT.
- **Language**: all code, comments, docstrings, and commit messages in
  English.
- **Layout**: `src/struggler/` package (src-layout, to avoid accidental
  implicit imports of the working directory during tests), split by
  concern:
  - `engine/` — the rules engine itself: state, board, cards, events,
    replay, and the `Player`/`HumanPlayer` contract that bots plug into.
  - `bots/` — the automated `Player` implementations, wired up by
    `src/main.py`'s `build_player`. `strategic/` is the main bot as a
    package of four: `evaluator.py` (the board-value terms as pure
    functions over an indexed snapshot, which a native port would receive
    as-is), `public_cards.py` (the deck's public schedule), `defcon.py`
    (the whole-hand survival search), and `policy.py` (everything
    stateful). Beside it: `greedy.py`/`naive.py` baselines, `mcts.py` and
    `rollout.py`, `opponent_model.py`, `llm/`, `train.py`, and
    `benchmark.py`, which is the gate.
  - `data/` — the game's JSON facts (`cards.json`, `countries.json`,
    `rules.json`).

  Tests live under `tests/`, golden replay logs under `tests/replays/`.
- **Logs**: run outputs go under `logs/` (gitignored) -- that is what it is
  there for -- not `/tmp`. Name them so the next session finds them:
  `logs/<topic>/...`, following the existing `ci-<runid>` entries. `/tmp`
  does not survive a reboot and hides work from whoever resumes.

## The rule

**If you make the same mistake twice, gate it with a test.** Not a note,
not a comment -- a test that fails when the mistake comes back. The
maintainer's rule, and the evidence for it is this file: every entry
below is a defect that recurred before anyone mechanised it, and the
ones that stopped recurring are the ones with a test next to them.

Recurrence is the signal. A mistake made once is bad luck; made twice it
is a property of the code or of how people read it, and neither is fixed
by remembering harder.

## Things that have bitten this codebase before

- **Check `tests/conftest.py` before writing a test helper.** A
  near-duplicate invariant checker copy-pasted across test files once let a
  real defect hide for weeks. See `docs/TESTING.md`.
- **Don't re-derive placement legality from the live board mid-Ops-spend.**
  Rule 6.1.1 freezes reachability at the start of the action round; see the
  reachability section of `docs/ARCHITECTURE.md`.
- **The full list, with the practice that stops each, is
  `docs/notes/claude/bug-shapes.md`.** Nine
  shapes; every one has recurred. Read it before adding a cache, a sentinel, a
  fallback, or a second copy of a rule.
- **Don't move the board mid-ranking without calling `_invalidate_base()`.**
  `delta` prices against per-decision caches keyed on the board as synced;
  moving it and then asking `delta` reads a base for a position that is not
  there. When the forward search did this the sign *inverted* -- breaks came
  back more attractive, and the minimum-poke rate stayed at 13 a game
  instead of falling to 0.25. Gated by `tests/test_base_cache_discipline.py`,
  which reconstructs the defect and requires the checker to catch it.
- **Don't decide "is this private?" from a key name.** `Decision.public()`
  hid option lists by testing `"card" in option.payload`, which is the
  privacy rule written down a second time. Blockade keys its card options
  `choice`, so the qualifying part of the US hand went into the shared
  history both players are handed -- the same leak already found and closed
  for headlines. Match the *values* against the card ids. Gated by
  `tests/test_history_privacy.py`, which checks the rules' question: every
  card the shared history names must already have been revealed in it.
- **Don't regroup a float expression while optimising it, and don't cache a
  sum when the caller accumulates it.** Made twice in one sitting on
  2026-09-21, both times while removing builtin calls from a hot loop.
  `coup_outcomes` nearly had `ops - 2 * stability + modifier` hoisted out of
  the six-roll loop -- `(1 + 3 - 4) + 0.1` is `0.1` and
  `1 + ((3 - 4) + 0.1)` is `0.09999999999999998`, with an `int()`
  truncation immediately downstream -- and `_delta`'s neighbour cache
  nearly stored `sum(after - then)` where the caller adds each difference
  into a running total. Neither is "close enough": rankings are decided by
  strict comparison, so one ulp is a changed move.
  `evaluator.py`'s header says this about multiplication; it is just as
  true of addition, and a profile is exactly the context that invites it.
  **The gate is `tests/test_parity_corpus.py`** -- run it before believing
  any optimisation, and cache the addends rather than the sum.
- **Don't memoise an evaluation term on less state than it reads.** This has
  shipped twice. `_access` reads influence two hops out and was keyed on one
  country, so a trial placement left it stale and the same position scored
  differently depending on what came first: 39 of 598 corpus rankings changed
  when the memo was bypassed. The terms now live in `bots/strategic/evaluator.py` and
  own no state; see the snapshot contract in `docs/STRATEGIC_AI.md`.

## Session environment (Codex CLI, 2026-09-15)

Learnings from running gates, suites, and recaptures in this container.
Standing prefs: docs always commit+push unasked; run logs under `logs/`
(gitignored); gates need explicit approval before dispatch.

- `exec_command`: `yield_time_ms` must be an integer, floats fail arg parse.
  Omit it for long runs, they background after ~10s wall with a session ID.
- Long commands: run as `cmd > logs/<topic>.log 2>&1; echo "exit=$?" >> log`,
  then poll with `sleep` + `tail`. Never `&`-background, it dies with the turn.
- No `apply_patch` tool in this harness. Edit via `python` + quoted heredocs,
  prefer line-number-targeted edits, verify with `grep` / `sed -n`. Watch
  heredoc backslash-escapes, a stray backtick escape has shipped a bug before.
- Kill duplicate runners (`ps aux | grep`) before timing anything. Suite and
  gate contend for all cores; the timing note in Conventions above was wrong
  twice from contended runs. Run gates alone locally, or prefer remote
  `gate.yml` dispatch, which is isolated so several can run at once.
- Fast A/B attribution: `git stash` + re-run the single failing test to decide
  "bundle or revert" before splitting branches.
- `gh` is authed (JamesYouL2). Gate dispatch:
  `gh workflow run gate.yml --ref <branch> -f bases='["<SHA>"]' -f vary=0`;
  poll with `gh run view <id> --json status,conclusion`.
  `decide` defaults to 1 (curtails ~15% once the verdict is stable); pass
  `-f decide=0` only for a full read when the precise score matters.
- `experiments.yml` runs weight A/Bs (one runner per arm, in parallel)
  rather than comparing revisions: dispatch
  `gh workflow run experiments.yml -f only=<slug>` (arms from
  `.github/experiments.json`) or `-f inline='{"slug":...,"weights":{...},
  "seeds":"...","held":"...",...}'` for a one-off without editing
  anything. Both `--decide` and `--held-seeds` come from the arm's own
  `held` field, which is required -- an arm without it silently never
  early-stops. Size arms full (a runner per arm removes the local
  one-at-a-time constraint; several 2026-09-12 runs were +/-0.075 and
  could not see a 6-point effect). The run's verdict is the summarise
  step's artifact, read it from the job summary, not the exit code.
- Ledger `models/provenance.json`: 2-space indent, never plain `json.dumps`
  (a test parses the format). Recompute `_summary` counts, verify with
  `tests/test_provenance.py`. New weights need entries or the suite fails.
- Suite ~4-6 min, `test_parity_corpus.py` is the pole. Recapture ~5-6 min for
  seeds 4000-4003. Ruff: compare against HEAD via `git stash`; only
  pre-existing (RUF005, B905, RUF059, PLW1510) should remain.

## Session environment, continued (opening swap, 2026-09-15)

- `yield_time_ms` takes an integer or nothing: `120000.0` fails arg parsing.
  When in doubt omit it; long commands background after ~10s with a session
  ID and `sleep 9` + `tail` polls them.
- Behaviour-change checklist for a default-opening swap: `DEFAULT_OPENINGS`
  in `policy.py`, the default test in `tests/test_openings.py`, the
  setup-and-handicap test in `tests/test_strategic.py` (it pins the exact
  placement order and board — grep for the new book name misses it; the
  suite is the backstop), and the opening bullet in `docs/STRATEGIC_AI.md`.
  First full run found the `test_strategic.py` pin; `-x` for fast discovery,
  then a full re-run.
- Recapture after any default change: the corpus follows the opening
  (431 records on iran, 474 on italy — longer games). Suite time follows
  the corpus: ~9:34 at 474 records, parity test the pole. A pass-count
  delta vs another branch is expected when the bases differ (861 here vs
  862 with the deck-tracking test).
- New experiments branch off `origin/main`, never pile onto a branch with
  a running gate — a moved HEAD confounds the verdict in flight.
- CI is free for verification, use it: `tests.yml` runs the full suite automatically on every push to `main`, and a full `decide=0` gate dispatches to isolated runners (`gh workflow run gate.yml --ref main -f bases='["<SHA>"]' -f decide=0 -f vary=0`). Route full-suite verification through CI whenever possible — a PR (or push to `main`) runs `tests.yml` with the parity oracle (`test_parity_corpus.py`) included. Prefer both over local runs and keep the local box free — local suite/gate contention is what corrupted the timing notes twice. Suites AND gates belong on GitHub; local runs are the exception, reserved for fast iterate-on-a-failure loops (2026-09-16, maintainer).
- The remote gate cannot measure an opening-default change: `gate.yml` has
  no openings input and `scripts/gate.sh` defaults both arms to
  `iran/austria` (`GATE_BOOKS`). Same for drift (`DRIFT_OPENINGS` in
  `scripts/drift_check.sh`). A remote gate on such a branch is safety-only;
  measuring the swap wants a local `GATE_OPENINGS=` empty run (each
  revision its own default) or `scripts/opening_tournament.py`.
- Never merge before the gate ACCEPTs, one verdict per branch, no bundling.
  Poll with `gh run view <id> --json status,conclusion`; workflow `success`
  is the ACCEPT, but confirm the ACCEPTED line in the log before merging.

## Session environment (pi, 2026-09-22)

What changes under the pi harness -- targeted `edit`/`write` tools instead
of heredoc edits (the backslash-escape hazard above is Codex-specific),
and skills under `.agents/skills/` mirrored to `.claude/skills/` -- is in
`docs/notes/pi/2026-09-22-the-pi-harness-and-what-to-ask-of-it.md`.

**This file is `CLAUDE.md` as well.** The two names are byte-identical on
purpose -- harnesses hardcode one name or the other -- and
`tests/test_agent_files.py` fails if they drift apart, the same way the
`.agents`/`.claude` skill mirrors are gated. Edit one, copy to the other.
