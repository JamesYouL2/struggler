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
| [docs/STRATEGIC_AI.md](docs/STRATEGIC_AI.md) | `bots/strategic.py`, `bots/evaluator.py`, the value function and its snapshot contract |
| [docs/TESTING.md](docs/TESTING.md) | Adding or changing any test |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Before "fixing" something that may be a documented simplification |
| [docs/RULES_SOURCES.md](docs/RULES_SOURCES.md) | Any rules question: the card face, the rulebook, the FAQ, and the rulings this engine rests on |
| [docs/CLAUDE_NOTES.md](docs/CLAUDE_NOTES.md) | Bot strategy work: the stated principles, their status, and what is open (Claude's notes; Codex's audit is `docs/CODEX_NOTES.md`, the Rust plan `docs/RUST_PORT_PLAN.md`) |

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
  the full suite before committing; it takes about 80 seconds.
- **License**: MIT.
- **Language**: all code, comments, docstrings, and commit messages in
  English.
- **Layout**: `src/struggler/` package (src-layout, to avoid accidental
  implicit imports of the working directory during tests), split by
  concern:
  - `engine/` — the rules engine itself: state, board, cards, events,
    replay, and the `Player`/`HumanPlayer` contract that bots plug into.
  - `bots/` — the automated `Player` implementations, wired up by
    `src/main.py`'s `build_player`, plus `evaluator.py`: the board-value
    terms as pure functions over an indexed snapshot, which the strategic
    policy calls and a native port would receive as-is.
  - `data/` — the game's JSON facts (`cards.json`, `countries.json`,
    `rules.json`).

  Tests live under `tests/`, golden replay logs under `tests/replays/`.

## Two things that have bitten this codebase before

- **Check `tests/conftest.py` before writing a test helper.** A
  near-duplicate invariant checker copy-pasted across test files once let a
  real defect hide for weeks. See `docs/TESTING.md`.
- **Don't re-derive placement legality from the live board mid-Ops-spend.**
  Rule 6.1.1 freezes reachability at the start of the action round; see the
  reachability section of `docs/ARCHITECTURE.md`.
- **Don't memoise an evaluation term on less state than it reads.** This has
  shipped twice. `_access` reads influence two hops out and was keyed on one
  country, so a trial placement left it stale and the same position scored
  differently depending on what came first: 39 of 598 corpus rankings changed
  when the memo was bypassed. The terms now live in `bots/evaluator.py` and
  own no state; see the snapshot contract in `docs/STRATEGIC_AI.md`.
