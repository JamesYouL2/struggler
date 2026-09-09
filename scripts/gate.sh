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
# `benchmark.acceptance`: no nuclear losses, two samples over disjoint seeds
# and 150+ games, and a pooled score whose one-sided 95% upper bound reaches
# 0.500. Only measurable regressions are blocked, because at these sample
# sizes most real changes are not measurable in either direction.
# Usage: scripts/gate.sh [base-ref=HEAD~1] [pre-session-ref] [seeds=4000-4031] [workers=8] [held-out=5000-5063]
# Results go to logs/game-check/gate-<head>/ and a one-line summary is printed.
# The candidate is a snapshot: HEAD is checked out into a temporary
# worktree and every benchmark runs from there, so editing the working
# tree while a gate runs cannot change what it measures (it did, once:
# a gate blamed a nuclear loss on a commit that never produced one).
# The anchor run (3b) is off by default; GATE_ANCHOR=1 turns it on.
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
# Each baseline gets its own directory: benchmark.load_module binds a sibling
# `evaluator.py` in place of the candidate's while it loads `strategic.py`, so
# a baseline that predates the evaluator split still runs its own terms.
snapshot() {  # snapshot <ref> <dir>
  mkdir -p "$2"
  git show "$1:src/struggler/bots/strategic.py" > "$2/strategic.py"
  git show "$1:src/struggler/bots/evaluator.py" > "$2/evaluator.py" 2>/dev/null \
    || rm -f "$2/evaluator.py"
}
snapshot "$BASE" "$OUT/base"
snapshot "$OLD" "$OUT/old"
SNAP=$(mktemp -d)
git worktree add -q --detach "$SNAP" HEAD
trap 'git worktree remove --force "$SNAP"' EXIT
cd "$SNAP"
export PYTHONPATH=src
echo "== 1. turn-1 table (seed ${SEEDS%%-*})"
$PY -m struggler.bots.benchmark --table --seeds "$SEEDS" | tee "$OUT/table.txt"
summ() { $PY -c "import sys,json; d=json.loads(sys.stdin.read()); print({k:d[k] for k in ('score','mean_signed_vp','mean_total','nuclear_losses') if k in d})"; }
echo "== 1b. expert valuations (US Ops)"
$PY -m struggler.bots.benchmark --expert models/expert_valuations.json --seeds "$SEEDS" | tee "$OUT/expert.txt" | grep -E 'misses|BROKEN|PLACEMENT'
echo "== 2. turn-3 checkpoint vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>/dev/null | summ
echo "== 3a. full games vs $BASE, tuning seeds $SEEDS"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-base.json" 2>/dev/null | summ
echo "== 3b. full games vs $BASE, held-out seeds $HELD"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic.py" --seeds "$HELD" --workers "$WORKERS" --report "$OUT/full-vs-held.json" 2>/dev/null | summ
if [ "${GATE_ANCHOR:-0}" = "1" ]; then
  echo "== 3c. full games vs pre-session $OLD"
  $PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/old/strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-old.json" 2>/dev/null | summ
fi
echo "== 4. acceptance"
STATUS=0
$PY -m struggler.bots.benchmark --accept "$OUT/full-vs-base.json" "$OUT/full-vs-held.json" || STATUS=$?
echo "results in $OUT"
exit $STATUS
