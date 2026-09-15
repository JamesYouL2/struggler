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
| [docs/notes/Codex/](docs/notes/Codex/) | Bot strategy work: one file per topic, indexed by its `README.md`, older entries under `archive/`. `bug-shapes.md` is the defect registry and has a stable path because a test parses it. (Codex's audit is `docs/notes/codex/`, the Rust plan `docs/RUST_PORT_PLAN.md`.) |
| [docs/EXPERT_STRATEGY.md](docs/EXPERT_STRATEGY.md) | Outside strategy references (Sankt, Ziemowit) before calibrating a weight to "what strong players do" -- including what those sources do *not* say |
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
- **Tests**: `uv run pytest`, plus `hypothesis` for property-based tests. Run
  the full suite before committing; it takes about six minutes (6:10 for
  777 tests on an idle machine, 2026-09-12 evening).
  `test_parity_corpus.py` is 4:41 of that -- three quarters of the suite --
  and it grew from 1:26 the same afternoon without anyone touching it: the
  corpus went from 344 records to 401 because the bot started reaching turn
  9, and turn-9 positions are the most expensive there are to rank. That
  cost is a function of how long the bot's games last, so it will move
  again. ALWAYS RUN THE WHOLE THING.
  This entry was wrong twice on 2026-09-12. It said three and a half minutes
  from before the tests that make up the difference existed, and was then
  "corrected" to eleven minutes from a run taken while a 128-seed gate held
  all eight cores -- contention recorded as fact, in the file that documents
  `sample_machine` and `contention_verdict` for exactly that reason. Time the
  suite on an idle machine or do not time it. `test_parity_corpus.py` (a bot rebuilt per
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
  `docs/notes/Codex/bug-shapes.md`.** Nine
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
  `gh workflow run gate.yml --ref <branch> -f bases='["<SHA>"]' -f decide=0 -f vary=0`;
  poll with `gh run view <id> --json status,conclusion`.
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
- The remote gate cannot measure an opening-default change: `gate.yml` has
  no openings input and `scripts/gate.sh` defaults both arms to
  `iran/austria` (`GATE_BOOKS`). Same for drift (`DRIFT_OPENINGS` in
  `scripts/drift_check.sh`). A remote gate on such a branch is safety-only;
  measuring the swap wants a local `GATE_OPENINGS=` empty run (each
  revision its own default) or `scripts/opening_tournament.py`.
- Never merge before the gate ACCEPTs, one verdict per branch, no bundling.
  Poll with `gh run view <id> --json status,conclusion`; workflow `success`
  is the ACCEPT, but confirm the ACCEPTED line in the log before merging.
