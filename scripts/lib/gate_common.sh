# Shared by scripts/gate.sh and scripts/drift_check.sh. Sourced, not run.
#
# The drift canary used to live inside gate.sh. Moving it out made these two
# scripts need the same three things, and copying them would be shape 4 in
# docs/notes/claude/bug-shapes.md -- two implementations of one rule, four
# recurrences. `snapshot` in particular has three separate hard-won details in
# it and must not be reimplemented.

# Each baseline gets its own directory holding that revision's whole
# `struggler/bots` package: benchmark.load_module resolves every
# `struggler.bots.*` import to it while `strategic.py` loads, so the baseline
# runs on its own code. Snapshotting `strategic.py` alone compared a
# `public_cards.py` change against itself and reported a dead heat.
#
# Sets ANCHOR_OK=0 if an *optional* ref predates the package split.
snapshot() {  # snapshot <ref> <dir> [optional]
  # Wipe first. `tar -x` overlays, it does not replace, so re-running at the
  # same HEAD against a different base used to leave both revisions' files
  # side by side -- and the layout has changed shape at least once
  # (`strategic.py` became the `strategic/` package), so the leftovers are not
  # always shadowed. That is a baseline made of two revisions, which is the
  # contamination this exists to prevent.
  rm -rf "$2"
  mkdir -p "$2"
  git archive "$1" src/struggler/bots | tar -x -C "$2" --strip-components=3
  if [ ! -e "$2/strategic/policy.py" ]; then
    # Pre-split: the bot was `strategic.py`, not `strategic/policy.py`, so
    # `--opponent strategic@.../strategic/policy.py` cannot resolve.
    if [ "${3:-required}" = required ]; then
      echo "FAILED: base $1 has no strategic/policy.py -- it predates the package split, so it cannot be a baseline for this HEAD."
      exit 4
    fi
    echo "note: anchor ref $1 predates the package split; disabled."
    ANCHOR_OK=0
  fi
}

# `load` is the 1-minute average; the count is python processes that are not
# this run's own benchmark workers.
machine() {
  # `pgrep -c` prints 0 *and* exits 1 when nothing matches, so a `|| echo 0`
  # fallback emits a SECOND line and the arithmetic sees "0\n0". Assign, then
  # default on the exit status.
  local all busy
  all=$(pgrep -cf '[p]ython' 2>/dev/null) || all=0
  busy=$(pgrep -cf '[b]ots.benchmark' 2>/dev/null) || busy=0
  printf 'load %s, %s other python processes, %s cores' \
    "$(cut -d' ' -f1 /proc/loadavg)" "$(( all - busy ))" "$(nproc)"
}

# Worst conditions seen so far. Load is a float, so awk does the comparison.
PEAK_LOAD=0
PEAK_OTHER=0
sample_machine() {
  local all busy other load
  all=$(pgrep -cf '[p]ython' 2>/dev/null) || all=0
  busy=$(pgrep -cf '[b]ots.benchmark' 2>/dev/null) || busy=0
  other=$(( all - busy ))
  load=$(cut -d' ' -f1 /proc/loadavg)
  [ "$other" -gt "$PEAK_OTHER" ] && PEAK_OTHER=$other
  PEAK_LOAD=$(awk -v a="$load" -v b="$PEAK_LOAD" 'BEGIN{printf "%.2f", (a>b)?a:b}')
  # `return 0` is load-bearing, not tidiness. Under `set -e` a bare
  # `[ cond ] && assign` whose condition is false makes the function return 1
  # and kills the caller -- and that condition is false exactly when nothing
  # else is running, so without this it would abort on a QUIET machine and
  # pass every hand check on a busy one. Same shape as the `pgrep -c` bug.
  return 0
}

# A run asked for `--workers N` should sit near load N. Foreign python at all,
# or load well above the workers requested, means the clock was shared and no
# timing from the run may be quoted. Shape 7: timing measured under
# uncontrolled conditions, three recurrences -- recorded, not assumed.
contention_verdict() {  # contention_verdict <workers>
  # NOT `-v load=`: `load` is a gawk builtin (the @load mechanism) and gawk dies
  # with "cannot use gawk builtin as variable name". Caught by `gate.sh --check`.
  #
  # Peak LOAD decides; the foreign-process count is context and must not
  # trigger. Measured on this machine, an idle VS Code sits at 4-5 python
  # processes (pylance, the env server) that consume no cores, so `foreign > 0`
  # would mark every run contended and the flag would be ignored within a week.
  # A process that is not running is not contention -- load is what moves the
  # clock.
  awk -v peak="$PEAK_LOAD" -v foreign="$PEAK_OTHER" -v workers="${1:-8}" 'BEGIN {
    if (peak > workers + 2)
      printf "CONTENDED (peak load %.2f against %d workers, %d foreign python) -- wall time and mean_game_seconds are NOT quotable from this run", peak, workers, foreign
    else
      printf "clean (peak load %.2f against %d workers, %d idle foreign python) -- timings are quotable", peak, workers, foreign
  }'
}
