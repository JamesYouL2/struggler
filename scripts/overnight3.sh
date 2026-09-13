#!/usr/bin/env bash
# Overnight queue, 2026-09-12: measurements the 2026-09-13 Claude handoff and
# Codex's full audit (docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md)
# both want, and nothing that needs a judgement.
#
# Split per the queue skill: the game run that has a workflow went to CI, and
# this script keeps what is local by nature.
#
#   CI       -- gate f492dc3 with every game played (gate.yml decide=0),
#               dispatched before launch; its run id is $1
#   1. suite            -- red stops everything, before any commit
#   2. self-play        -- f492dc3 vs launch HEAD, paired by seed, with every
#                          sandbox failure's stack kept (handoff sec. 2, 4c)
#   3. determinism      -- 16 of the games CI run 34731449614 played, replayed
#                          here: do they come out identical on this machine?
#   4. collect CI       -- wait for the full-sample gate, download it, compare
#                          with the curtailed run (audit F3/F4), commit a note
#
# DROPPED, deliberately: conversion p at two scorings (handoff 4d). The
# collector resolves on a scoring card being CHOSEN, not scored -- audit F1 --
# so a second horizon would double a bias nobody has measured. Fix F1 first.
#
# NOTHING DEPENDS ON AN EARLIER VERDICT. Each item answers its own question
# from its own games; step 4 only reads what CI produced.
#
# NOT `set -e`: a failed item is recorded and the queue continues. Staging is
# EXPLICIT PATHS, never `git add -A`. The gate base is a pinned SHA. Steps 2-3
# play from snapshots and a worktree of the launch commit, so editing src/ or
# scripts/ overnight cannot change what they measure.
#
# Usage: scripts/overnight3.sh <ci-run-id>   (empty: step 4 is left for the morning)
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/overnight3/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$ROOT/$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'
NOTES=docs/notes/claude
REPO=JamesYouL2/struggler

CI_FULL_RUN=${1:-}
BASE=f492dc311f2dc293beca19d5d4c869dd3a9c4b1a      # the route-decay change's parent
CI_CURTAILED_RUN=34731449614
CI_CURTAILED=$ROOT/logs/ci-gate-$CI_CURTAILED_RUN/f492dc3
SELF_SEEDS=9000-9191
LAUNCH=$(git rev-parse HEAD)

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

commit() {  # commit <message> <paths...>
  local msg=$1; shift
  git add -- "$@" 2>>"$STATUS"
  if git diff --cached --quiet; then say "  (nothing to commit)"; return 0; fi
  git commit -q -m "$msg" -m "$ATTRIB" -- "$@" && say "  committed: $(git log --oneline -1)"
}

fence() {  # fence <file>: a file's contents as a markdown code block
  printf '```text\n'; cat "$1" 2>/dev/null || echo "(missing: $1)"; printf '```\n'
}

# compare_reports <new-dir> <reference-dir> <planned-per-sample> [subset-dir]
# Both dirs hold full-vs-base.json and full-vs-held.json. Prints how many games
# finished against the plan (a stall exits 0 and says nothing -- audit F4),
# and which (seed, seat) games differ in outcome. With a subset dir, writes the
# NEW games restricted to the seeds the reference finished, as reports the real
# acceptance code can read -- not a second implementation of it.
compare_reports() {
  $PY - "$@" <<'PYEND'
import json, os, sys
new_dir, ref_dir, planned = sys.argv[1], sys.argv[2], int(sys.argv[3])
subset = sys.argv[4] if len(sys.argv) > 4 else None
key = lambda g: (g['seed'], g['bot_side'])
outcome = lambda g: (g['result'], g['turn'], g['vp'], g['reason'])
for name in ('full-vs-base', 'full-vs-held'):
    new = json.load(open(f'{new_dir}/{name}.json'))
    ref = json.load(open(f'{ref_dir}/{name}.json'))
    ng = {key(g): g for g in new['games'] if g.get('finished')}
    rg = {key(g): g for g in ref['games'] if g.get('finished')}
    both = sorted(ng.keys() & rg.keys())
    same = [k for k in both if outcome(ng[k]) == outcome(rg[k])]
    print(f'{name}: {len(ng)} of {planned} planned games finished'
          f'{"" if len(ng) == planned else "  <-- INCOMPLETE (a stall exits 0; audit F4)"}')
    print(f'  reference played {len(rg)}; {len(both)} in both; identical (result, turn, VP, reason) on {len(same)}')
    for k in [k for k in both if k not in same][:10]:
        print(f'    differs {k}: reference {outcome(rg[k])} new {outcome(ng[k])}')
    s, r = new.get('summary', {}), ref.get('summary', {})
    print(f'  new:       score {s.get("score")} +/-{s.get("score_halfwidth")} over {s.get("seeds")} seeds')
    print(f'  reference: score {r.get("score")} +/-{r.get("score_halfwidth")} over {r.get("seeds")} seeds')
    if subset:
        os.makedirs(subset, exist_ok=True)
        sub = [ng[k] for k in sorted(ng) if k in rg]
        json.dump(dict(summary={}, games=sub), open(f'{subset}/{name}.json', 'w'))
PYEND
}

