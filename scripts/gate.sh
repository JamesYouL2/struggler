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
# not fewer seeds. See docs/CLAUDE_NOTES.md "The gate's time budget".
# Usage: scripts/gate.sh [base-ref=HEAD~1] [pre-session-ref] [seeds=4000-4031] [workers=8] [held-out=5000-5063]
# Results go to logs/game-check/gate-<head>/ and a one-line summary is printed.
# The candidate is a snapshot: HEAD is checked out into a temporary
# worktree and every benchmark runs from there, so editing the working
# tree while a gate runs cannot change what it measures (it did, once:
# a gate blamed a nuclear loss on a commit that never produced one).
# The anchor run (3c) is off by default; GATE_ANCHOR=1 turns it on.
# Step 3 runs both samples in one pool and stops once the seeds still
# unplayed cannot change the verdict (about 15% of the games, and no
# historical verdict changes); GATE_DECIDE=0 plays every game.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${1:-HEAD~1}
OLD=${2:-b2e8572}
SEEDS=${3:-4000-4031}
WORKERS=${4:-8}
HELD=${5:-5000-5063}
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
HEAD_SHA=$(git rev-parse --short HEAD)
OUT=$ROOT/logs/game-check/gate-${HEAD_SHA}
mkdir -p "$OUT"
# The maintainer has a time budget for this script, so it reports against it
# instead of leaving the number to be recovered from file mtimes afterwards
# (which is how the 46m09s in the notes was found).
GATE_STARTED=$(date +%s)
elapsed() { printf '%dm%02ds' $(( ($(date +%s) - GATE_STARTED) / 60 )) $(( ($(date +%s) - GATE_STARTED) % 60 )); }
# Each baseline gets its own directory holding that revision's whole
# `struggler/bots` package: benchmark.load_module resolves every
# `struggler.bots.*` import to it while `strategic.py` loads, so the baseline
# runs on its own code. Snapshotting `strategic.py` alone compared a
# `public_cards.py` change against itself and reported a dead heat.
snapshot() {  # snapshot <ref> <dir>
  # Wipe first. `tar -x` overlays, it does not replace, so re-running a gate
  # at the same HEAD against a different base used to leave both revisions'
  # files side by side -- and the layout has changed shape at least once
  # (`strategic.py` became the `strategic/` package), so the leftovers are
  # not always shadowed by the new ones. That is a baseline made of two
  # revisions, which is the contamination this snapshot exists to prevent.
  rm -rf "$2"
  mkdir -p "$2"
  git archive "$1" src/struggler/bots | tar -x -C "$2" --strip-components=3
  if [ ! -e "$2/strategic/policy.py" ]; then
    # Pre-split: the bot was `strategic.py`, not `strategic/policy.py`, so
    # `--opponent strategic@.../strategic/policy.py` cannot resolve. Fatal for
    # the base, which decides the verdict; only disabling for the optional
    # anchor, whose default ref is older than the split.
    if [ "${3:-required}" = required ]; then
      echo "GATE FAILED: base $1 has no strategic/policy.py -- it predates the package split, so it cannot be a baseline for this HEAD."
      exit 4
    fi
    echo "note: anchor ref $1 predates the package split; step 3c disabled."
    ANCHOR_OK=0
  fi
}
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
ANCHOR_OK=1
snapshot "$OLD" "$OUT/old" optional
SNAP=$(mktemp -d)
git worktree add -q --detach "$SNAP" HEAD
trap 'git worktree remove --force "$SNAP"' EXIT
cd "$SNAP"
export PYTHONPATH=src
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
  printf '%s\n' "$out" | $PY -c "import sys,json; d=json.loads(sys.stdin.read()); print({k:d[k] for k in ('score','mean_signed_vp','mean_total','nuclear_losses') if k in d})"
}
echo "== 1b. expert valuations (US Ops)"
$PY -m struggler.bots.benchmark --expert models/expert_valuations.json --seeds "$SEEDS" | tee "$OUT/expert.txt" | grep -E 'misses|BROKEN|PLACEMENT'
echo "== 2. turn-3 checkpoint vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic/policy.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>"$OUT/t3.err" | summ t3
echo "== 3. full games vs $BASE, tuning seeds $SEEDS and held-out $HELD"
# One pool over both samples, not two runs. Two pools drained in sequence pay
# the slowest game's tail twice, and --decide can only stop a run that has
# played some of each sample. GATE_DECIDE=0 plays every game regardless.
DECIDE=$([ "${GATE_DECIDE:-1}" = "1" ] && echo --decide || echo)
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic/policy.py" \
   --seeds "$SEEDS" --held-seeds "$HELD" --workers "$WORKERS" $DECIDE \
   --report "$OUT/full-vs-base.json" --held-report "$OUT/full-vs-held.json" 2>"$OUT/full.err" | summ full
if [ "${GATE_ANCHOR:-0}" = "1" ] && [ "$ANCHOR_OK" = "1" ]; then
  echo "== 3c. full games vs pre-session $OLD"
  $PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/old/strategic/policy.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-old.json" 2>"$OUT/anchor.err" | summ anchor
fi
echo "== 4. acceptance"
STATUS=0
$PY -m struggler.bots.benchmark --accept "$OUT/full-vs-base.json" "$OUT/full-vs-held.json" || STATUS=$?
TOOK=$(elapsed)
SECONDS_TAKEN=$(( $(date +%s) - GATE_STARTED ))
echo "took $TOOK (budget: under 60m; $( [ "$SECONDS_TAKEN" -lt 3600 ] && echo ok || echo OVER ))"
if [ "$SECONDS_TAKEN" -ge 3600 ]; then
  # Not a failure -- the verdict is about the bot, not the clock -- but the
  # maintainer wants to know, and a gate that drifts past an hour stops
  # being run.
  echo "  WARN over the hour. Was anything else using the cores? See" \
       "docs/CLAUDE_NOTES.md 'The gate's time budget': the floor is ~24m at" \
       "150 games and a 76.5s median, so a big overrun is usually contention." >&2
fi
echo "results in $OUT"
exit $STATUS
