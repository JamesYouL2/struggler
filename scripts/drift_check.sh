#!/usr/bin/env bash
# The drift canary, on its own schedule.
#
# WHY IT IS NOT IN gate.sh ANY MORE. It never decided anything -- acceptance
# runs against HEAD~1 and never saw this -- so it spent 32 of every gate's 192
# games on a reading with no authority. Three consequences, all bad:
#
#  1. ~17% of every gate's wall time, on the maintainer's one-hour budget.
#  2. At 16 seeds it read 0.469 against v0.1.0 where the full 77-seed run gave
#     0.578: a 0.11 reversal. Raised to 32 (+/-0.055), still too blunt to see
#     the thing it exists for.
#  3. It cost the verdict 16 seeds (96 -> 80), which put the verdict pool so
#     close to `ACCEPTANCE['min_games']` that early stopping could shave at
#     most 5 seeds. A gate measured on 2026-09-11 stopped at 153 of 160.
#
# Drift is a slow accumulation across many commits. Sampling it per-commit is
# high-frequency measurement of a low-frequency signal with a blunt
# instrument. Once a day it can afford a sample large enough to mean
# something, for less total compute than 32 seeds on every gate.
#
# THE EXIT STATUS IS THE VERDICT, so a scheduler can act on it. Non-zero means
# the bot has measurably drifted below the anchor.
#
# Usage: scripts/drift_check.sh [anchor-ref=v0.1.0] [seeds=6000-6079] [workers=8]
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
. "$ROOT/scripts/lib/gate_common.sh"

OLD=${1:-v0.1.0}
SEEDS=${2:-6000-6079}
WORKERS=${3:-8}
PY=${PYTHON:-$ROOT/.venv/bin/python}

HEAD_SHA=$(git rev-parse --short HEAD)
STARTED=$(date +%s)
OUT=$ROOT/logs/drift/$(date +%Y%m%d)-${HEAD_SHA}
mkdir -p "$OUT"

echo "drift check: HEAD $HEAD_SHA vs $OLD on seeds $SEEDS"
echo "  started $(date -Is)"
sample_machine
echo "  machine: $(machine)"

ANCHOR_OK=1
snapshot "$OLD" "$OUT/old" optional
if [ "$ANCHOR_OK" != "1" ]; then
  echo "DRIFT CHECK SKIPPED: anchor $OLD predates the package split." >&2
  exit 0
fi

SNAP=$(mktemp -d)
git worktree add -q --detach "$SNAP" HEAD
trap 'git worktree remove --force "$SNAP"' EXIT
cd "$SNAP"
export PYTHONPATH=src

# No --vary-openings: an anchor from before the opening books cannot be given
# one, and falling back would start the two arms from *different* boards.
sample_machine
$PY -m struggler.bots.benchmark --bot strategic \
    --opponent "strategic@$OUT/old/strategic/policy.py" \
    --seeds "$SEEDS" --workers "$WORKERS" --report "$OUT/report.json" \
    2>"$OUT/drift.err" >/dev/null || {
      echo "DRIFT CHECK FAILED: the benchmark crashed. stderr:" >&2
      tail -n 20 "$OUT/drift.err" >&2
      exit 3
    }
sample_machine

STATUS=0
$PY - "$OUT/report.json" <<'PYEND' || STATUS=$?
import json, sys
report = json.load(open(sys.argv[1]))
s = report['summary'] if 'summary' in report else report
score = s['score']
half = s.get('score_halfwidth')
seeds = s.get('seeds')
print(f"  score {score:.3f} +/-{half:.3f} over {seeds} seeds "
      f"({s.get('games')} games, {s.get('nuclear_losses')} nuclear losses)")
print(f"  US win rate {s.get('us_win_rate')}, mean end turn {s.get('mean_end_turn')}, "
      f"endings {s.get('endings')}")
# The whole point of a bigger sample: the verdict is the interval, not the
# point estimate. Drift is called only when the UPPER bound is still below
# parity -- the same one-sided logic `benchmark.acceptance` uses, so that a
# noisy reading cannot raise an alarm the gate would not have raised.
upper = score + half
if upper < 0.500:
    print(f"  DRIFT: the 95% upper bound {upper:.3f} is below 0.500. HEAD has "
          f"measurably fallen behind the anchor.")
    raise SystemExit(1)
print(f"  ok: upper bound {upper:.3f} reaches 0.500 -- no measurable drift.")
PYEND

TOOK=$(( $(date +%s) - STARTED ))
echo "  took $(( TOOK / 60 ))m$(( TOOK % 60 ))s"
echo "  contention: $(contention_verdict "$WORKERS")"
echo "  results in $OUT"
exit $STATUS
