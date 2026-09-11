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
| [docs/CLAUDE_NOTES.md](docs/CLAUDE_NOTES.md) | Bot strategy work: the stated principles, their status, and what is open (Claude's notes; Codex's audit is `docs/CODEX_NOTES.md`, the Rust plan `docs/RUST_PORT_PLAN.md`) |
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
  the full suite before committing; it takes about three and a half minutes.
  Two files are most of that: `test_parity_corpus.py` rebuilds a bot per
  record and takes ~150s, and `test_poke_rate.py` plays four games and takes
  ~33s. Both earn it -- one is the exactness oracle, the other is the only
  behavioural rate the suite measures -- but run a subset while iterating.
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
  `docs/CLAUDE_NOTES.md` "The bugs this repo actually gets".** Eight
  shapes; six have recurred. Read it before adding a cache, a sentinel, a
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
