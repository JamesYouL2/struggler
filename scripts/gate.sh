#!/usr/bin/env bash
# What every value-function change has to clear before it lands:
#   1. the turn-1 event-value table and the expert-valuation diff (read by eye),
#   2. the turn-3 checkpoint against the previous commit (a diagnostic),
#   3. full games against the previous commit, on the tuning seeds and on a
#      held-out range that no change is selected against,
#   4. the acceptance rules, which decide.
# THE EXIT STATUS IS THE VERDICT. This script used to print numbers and exit 0
# whatever they said, so "the gate passed" only ever meant "the gate ran"; step
# 4 is what makes it mean something. The rules live in
# `benchmark.acceptance`: no more nuclear losses than chance explains, two
# samples over disjoint seeds and 150+ games, and a pooled score whose
# one-sided 95% upper bound reaches 0.500. Only measurable regressions are
# blocked, because at these sample sizes most real changes are not measurable
# in either direction.
# Read the verdict, and mind the exit status: piping this script into `tail`
# hands you tail's status, not the gate's.
# TIME BUDGET (the maintainer's): stay under an hour; ten minutes preferred.
# Last measured 46m09s, and that was with other jobs on the same eight cores
# -- so run a gate alone. The floor is not the seed count: acceptance needs
# 150 finished games, which at a 76.5s median game over 8 workers is 24
# minutes before anything else runs. Ten minutes needs a ~2.5x faster game,
# not fewer seeds. See docs/notes/claude/ "The gate's time budget".
# Usage: scripts/gate.sh [base-ref=HEAD~1] [seeds=4000-4031] [workers=8] [held-out=5000-5063]
# Drift against an old anchor is scripts/drift_check.sh, not this script.
# Results go to logs/game-check/gate-<head>/ and a one-line summary is printed.
# The candidate is a snapshot: HEAD is checked out into a temporary
# worktree and every benchmark runs from there, so editing the working
# tree while a gate runs cannot change what it measures (it did, once:
# a gate blamed a nuclear loss on a commit that never produced one).
# THE DRIFT CANARY MOVED OUT, 2026-09-11. It ran here as step 3c, against the
# oldest tag still believed sound, because one baseline cannot see drift: a run
# of individually-neutral changes can walk the bot downward with every single
# gate accepting. That reasoning still holds; running it *here* did not.
#
# It never decided anything -- acceptance runs against HEAD~1 and never saw it
# -- so it spent 32 of every 192 games on a reading with no authority, and it
# cost the verdict 16 seeds (96 -> 80). That left the pool so close to
# `ACCEPTANCE['min_games']` that early stopping could shave at most 5 seeds:
# the gate on 2026-09-11 stopped at 153 of 160.
#
# It is now `scripts/drift_check.sh`, scheduled by `scripts/drift_cron.sh`,
# where it can afford a sample big enough to mean something -- at 16 seeds it
# once read 0.469 against v0.1.0 where the full 77-seed run gave 0.578. Drift
# accumulates over many commits, so once a day is the right rate for it.
#
# The seeds are given back: HELD returns to 5000-5063, so the verdict is 96
# seeds and +/-0.032 again, and early stopping has 42 games of headroom.
# Step 3 runs both samples in one pool and stops once the seeds still
# unplayed cannot change the verdict (about 15% of the games, and no
# historical verdict changes); GATE_DECIDE=0 plays every game.
set -euo pipefail
cd "$(dirname "$0")/.."
# --check runs everything up to the first game and exits: the setup, the
# helpers, the snapshots and the worktree. It exists because this script
# is only ever exercised by a 50-minute run, so a mistake in the preamble
# is found 50 minutes late -- or, once, instantly and after the wait:
# `MACHINE_AT_START=$(machine)` was placed above `machine()`'s definition,
# which `bash -n` accepts because it is a runtime error, not a syntax one.
# Gated by tests/test_gate_script.py.
CHECK=0
if [ "${1:-}" = "--check" ]; then CHECK=1; shift; fi
BASE=${1:-HEAD~1}
SEEDS=${2:-4000-4031}
WORKERS=${3:-8}
HELD=${4:-5000-5063}
ROOT=$(pwd)
# snapshot(), machine(), sample_machine() and contention_verdict() are shared
# with scripts/drift_check.sh. They were copied there when the drift canary
# moved out, which is shape 4 in docs/notes/claude/bug-shapes.md -- two
# implementations of one rule, four recurrences -- so there is one copy, here.
. "$ROOT/scripts/lib/gate_common.sh"
# Overlapping other work with a gate is allowed: the seeds are deterministic,
# so contention moves the clock and never the verdict. It does make the wall
# time uninterpretable unless it is written down, so it is. `load` is the
# 1-minute average; `busy` counts python processes that are not this gate's.
#
# CONTENTION, recorded rather than assumed. Every timing this script prints --
# `took`, and `mean_game_seconds` in each report -- is quotable only if the
# gate had the cores to itself. "Run it alone" is a discipline nobody can
# enforce and everybody forgets, and a timing taken under uncontrolled
# conditions is shape 7 in docs/notes/claude/bug-shapes.md, three recurrences.
# So `sample_machine` runs at every step boundary, the worst reading survives,
# and the end says plainly whether the numbers can be used. Sampling only at
# the start and end is not enough: it misses a spike that begins and ends
# inside a 25-minute step.

