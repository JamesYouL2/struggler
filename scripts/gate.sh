#!/usr/bin/env bash
# The three checks every value-function change must pass before it lands:
#   1. the turn-1 event-value table (read it by eye) and the expert-valuation diff,
#   2. the turn-3 checkpoint against the previous commit,
#   3. full games against the previous commit and against the pre-session bot.
# Usage: scripts/gate.sh [base-ref] [pre-session-ref] [seeds] [workers]
# Results go to logs/game-check/gate-<head>/ and a one-line summary is printed.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${1:-HEAD}
OLD=${2:-b2e8572}
SEEDS=${3:-4000-4015}
WORKERS=${4:-4}
PY=${PYTHON:-.venv/bin/python}
HEAD_SHA=$(git rev-parse --short HEAD)
DIRTY=$(git status --porcelain src | grep -q . && echo "-dirty" || true)
OUT=logs/game-check/gate-${HEAD_SHA}${DIRTY}
mkdir -p "$OUT"
git show "$BASE:src/struggler/bots/strategic.py" > "$OUT/base_strategic.py"
git show "$OLD:src/struggler/bots/strategic.py" > "$OUT/old_strategic.py"
export PYTHONPATH=src
echo "== 1. turn-1 table (seed ${SEEDS%%-*})"
$PY -m struggler.bots.benchmark --table --seeds "$SEEDS" | tee "$OUT/table.txt"
summ() { $PY -c "import sys,json; d=json.loads(sys.stdin.read()); print({k:d[k] for k in ('score','mean_signed_vp','mean_total','nuclear_losses') if k in d})"; }
echo "== 1b. expert valuations (US Ops)"
$PY -m struggler.bots.benchmark --expert models/expert_valuations.json --seeds "$SEEDS" | tee "$OUT/expert.txt" | grep -E 'misses|BROKEN|<--'
echo "== 2. turn-3 checkpoint vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>/dev/null | summ
echo "== 3a. full games vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-base.json" 2>/dev/null | summ
echo "== 3b. full games vs pre-session $OLD"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/old_strategic.py" --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/full-vs-old.json" 2>/dev/null | summ
echo "results in $OUT"
