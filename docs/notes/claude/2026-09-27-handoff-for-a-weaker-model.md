# Handoff: cleanup and routine experiments for a weaker model

This is written for an agent that is careful but not expected to make
strategy or design judgements (maintainer, 2026-09-27: "what I should
dump off to a weaker model"). Every task below has an exact procedure and
a check that tells you whether you got it right. **If a task needs a
judgement this note does not give you, stop and ask; do not guess.** The
tasks at the end are listed so you know NOT to take them.

## Read first, every time

- `CLAUDE.md`, the whole of it. It is binding.
- `docs/notes/claude/bug-shapes.md`: the nine mistakes this repo keeps
  making.

## Rules that apply to every task

1. **Run everything through `uv run`.** Bare `python3` has no
   dependencies.
2. **A behaviour-preserving change must pass `tests/test_parity_corpus.py`
   WITHOUT recapturing the corpus.** That is the proof that play did not
   change. If it fails, your change changed play: undo it and report. Never
   "fix" the corpus by recapturing (`scripts/capture_corpus.py`) unless the
   task says play is meant to change.
3. **Run the whole suite before you push:** `uv run pytest -q`, about 4
   minutes. It must be green. The pre-push hook runs a subset; that is not
   enough.
4. **Lint:** `uvx ruff check --select F src tests scripts` must show no
   finding that `origin/main` does not.
5. **One task per branch, branched from `origin/main`.** Commit messages
   end with the attribution line the harness gives you. Push the branch
   and open a PR. Never merge; the maintainer merges.
6. **JSON registries have exact formats:**
   - `models/provenance.json` and `models/experiment_ledger.json`
     round-trip exactly with `json.dumps(obj, indent=2, ensure_ascii=False)
     + '\n'`.
   - `.github/experiments.json` does NOT; its indentation is inconsistent.
     Edit it textually (find an arm's object by brace-matching from its
     `"slug"`), then check with `json.loads` that nothing else changed.
   - When you remove a `StrategicWeights` field, three things follow in
     the same commit (the tests enforce them):
     - its provenance entry goes, and `_summary.counts_by_source` /
       `counts_by_determination` are recomputed from the entries;
     - any arm under `experiments` that names it moves to `_retired.arms`;
     - its key is stripped from every record's `weights` in
       `tests/corpus/positions.json.gz`, after asserting it equals the
       default in every record. Write back with gzip and `json.dump(D, f)`,
       default separators.
7. **Notes:** any new note under `docs/notes/claude/` must be indexed with
   `uv run python scripts/index_note.py <path>`, or `tests/test_agent_files.py`
   fails. Never edit an old dated note's findings. Add a dated section, or
   a new note.
8. **Timings:** never quote a CI runner's wall clock as a speed. Local
   timings only on an idle machine (`uv run python scripts/gate_running.py`
   must say "not running"), one measurement at a time.

## Cleanup tasks (behaviour-preserving)

### C1. Dead code in the bot package

Candidates from a `vulture` scan (2026-09-27, confidence 60%). Each needs
**checking by grep before deleting**: grep `src/`, `tests/` and `scripts/`
for the name, and ignore comments and docstrings. Delete only what has no
caller outside tests.

| candidate | where | what the scan and a grep found |
| --- | --- | --- |
| `retention_p`, `RETENTION_P` | `bots/strategic/evaluator.py` | called only by tests (`test_strategic.py`, `test_public_cards.py`); the measurement it held is in its comment and the notes. If deleted, its tests go too and its provenance entry is removed. |
| `Terrain.neighbor_set` | `evaluator.py` | built, never read: the `access_chain` loop that read it was deleted |
| `Terrain.coup_min_defcon` | `evaluator.py` | built, never read in `bots/` (the engine and `greedy.py` read RULES directly) |
| `Position._rehash` | `evaluator.py` | mentioned only in docstrings |
| `StrategicPlayer._access`, `scoring_weight` | `policy.py` | check the callers; `scoring_weight` may be public API used by scripts |
| the `threshold` parameter | `benchmark.py`, near line 640 | unused argument; check the callers pass it |

Other names the scan listed (the `_vp_price`, `_placement_values`,
`_relocation_gain` and `_coup_bans` attributes, the LLM classes,
`find_spec`) are false positives: read by `__dict__.get`, by reflection,
or from other modules. Leave them.

Check: the parity corpus passes unrecaptured; the whole suite is green;
no new lint.

### C2. Stale one-off scripts

`scripts/` has about 50 files. Several are one-night queue scripts
(`overnight2.sh`, `morning.sh`, `space_check.sh`, `queue_*.sh`) that name
weights deleted since (`space_ability_2/4/6/8`, `scoring_discount`,
`access_chain`, and others). They would fail if run.

1. For each shell script under `scripts/`, grep it for weight names that
   `StrategicWeights` (`src/struggler/bots/strategic/policy.py`) no longer
   has.
2. Check whether any test, workflow or doc references the script:
   `grep -rn <script name> tests .github docs`, and ignore `docs/notes/`,
   which are history.
3. A stale script nothing references moves to `scripts/archive/`, with a
   one-line `scripts/archive/README.md` entry saying why. `git mv`, do not
   delete. Referenced ones stay, and you report them.

Check: `tests/test_tooling_paths.py` and the whole suite are green.

### C3. The provenance `_reading` paragraph

`models/provenance.json` `_summary._reading` has grown by prepended
"Recounted ..." sentences. Rewrite it as one current paragraph: the
current counts (computed from the entries, not copied), the known-wrong
entries, and one line on where the history is (git log). Check that
`tests/test_provenance.py` is green.

## Routine experiments (CI only)

Experiments run on GitHub (`.github/workflows/experiments.yml`), never on
this machine. The procedure, every time:

1. **Consult `models/experiment_ledger.json` first.** If the question has
   an answered entry, do not re-run it. Say so.
2. **Write the rule into a note BEFORE dispatching:** what each outcome
   means. Copy the shape of the latest rule in
   `docs/notes/claude/2026-09-26-events-still-to-come.md`: nomination (lower
   bound above 0), the veto (bot DEFCON-1 losses above 1.5x the base's),
   covers 0, costs.
3. **Add each arm** to `.github/experiments.json` `experiments`:
   - `slug`, `seeds` (a FRESH block that overlaps no existing text:
     `scripts/shard_plan.py`'s `assert_disjoint` checks this), `reserve`
     (two spare shards' worth), `anchor: "v0.6.0"`, and `compare_to` the
     base arm;
   - plus a ledger entry with `status: "planned"` and the note in `notes`.
4. **Dispatch** with `gh workflow run experiments.yml --ref <branch> -f
   only=<base>,<arm>,... -f waves=false`. Within a minute, check that the
   run exists and its `plan` job succeeded.
5. **Reading:**
   - `gh run download <id> -D logs/ci-<id> -n pooled`, and read
     `pooled.json` (`arms`, `paired`).
   - State every number with its interval, then which branch of the rule
     it is.
   - Fill in the ledger entry (`run`, `reading`, `verdict`, `status:
     "answered"`), move the arms to `_retired.arms`, and add the reading
     section to the note.
   - **Do not change a default weight because of a reading.** A nomination
     goes to the maintainer.

Experiments that fit this procedure and are waiting:

- **E1. MCTS guarded at 192 simulations.**
  - Settings: the `mcts-h1-guarded` settings with `"simulations": 192`
    (in the arm's `search` object), on the SAME seeds as the guarded run
    (151000-151255, reserve 151300-151363, `"shard": 32`), no anchor.
  - What it asks: whether deeper search makes the guarded overrides
    worth something.
  - Its rule: the guarded run's rule, with the override rate reported.
  - Note: `docs/notes/claude/2026-09-27-mcts-horizons-timed.md`.
- **E2. A second annotated-position pack for the maintainer.** Run
  `uv run python scripts/position_pack.py --decisions 5 --boards 0 --out
  logs/positions/pack2.md`, pick five positions not already in
  `tests/fixtures/positions/annotated-01.json`, and put them in front of
  the maintainer as the first pack was. Do not answer them yourself.

## Do NOT take these (they need judgement)

- Anything that changes a default weight or ships a feature. The event
  discount stack (#68/#72/#75) is waiting on the maintainer's
  ship-or-close decision.
- New value-function terms: flag prices, Debt Crisis pay, a hold price,
  and the China Card's held value.
- Performance work on the event sandbox or the DEFCON planner. Exact
  optimisations there have shipped bugs that only the parity corpus
  caught, and choosing what to cache is bug shape 1's territory.
- The Rust port itself, and deciding its scope.
- Recapturing the parity corpus for any reason other than a task that says
  play changes.