PY=${PYTHON:-$ROOT/.venv/bin/python}
MACHINE_AT_START=$(machine)
HEAD_SHA=$(git rev-parse --short HEAD)
OUT=$ROOT/logs/game-check/gate-${HEAD_SHA}
# --check gets its own directory. Sharing the real one is not a tidiness
# issue: `snapshot` begins with `rm -rf`, so a dry run at the same HEAD
# deletes a *running* gate's baseline. That happened -- the suite runs
# `gate.sh --check` through tests/test_gate_script.py, and doing so during
# a gate killed it at step 3 with a missing snapshot, forty minutes in.
[ "$CHECK" = "1" ] && OUT=$(mktemp -d)
mkdir -p "$OUT"

# ONE GATE AT A TIME, enforced rather than asked for.
#
# Two gates at the same HEAD share this directory, and `snapshot` begins with
# `rm -rf` -- so the second deletes the first's baseline mid-run and the first
# dies at its next step with FileNotFoundError. That is not hypothetical: it
# killed the v0.2.1 gate forty minutes in. The fix then was to give `--check`
# its own directory, which was too narrow; two *real* gates still collide, and
# they also clobber each other's report files, so acceptance can read a
# verdict computed from the other run's games.
#
# At different HEADs the directories differ, but both ask for `--workers 8` on
# eight cores, so each runs at roughly half speed and every timing either
# prints is meaningless. The lock is global for that reason: the constraint is
# one gate per machine, not one per revision.
#
# `--check` does not take it. It writes to a mktemp directory, costs seconds,
# and the test suite runs it -- blocking there would make the suite fail
# whenever a gate happens to be running.
if [ "$CHECK" != "1" ]; then
  exec 8>"$ROOT/logs/game-check/.lock"
  if [ "${GATE_WAIT:-0}" = "1" ]; then
    flock 8
  elif ! flock -n 8; then
    echo "GATE REFUSED: another gate holds $ROOT/logs/game-check/.lock." >&2
    echo "  Two gates at once delete each other's baseline and halve each" >&2
    echo "  other's speed. Wait, or re-run with GATE_WAIT=1 to queue behind it." >&2
    "$PY" "$ROOT/scripts/gate_running.py" 2>/dev/null | grep -v "^not running$" >&2 || true
    exit 5
  fi
fi
GATE_STARTED=$(date +%s)
elapsed() { printf '%dm%02ds' $(( ($(date +%s) - GATE_STARTED) / 60 )) $(( ($(date +%s) - GATE_STARTED) % 60 )); }
# The maintainer has a time budget for this script, so it reports against it
# instead of leaving the number to be recovered from file mtimes afterwards
# (which is how the 46m09s in the notes was found).
# Each baseline gets its own directory holding that revision's whole
# `struggler/bots` package: benchmark.load_module resolves every
# `struggler.bots.*` import to it while `strategic.py` loads, so the baseline
# runs on its own code. Snapshotting `strategic.py` alone compared a
# `public_cards.py` change against itself and reported a dead heat.
# A rules change to the engine is not a strength change, and this script
# cannot see it. Only `src/struggler/bots` is snapshotted -- the engine is
# deliberately shared, as the arbiter both sides are measured under -- so a
# change that touches no bot file puts byte-identical players on both sides
# of every game and returns exactly 0.500. That is the same misreading that
# once let a broken snapshot report a dead heat as a pass, except here it is
# inherent: both sides play under the same rules, so a rules fix is symmetric
# by construction and the games can only say it did not crash. Such a change
# is validated by its tests, not by this script.
if [ -z "$(git diff --name-only "$BASE"..HEAD -- src/struggler/bots)" ]; then
  echo "NOTE: $BASE..HEAD touches no file under src/struggler/bots, which is all"
  echo "      this gate snapshots. Both sides will play identical bots, so step 4"
  echo "      can only report a dead heat. Read this run as a crash-and-nuclear-loss"
  echo "      smoke test; the rules tests are what validate an engine change."
