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
# Usage: scripts/gate.sh [base-ref=HEAD~1] [drift-ref=v0.1.0] [seeds=4000-4031] [workers=8] [held-out=5000-5047] [drift-seeds=6000-6015]
# Results go to logs/game-check/gate-<head>/ and a one-line summary is printed.
# The candidate is a snapshot: HEAD is checked out into a temporary
# worktree and every benchmark runs from there, so editing the working
# tree while a gate runs cannot change what it measures (it did, once:
# a gate blamed a nuclear loss on a commit that never produced one).
# The drift run (3c) plays the candidate against the oldest tag still
# believed sound (docs/VERSIONING.md, default v0.1.0) rather than against
# HEAD~1. One baseline cannot see drift: a run of individually-neutral
# changes can walk the bot downward with every single gate accepting.
#
# It gets its own 16 seeds, paid for by taking the verdict from 96 down to
# 80 -- so the whole gate still plays 192 games and costs what it did.
#
# Not a half-and-half split, which is the obvious version and costs more
# than it looks: 48 seeds widens the verdict's half-width from +/-0.032 to
# +/-0.045, and a wider interval makes the gate *more permissive* exactly
# where it is meant to be strict. It also leaves ~96 games, under the 150
# `benchmark.ACCEPTANCE` requires. At 80 the half-width is +/-0.035, 9%
# wider, and 160 games clears the floor with room -- `_decided` will not
# stop below 150 whatever the score says, so early stopping can shave at
# most five seeds here rather than its usual 15%.
#
# 32 seeds, raised from 16 after the canary read 0.469 against v0.1.0 and
# the full 77-seed run gave 0.578 -- a reversal of 0.11, which is what a
# 16-seed sample can do. At 32 the half-width is about +/-0.055 rather
# than +/-0.078, and every score the gate prints now carries its interval,
# so a reading like that cannot be mistaken for a signal again.
#
# The drift check is still a canary, not a verdict: acceptance decides
# against HEAD~1 and never sees this. GATE_ANCHOR=0 turns it off if the
# hour is tight.
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
OLD=${2:-v0.1.0}
SEEDS=${3:-4000-4031}
DRIFT=${6:-6000-6031}   # the drift run's own seeds, disjoint from both samples
WORKERS=${4:-8}
HELD=${5:-5000-5047}
ROOT=$(pwd)
# Overlapping other work with a gate is allowed: the seeds are deterministic,
# so contention moves the clock and never the verdict. It does make the wall
# time uninterpretable unless it is written down, so it is. `load` is the
# 1-minute average; `busy` counts python processes that are not this gate's.
machine() {
  # `pgrep -c` prints 0 *and* exits 1 when nothing matches, so `|| echo 0`
  # emits a second line and the arithmetic below sees "0\n0". Assign, then
  # default on the exit status.
  local all busy
  all=$(pgrep -cf '[p]ython' 2>/dev/null) || all=0
  busy=$(pgrep -cf '[b]ots.benchmark' 2>/dev/null) || busy=0
  printf 'load %s, %s other python processes, %s cores' \
    "$(cut -d' ' -f1 /proc/loadavg)" "$(( all - busy ))" "$(nproc)"
}

PY=${PYTHON:-$ROOT/.venv/bin/python}
MACHINE_AT_START=$(machine)
HEAD_SHA=$(git rev-parse --short HEAD)
OUT=$ROOT/logs/game-check/gate-${HEAD_SHA}
mkdir -p "$OUT"
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
if [ "$CHECK" = "1" ]; then
  echo "--check: setup, helpers, snapshots and worktree all fine."
  echo "  machine: $MACHINE_AT_START"
  echo "  base $BASE -> $OUT/base; drift $OLD -> $OUT/old (ok=$ANCHOR_OK)"
  echo "  elapsed $(elapsed)"
  exit 0
fi
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
echo "== 1b. expert valuations (US Ops)"
$PY -m struggler.bots.benchmark --expert models/expert_valuations.json --seeds "$SEEDS" | tee "$OUT/expert.txt" | grep -E 'misses|BROKEN|PLACEMENT'
echo "== 1c. types and lint (advisory)"
# Advisory on purpose: the hard gate is tests/test_types.py, five rules at
# zero findings. This is the rest -- about 95 ty diagnostics of annotation
# debt and 109 ruff findings -- reported so the backlog stays visible
# without blocking a change on it.
"$ROOT/.venv/bin/ty" check --output-format concise 2>&1 | tail -1 | sed 's/^/  ty: /' || true
"$ROOT/.venv/bin/ruff" check --statistics src tests scripts 2>&1 | tail -3 | sed 's/^/  ruff: /' || true
echo "== 2. turn-3 checkpoint vs $BASE"
$PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/base/strategic/policy.py" --seeds "$SEEDS" --workers "$WORKERS" --stop-turn 3 --report "$OUT/t3-vs-base.json" 2>"$OUT/t3.err" | summ t3
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
if [ "${GATE_ANCHOR:-1}" = "1" ] && [ "$ANCHOR_OK" = "1" ]; then
  # No --vary-openings here: a baseline from before the opening books cannot
  # be given one, and falling back would start the two arms from *different*
  # boards. The drift question does not need varied openings anyway.
  echo "== 3c. drift: full games vs $OLD on seeds $DRIFT (fixed opening)"
  $PY -m struggler.bots.benchmark --bot strategic --opponent "strategic@$OUT/old/strategic/policy.py" \
     --seeds "$DRIFT" --workers "$WORKERS" --report "$OUT/full-vs-old.json" 2>"$OUT/anchor.err" | summ anchor
  # Deliberately not fed to step 4. Acceptance decides against HEAD~1; this
  # is a reading to look at, and a small sample cannot carry a verdict.
  echo "  (informational: drift is read by eye, not by the acceptance rules)"
fi
echo "== 4. acceptance"
STATUS=0
$PY -m struggler.bots.benchmark --accept "$OUT/full-vs-base.json" "$OUT/full-vs-held.json" || STATUS=$?
TOOK=$(elapsed)
SECONDS_TAKEN=$(( $(date +%s) - GATE_STARTED ))
echo "took $TOOK (budget: under 60m; $( [ "$SECONDS_TAKEN" -lt 3600 ] && echo ok || echo OVER ))"
echo "  machine at start: $MACHINE_AT_START"
echo "  machine at end:   $(machine)"
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
