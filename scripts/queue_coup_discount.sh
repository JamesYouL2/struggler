#!/usr/bin/env bash
# The coup_discount removal: wait for its experiment, gate it, collect both.
#
# The maintainer's call (2026-09-13): the variable does not make sense -- dice
# and their board consequences are already priced, so a 0.9 on top is a
# placement preference, not a rule -- "but wait for the experiment". So:
#
#   1. wait for the full-seed experiment arm (coup_discount 1.0, every one of
#      256 seeds played) to finish on CI
#   2. dispatch the CI gate of the branch that deletes the variable against
#      its pinned base, every game played
#   3. wait for the gate, download both, and commit one note of the numbers
#
# Split per the queue skill: the games run on CI, and this local script only
# waits, dispatches and collects. It dispatches the gate WHATEVER the
# experiment says -- nothing here depends on an earlier verdict, and whether to
# merge is the maintainer's decision, not this script's. It never pushes; the
# note is committed to the local branch it is run from, by explicit path.
#
# Usage: scripts/queue_coup_discount.sh <base-sha> <branch> <experiment-run-id>
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
REPO=JamesYouL2/struggler
BASE=$1; BRANCH=$2; EXPERIMENT=$3
RUN=logs/queue-coup-discount/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$ROOT/$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }
fence() { printf '```text\n'; cat "$1" 2>/dev/null || echo "(missing: $1)"; printf '```\n'; }

exec 9>"$ROOT/logs/queue-coup-discount.lock"
if ! flock -n 9; then echo "already running" >&2; exit 5; fi

wait_run() {  # wait_run <id> <max-seconds>: 0 once completed, 1 on timeout
  local waited=0 st
  while :; do
    st=$(gh run view "$1" -R "$REPO" --json status -q .status 2>>"$STATUS")
    [ "$st" = completed ] && return 0
    [ "$waited" -ge "$2" ] && { say "  run $1 still '$st' after $2s"; return 1; }
    sleep 120; waited=$((waited + 120))
  done
}

say "base ${BASE:0:7}, branch $BRANCH, experiment run $EXPERIMENT; logs in $RUN"

# --- 1. the experiment --------------------------------------------------
say "step 1: waiting for experiment run $EXPERIMENT"
wait_run "$EXPERIMENT" 28800
say "  experiment: $(gh run view "$EXPERIMENT" -R "$REPO" --json conclusion -q .conclusion 2>&1)"

# --- 2. the gate --------------------------------------------------------
say "step 2: dispatching the gate of $BRANCH against ${BASE:0:7}"
BEFORE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if gh workflow run gate -R "$REPO" --ref "$BRANCH" -f bases="[\"$BASE\"]" \
     -f seeds=4000-4063 -f held=5000-5063 -f decide=0 >>"$STATUS" 2>&1; then
  sleep 20
  GATE=$(gh run list -R "$REPO" --workflow gate --branch "$BRANCH" --limit 5 \
           --json databaseId,createdAt -q "[.[] | select(.createdAt >= \"$BEFORE\")][0].databaseId" 2>>"$STATUS")
  say "  gate run: ${GATE:-NOT FOUND}"
else
  say "  gate dispatch FAILED"; GATE=
fi
[ -n "$GATE" ] && wait_run "$GATE" 25200
[ -n "$GATE" ] && say "  gate: $(gh run view "$GATE" -R "$REPO" --json conclusion -q .conclusion 2>&1)"

# --- 3. collect ---------------------------------------------------------
say "step 3: collecting"
OUT=$ROOT/$RUN/readings.txt
: > "$OUT"
for id in $EXPERIMENT $GATE; do
  gh run download "$id" -R "$REPO" -D "$ROOT/logs/ci-$id" >>"$STATUS" 2>&1 \
    && say "  run $id downloaded" || say "  run $id NOT downloaded"
done
{
  echo "== experiment run $EXPERIMENT: coup_discount 1.0 against the shipped 0.9, same code, every seed"
  held=$(find "$ROOT/logs/ci-$EXPERIMENT" -name '*.held.json' | head -1)
  if [ -n "$held" ]; then
    $PY - "${held%.held.json}.json" "$held" <<'PYEND'
import json, math, statistics, sys
from struggler.bots.benchmark import seed_scores
games = [g for p in sys.argv[1:] for g in json.load(open(p))['games']]
v = list(seed_scores(games).values())
m, se = statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))
print(f'  score {m:.3f}, 95% two-sided [{m - 1.96 * se:.3f}, {m + 1.96 * se:.3f}] over {len(v)} seeds, '
      f'{sum(1 for g in games if g.get("finished"))} games')
PYEND
    $PY -m struggler.bots.benchmark --accept "${held%.held.json}.json" "$held" | grep -E "strength|^ACCEPTED|^REJECTED"
  else
    echo "  (no experiment report)"
  fi
  echo
  echo "== gate run ${GATE:-none}: branch $BRANCH (variable deleted) against ${BASE:0:7}, every game played"
  base_report=$(find "$ROOT/logs/ci-${GATE:-none}" -name full-vs-base.json 2>/dev/null | head -1)
  if [ -n "$base_report" ]; then
    dir=$(dirname "$base_report")
    $PY -m struggler.bots.benchmark --accept "$dir/full-vs-base.json" "$dir/full-vs-held.json" \
      | grep -E "strength|completeness|^ACCEPTED|^REJECTED"
    grep -hE "planned_games|finished_games|stop_reason" -m3 "$dir/full-vs-base.json" | sed 's/^/  /'
  else
    echo "  (no gate report)"
  fi
} >> "$OUT" 2>&1

NOTE=docs/notes/claude/$(date +%F)-coup-discount-experiment-and-gate.md
{
  echo "# coup_discount: the full-seed experiment and the gate of its deletion"
  echo
  echo "Generated by \`scripts/queue_coup_discount.sh\`. The maintainer's reading is that"
  echo "the variable does not make sense: a coup is already priced over its dice and"
  echo "their board consequences, so a 0.9 on top is a placement preference and not a"
  echo "rule. The 2026-09-12 arm read 0.526 [0.452, 0.600] but stopped early at 77 of"
  echo "256 seeds. The experiment below plays every seed at 1.0 on the shipped code; the"
  echo "gate plays branch \`$BRANCH\`, which deletes the variable, against \`${BASE:0:7}\`."
  echo "The two measure the same change two ways: a weight override, and the code."
  echo
  fence "$OUT"
  echo
  echo "## What this does not say"
  echo
  echo "ACCEPTED means not measurably worse, never better. Whether to merge the branch"
  echo "is the maintainer's call; this script dispatched the gate regardless of the"
  echo "experiment's result. Nobody has read these numbers yet."
} > "$NOTE"
git add -- "$NOTE" && git commit -q -m "docs: coup_discount experiment and the gate of its deletion, collected from CI" \
  -m "$ATTRIB" -- "$NOTE" && say "  committed: $(git log --oneline -1)"
say "finished"
