#!/usr/bin/env bash
# What cron runs: a staleness check that usually does nothing.
#
# WHY NOT JUST `0 3 * * *`. This machine is WSL2. It stops when Windows
# sleeps and when the last terminal closes, so a fixed 3am entry fires only
# if the box happens to be awake at 3am -- and when it does not fire, nothing
# says so. That is the silent-no-coverage failure, which is strictly worse
# than leaving the canary inside gate.sh: it produces the *appearance* of
# coverage. "Fail loudly" was the condition on moving it out at all.
#
# So cron runs this hourly and on boot, and it decides for itself:
#
#   * in the 03:00-05:59 window, run if the last check is >= 20h old
#     -- the normal path, and it lands at ~3am when the box is up then;
#   * outside the window, run only if the last check is >= 26h old
#     -- the catch-up, for the night the machine was asleep.
#
# So a machine that is up at 3am behaves exactly as asked, and one that is
# not still gets checked within a few hours of waking. Both paths stamp
# LAST_RUN, so two runs never happen in one day.
#
# Usage: scripts/drift_cron.sh [--force|--dry-run] [args for drift_check.sh...]
#
# `--dry-run` prints the decision and exits without playing anything, and
# DRIFT_CRON_NOW / DRIFT_CRON_HOUR override the clock. Those two exist so the
# branch logic is testable: the whole value of this script is that it fires
# when it should, and that cannot be checked by reading it.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs/drift

STAMP=logs/drift/LAST_RUN
WINDOW_START=3
WINDOW_END=5
STALE_IN_WINDOW=$(( 20 * 3600 ))
STALE_ANY_TIME=$(( 26 * 3600 ))

FORCE=0
DRY=0
case "${1:-}" in
  --force)   FORCE=1; shift ;;
  --dry-run) DRY=1;   shift ;;
esac

now=${DRIFT_CRON_NOW:-$(date +%s)}
hour=${DRIFT_CRON_HOUR:-$(date +%-H)}
last=$(cat "$STAMP" 2>/dev/null) || last=0
case $last in ''|*[!0-9]*) last=0 ;; esac
age=$(( now - last ))

if [ "$FORCE" = "1" ]; then
  why="forced"
elif [ "$hour" -ge "$WINDOW_START" ] && [ "$hour" -le "$WINDOW_END" ] \
     && [ "$age" -ge "$STALE_IN_WINDOW" ]; then
  why="in the 03:00-05:59 window, $(( age / 3600 ))h since the last check"
elif [ "$age" -ge "$STALE_ANY_TIME" ]; then
  why="catch-up: $(( age / 3600 ))h since the last check, window was missed"
else
  # The common case. It must stay silent, or an hourly job makes the log
  # useless -- 24 "nothing to do" lines a day would bury the one that matters.
  [ "$DRY" = "1" ] && echo "would NOT run: $(( age / 3600 ))h old, hour $hour"
  exit 0
fi

if [ "$DRY" = "1" ]; then
  echo "would run: $why"
  exit 0
fi

# A drift check takes ~30 minutes and cron fires hourly, so overlap is
# reachable -- and two of these would fight over the same git worktree.
exec 9>logs/drift/.lock
if ! flock -n 9; then
  echo "$(date -Is) drift check already running; skipped" >> logs/drift/history.log
  exit 0
fi

# Stamp BEFORE running, not after. A crash or a kill must still count as an
# attempt: stamping only on success turns a reproducible failure into a job
# that retries every hour for ever.
printf '%s' "$now" > "$STAMP"

{
  echo "=== drift check $(date -Is) ($why) ==="
  scripts/drift_check.sh "$@"
  echo "EXIT=$?"
} > logs/drift/LATEST 2>&1
cat logs/drift/LATEST >> logs/drift/history.log

# The verdict as a filename, so `ls logs/drift/` is enough to read it.
if grep -q '^EXIT=0$' logs/drift/LATEST; then
  : > logs/drift/STATUS-ok
  rm -f logs/drift/STATUS-DRIFT
else
  : > logs/drift/STATUS-DRIFT
  rm -f logs/drift/STATUS-ok
fi