. "$ROOT/scripts/lib/gate_common.sh"   # snapshot()

exec 9>"$ROOT/logs/overnight3/.lock"
if ! flock -n 9; then echo "overnight3 is already running" >&2; exit 5; fi

say "overnight3 starting at $(git rev-parse --short HEAD); CI full-sample run: ${CI_FULL_RUN:-none}; logs in $RUN"
while $PY scripts/gate_running.py --quiet; do
  say "  a local gate is running; waiting"; sleep 300
done

# --- 1. the suite decides whether anything gets committed ----------------
say "step 1: full test suite"
if $PY -m pytest -q -p no:cacheprovider > "$RUN/suite.log" 2>&1; then
  say "  suite PASSED: $(tail -1 "$RUN/suite.log")"
else
  say "  suite FAILED -- committing nothing and stopping."
  grep -E '^(FAILED|ERROR)' "$RUN/suite.log" | head -5 | tee -a "$STATUS"
  exit 1
fi

WT=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$WT" 2>/dev/null' EXIT
SETUP_OK=0
if git worktree add -q --detach "$WT" "$LAUNCH" \
   && ( snapshot "$BASE" "$ROOT/$RUN/base" ) >>"$STATUS" 2>&1 \
   && ( snapshot "$LAUNCH" "$ROOT/$RUN/head" ) >>"$STATUS" 2>&1; then
  SETUP_OK=1
else
  say "  setup FAILED (worktree or snapshot); steps 2 and 3 will be skipped"
fi

# --- 2. self-play, paired by seed, with sandbox stacks kept -------------
say "step 2: self-play $SELF_SEEDS, base ${BASE:0:7} vs launch ${LAUNCH:0:7}"
if [ "$SETUP_OK" = 1 ]; then
  for arm in base head; do
    say "  arm $arm"
    if (cd "$WT" && PYTHONPATH="$WT/src" $PY scripts/selfplay_trace.py \
          --bot "strategic@$ROOT/$RUN/$arm/strategic/policy.py" \
          --seeds "$SELF_SEEDS" --workers 8 --out "$ROOT/$RUN/selfplay-$arm" \
          > "$ROOT/$RUN/selfplay-$arm.txt" 2> "$ROOT/$RUN/selfplay-$arm.err"); then
      say "  arm $arm done: $(sed -n 1,2p "$RUN/selfplay-$arm.txt" | tr '\n' ' ')"
    else
      say "  arm $arm exit $? (3 = stalled, partial report kept) -- see $RUN/selfplay-$arm.err"
      tail -5 "$RUN/selfplay-$arm.err" | tee -a "$STATUS"
    fi
  done
  (cd "$WT" && PYTHONPATH="$WT/src" $PY scripts/selfplay_trace.py \
      --compare "$ROOT/$RUN/selfplay-base.json" "$ROOT/$RUN/selfplay-head.json") \
      > "$RUN/selfplay-compare.txt" 2>&1 || say "  compare FAILED"
