#!/usr/bin/env bash
# The three checks every value-function change must pass before it lands:
#   1. the turn-1 event-value table (read it by eye) and the expert-valuation diff,
#   2. the turn-3 checkpoint against the previous commit,
#   3. full games against the previous commit and against the pre-session bot.
# Usage: scripts/gate.sh [base-ref=HEAD~1] [pre-session-ref] [seeds=4000-4031] [workers=8]
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
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
HEAD_SHA=$(git rev-parse --short HEAD)
OUT=$ROOT/logs/game-check/gate-${HEAD_SHA}
mkdir -p "$OUT"
git show "$BASE:src/struggler/bots/strategic.py" > "$OUT/base_strategic.py"
git show "$OLD:src/struggler/bots/strategic.py" > "$OUT/old_strategic.py"
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
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>/dev/null | summ
echo "== 3a. full games vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-base.json" 2>/dev/null | summ
if [ "${GATE_ANCHOR:-0}" = "1" ]; then
  echo "== 3b. full games vs pre-session $OLD"
  $PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/old_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-old.json" 2>/dev/null | summ
fi
echo "results in $OUT"