fi
snapshot "$BASE" "$OUT/base"
SNAP=$(mktemp -d)
git worktree add -q --detach "$SNAP" HEAD
trap 'git worktree remove --force "$SNAP"' EXIT
cd "$SNAP"
export PYTHONPATH=src
if [ "$CHECK" = "1" ]; then
  echo "--check: setup, helpers, snapshots and worktree all fine."
  echo "  machine: $MACHINE_AT_START"
  sample_machine
  echo "  contention: $(contention_verdict "$WORKERS")"
  echo "  base $BASE -> $OUT/base"
  echo "  elapsed $(elapsed)"
  exit 0
fi
sample_machine
echo "== 1. turn-1 table (seed ${SEEDS%%-*})"
$PY -m struggler.bots.benchmark --table --seeds "$SEEDS" | tee "$OUT/table.txt"
# A benchmark step that dies used to surface as a JSONDecodeError from this
# summariser, with the actual traceback already discarded to /dev/null -- so
# "the gate crashed" was indistinguishable from "the gate disagreed", and the
# reason was gone. Every step now keeps its stderr in $OUT and `summ` names
# the file when it is handed no JSON. A crash is a verdict: the run is not a
# dead heat, it is unmeasured, and it exits non-zero saying so.
summ() {  # summ <step-name>
  local step=$1 out
  out=$(cat)
  if [ -z "$out" ]; then
    echo "GATE FAILED: step $step produced no result -- it crashed or was killed."
    # Attribute it. Frames under $OUT/base and none in the candidate worktree
    # mean the *baseline* died on its own code, which is a different verdict:
    # a fix for a crash cannot be mirror-gated against the revision that
    # crashes, because the gate needs both sides to finish their games.
    if grep -q "$OUT/base/" "$OUT/$step.err" 2>/dev/null &&
       ! grep -q "$SNAP/src/struggler/bots/" "$OUT/$step.err" 2>/dev/null; then
      echo "  THE BASELINE CRASHED, NOT THE CANDIDATE -- every frame is under $OUT/base."
      echo "  A crash fix cannot be measured against the revision it fixes. Gate it"
      echo "  against a baseline that finishes, or accept it on the crash evidence."
    fi
    echo "  stderr: $OUT/$step.err"
    tail -n 20 "$OUT/$step.err" 2>/dev/null | sed 's/^/  | /'
    exit 3
  fi
  printf '%s\n' "$out" | $PY -c "
import sys, json
d = json.loads(sys.stdin.read())
bits = []
if 'score' in d:
    ci = f\" +/-{d['score_halfwidth']}\" if 'score_halfwidth' in d else ''
    bits.append(f\"score {d['score']}{ci} over {d.get('seeds', '?')} seeds\")
for k in ('mean_signed_vp', 'mean_total', 'nuclear_losses'):
    if k in d:
        bits.append(f'{k} {d[k]}')
print('  ' + ', '.join(bits))"
}
sample_machine
echo "== 1b. expert valuations (US Ops)"
$PY -m struggler.bots.benchmark --expert models/expert_valuations.json --seeds "$SEEDS" | tee "$OUT/expert.txt" | grep -E 'misses|BROKEN|PLACEMENT'
sample_machine
echo "== 1c. types and lint (advisory)"
# Advisory on purpose: the hard gate is tests/test_types.py, five rules at
# zero findings. This is the rest -- about 95 ty diagnostics of annotation
# debt and 109 ruff findings -- reported so the backlog stays visible
# without blocking a change on it.
"$ROOT/.venv/bin/ty" check --output-format concise 2>&1 | tail -1 | sed 's/^/  ty: /' || true
"$ROOT/.venv/bin/ruff" check --statistics src tests scripts 2>&1 | tail -3 | sed 's/^/  ruff: /' || true
sample_machine
echo "== 2. turn-3 checkpoint vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic/policy.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>"$OUT/t3.err" | summ t3
sample_machine
echo "== 3. full games vs $BASE, tuning seeds $SEEDS and held-out $HELD"
# One pool over both samples, not two runs. Two pools drained in sequence pay
# the slowest game's tail twice, and --decide can only stop a run that has
# played some of each sample. GATE_DECIDE=0 plays every game regardless.
DECIDE=$([ "${GATE_DECIDE:-1}" = "1" ] && echo --decide || echo)
# --vary-openings: each seed gets one of the nine opening-book pairs, the
# same pair for both arms, so it cancels from the difference exactly as the
# deal does. Measured at 32 seeds to cost no precision (se 0.0524 varied
# against 0.0591 fixed). Scores from before this landed are not directly
# comparable with scores after, though the verdict logic is unchanged.
#
# GATE_VARY=0 turns it off, and there are two reasons to:
#   1. A baseline older than the opening books cannot be given one, and
#      `build` refuses rather than silently starting the arms from
#      different boards. Baselines before v0.2.0 need GATE_VARY=0.
#   2. **A change to the *default* opening is invisible with this on**,
#      because varying overrides both arms' defaults. Measuring one means
#      turning this off, so that each side plays the book it ships with.
VARY=$([ "${GATE_VARY:-1}" = "1" ] && echo --vary-openings || echo)
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic/policy.py" \
   --seeds "$SEEDS" --held-seeds "$HELD" --workers "$WORKERS" $DECIDE $VARY \
   --report "$OUT/full-vs-base.json" --held-report "$OUT/full-vs-held.json" 2>"$OUT/full.err" | summ full
sample_machine
echo "== 3b. cards, by what the bot chose to do with them (advisory)"
# Revealed preference: which cards each side pays to *event* rather than
# spend for Ops. Scoring cards are excluded -- they have no Ops and must be
# played, so they measure the rules. Intervals are Wilson and are a floor
# on the width, since plays inside one game are not independent.
$PY - "$OUT/full-vs-base.json" <<'PYEND' || true
import json, sys
d = json.load(open(sys.argv[1]))
s = d.get('summary', {})
if not s.get('evented_top5'):
    print('  (no card data in this report)'); raise SystemExit
print(f"  plays by mode: {s.get('plays_by_mode')}"
      f"  (+{s.get('forced_scoring_plays', 0)} forced scoring plays, excluded)")
for side in ('US', 'USSR'):
    rows = s['evented_top5'].get(side, [])
    print(f'  {side} evented most:')
    for card, ev, total, lo, hi in rows:
        print(f'    {ev:3}/{total:<3} {ev/total:4.0%}  [{lo:.2f},{hi:.2f}]  {card}')
    never = s.get('never_for_ops', {}).get(side, [])
    if never:
        print(f'    never for Ops (3+ plays): '
              + ', '.join(f'{c} x{n}' for c, n in never))
PYEND
echo "== 4. acceptance"
STATUS=0
$PY -m struggler.bots.benchmark --accept "$OUT/full-vs-base.json" "$OUT/full-vs-held.json" || STATUS=$?
TOOK=$(elapsed)
SECONDS_TAKEN=$(( $(date +%s) - GATE_STARTED ))
echo "took $TOOK (budget: under 60m; $( [ "$SECONDS_TAKEN" -lt 3600 ] && echo ok || echo OVER ))"
sample_machine
echo "  machine at start: $MACHINE_AT_START"
echo "  machine at end:   $(machine)"
echo "  contention:       $(contention_verdict "$WORKERS")"
if [ "$SECONDS_TAKEN" -ge 3600 ]; then
  # Not a failure -- the verdict is about the bot, not the clock -- but the
  # maintainer wants to know, and a gate that drifts past an hour stops
  # being run.
  echo "  WARN over the hour. Was anything else using the cores? See" \
       "docs/notes/claude/ 'The gate's time budget': the floor is ~24m at" \
       "150 games and a 76.5s median, so a big overrun is usually contention." >&2
fi
echo "results in $OUT"
exit $STATUS