fi
NOTE2=$NOTES/$(date +%F)-selfplay-lengths-and-sandbox-stacks.md
{
  echo "# Self-play game length at ${BASE:0:7} and ${LAUNCH:0:7}, and the sandbox failures' stacks"
  echo
  echo "Generated by \`scripts/overnight3.sh\` step 2. Two questions from"
  echo "\`2026-09-13-handoff-for-codex.md\`: section 2 (the corpus turn distribution"
  echo "moved after \`7a1ac6c\` -- are the games longer?) and 4c (where the Blockade"
  echo "RecursionError comes from). Strategic self-play, seeds $SELF_SEEDS, one seat"
  echo "per seed (the other is the same game), opening books varied by seed as the"
  echo "gate does. Both arms are snapshots loaded through \`strategic@\`; the engine,"
  echo "benchmark and tracer are the launch commit's for both. A is \`${BASE:0:7}\`"
  echo "(before the stability route decay), B is the launch commit."
  echo
  echo "## Paired comparison"
  echo
  fence "$RUN/selfplay-compare.txt"
  echo
  for arm in base head; do
    echo "## Arm $arm: summary and sandbox failures"
    echo
    fence "$RUN/selfplay-$arm.txt"
    echo
  done
  echo "Full stacks: \`$RUN/selfplay-{base,head}.failures.json\` (gitignored)."
  echo
  echo "## What this does not say"
  echo
  echo "Nothing about strength: self-play puts the same bot in both seats. A longer"
  echo "game is not a better one, and a shift in how games end is not an"
  echo "explanation of why. Zero failures means none in these games, not that the"
  echo "defect is gone. Nobody has read these numbers yet."
} > "$NOTE2"
commit "docs: self-play game length before and after the route decay, and sandbox stacks" "$NOTE2"

# --- 3. do CI's games replay identically on this machine? ----------------
say "step 3: replay 16 of CI run $CI_CURTAILED_RUN's games locally"
if [ "$SETUP_OK" = 1 ]; then
  mkdir -p "$RUN/det"
  # The gate's step 3, on four seeds of each sample: candidate from the
  # launch worktree (its src/struggler is the CI candidate's, checked below),
  # base from the snapshot, openings varied, no early stopping.
  (cd "$WT" && PYTHONPATH="$WT/src" $PY -m struggler.bots.benchmark --bot strategic \
      --opponent "strategic@$ROOT/$RUN/base/strategic/policy.py" \
      --seeds 4000-4003 --held-seeds 5000-5003 --workers 8 --vary-openings \
      --report "$ROOT/$RUN/det/full-vs-base.json" --held-report "$ROOT/$RUN/det/full-vs-held.json") \
      > "$RUN/det.out" 2> "$RUN/det.err" || say "  replay exit $? -- see $RUN/det.err"
  compare_reports "$RUN/det" "$CI_CURTAILED" 8 > "$RUN/det-compare.txt" 2>&1 || say "  determinism compare FAILED"
fi
if git diff --quiet 93a78d3bb70ea9b36c71cb20f0925ede6dd34eae "$LAUNCH" -- src/struggler; then
  SAME_SRC="src/struggler at launch is identical to the CI candidate 93a78d3"
else
  SAME_SRC="WARNING: src/struggler at launch DIFFERS from the CI candidate 93a78d3; not a replication"
fi
NOTE3=$NOTES/$(date +%F)-ci-games-replayed-locally.md
{
  echo "# Sixteen of CI's gate games, replayed on this machine"
  echo
  echo "Generated by \`scripts/overnight3.sh\` step 3. Seeds are deterministic, so a"
  echo "game CI played should come out identical here; that is what lets a CI"
  echo "verdict stand in for a local one. Codex's audit F3 adds that the *prefix*"
  echo "an early-stopped run keeps depends on completion order, which is not"
  echo "deterministic -- this checks the games themselves, not the prefix."
  echo "Seeds 4000-4003 and 5000-5003, both seats, against CI run $CI_CURTAILED_RUN."
  echo
  echo "- $SAME_SRC"
  echo
  fence "$RUN/det-compare.txt"
  echo
  echo "## What this does not say"
  echo
  echo "Sixteen identical games do not prove every game replays; one that differs"
  echo "would be a finding in its own right and is listed rather than explained."
  echo "The scores here are over four seeds and mean nothing."
} > "$NOTE3"
commit "docs: replay sixteen of CI's gate games locally" "$NOTE3"

# --- 4. collect the CI full-sample gate ----------------------------------
if [ -z "$CI_FULL_RUN" ]; then
  say "step 4: no CI run id given; collection left for the morning"
else
  say "step 4: waiting for CI run $CI_FULL_RUN"
  waited=0
  while :; do
    st=$(gh run view "$CI_FULL_RUN" -R "$REPO" --json status -q .status 2>>"$STATUS")
    [ "$st" = completed ] && break
    if [ "$waited" -ge 25200 ]; then say "  still '$st' after 7h; leaving it for the morning"; break; fi
    sleep 120; waited=$((waited + 120))
  done
  CONCLUSION=$(gh run view "$CI_FULL_RUN" -R "$REPO" --json conclusion -q .conclusion 2>>"$STATUS")
  say "  run $CI_FULL_RUN: status ${st:-unknown}, conclusion ${CONCLUSION:-none} (failure = rejected OR crashed; read the log)"
  DL=$ROOT/logs/ci-gate-$CI_FULL_RUN
  if [ "$st" = completed ] && gh run download "$CI_FULL_RUN" -R "$REPO" -D "$DL" >>"$STATUS" 2>&1; then
    FULL_DIR=$(dirname "$(find "$DL" -name full-vs-base.json | head -1)")
    GATE_LOG=$(find "$DL" -name gate.log | head -1)
    {
      compare_reports "$FULL_DIR" "$CI_CURTAILED" 128 "$ROOT/$RUN/ci-subset"
      echo
      echo "acceptance on ALL the full-sample games:"
      $PY -m struggler.bots.benchmark --accept "$FULL_DIR/full-vs-base.json" "$FULL_DIR/full-vs-held.json"
      echo "  exit $?"
      echo
      echo "acceptance on the full-sample games restricted to the seeds the curtailed run finished:"
      $PY -m struggler.bots.benchmark --accept "$RUN/ci-subset/full-vs-base.json" "$RUN/ci-subset/full-vs-held.json"
      echo "  exit $?"
    } > "$RUN/ci-compare.txt" 2>&1
    tail -45 "$GATE_LOG" > "$RUN/ci-gate-tail.txt" 2>/dev/null
  else
    say "  download skipped or FAILED; collect by hand: gh run download $CI_FULL_RUN -R $REPO"
  fi
  NOTE4=$NOTES/$(date +%F)-gate-without-early-stopping.md
  {
    echo "# The route-decay gate with every game played"
    echo
    echo "Generated by \`scripts/overnight3.sh\` step 4. CI run $CI_CURTAILED_RUN gated"
    echo "\`93a78d3\` against \`${BASE:0:7}\` (the stability route decay alone) and ACCEPTED"
    echo "at pooled 0.500 +/-0.027, curtailed by \`--decide\` at 84 of 128 seeds per"
    echo "sample. Codex's audit F3 says stopping and acceptance can disagree; the"
    echo "curtailed reports hold no incomplete seed pair (checked 2026-09-12), so the"
    echo "open question is only whether the verdict survives the rest of the sample."
    echo "CI run $CI_FULL_RUN is the same gate dispatched with \`decide=0\`."
    echo
    echo "- CI conclusion: **${CONCLUSION:-unknown}** (a job fails on rejection and on a crash alike)"
    echo
    echo "## Against the curtailed run"
    echo
    fence "$RUN/ci-compare.txt"
    echo
    echo "## Gate log (tail)"
    echo
    fence "$RUN/ci-gate-tail.txt"
    echo
    echo "## What this does not say"
    echo
    echo "ACCEPTED means not measurably worse, never better. One agreement or"
    echo "disagreement is one data point about early stopping, not a calibration."
    echo "Nobody has read these numbers yet."
  } > "$NOTE4"
  commit "docs: the route-decay gate with every game played, collected from CI" "$NOTE4"
fi

say "overnight3 finished"
grep -E "PASSED|FAILED|done:|exit|WARNING|conclusion|committed" "$STATUS" | sed 's/^/  /'
