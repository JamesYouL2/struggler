#!/usr/bin/env bash
# The Space Race ability pricing, regression-checked WITHOUT a baseline
# snapshot -- because as of 2026-09-12 there is no reachable baseline.
#
# scripts/morning.sh step 1 tried the normal thing, `gate.sh 91f26d1`, and
# died in two seconds:
#
#   ImportError: cannot import name '_coup_risks_defcon'
#   from 'struggler.bots.greedy' (<the CANDIDATE's greedy.py>)
#
# benchmark.py imports struggler.bots.strategic at module level, which pulls
# struggler.bots.greedy into sys.modules before `load_module` installs its
# finder -- and a finder is never consulted for an already-imported module.
# So the baseline's policy.py binds the *candidate's* greedy. c0ccd95 moved
# nine functions out of greedy.py into rules_math.py, so the import fails and
# every gate against a base older than c0ccd95 is unrunnable, drift_check.sh
# against v0.1.0 included. That is fixed separately, in load_module.
#
# This script does not need any of it. c0ccd95 records that the parity corpus
# reproduces all 429 positions with the ability weights forced to 0.0, so
# zeroing the four weights IS the pre-change behaviour -- expressed as a
# weight A/B, which runs entirely on current code and touches no snapshot.
# Same question, same 80 seeds, none of the machinery that is broken.
#
# Boxes 3, 5 and 7 award VP and are priced by the VP track, not by these
# weights; 2, 4, 6 and 8 are the ability boxes and are the whole of the
# change. Zeroing all four restores the zero-VP wall the change removed.
#
# Waits for the morning queue rather than running beside it: the machine's
# timings are part of every result, and two 8-worker runs at once corrupt
# both.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/space-check/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

. "$ROOT/scripts/lib/queue_common.sh"  # run_ab, shared with the other queues

commit() {  # commit <message> <paths...>
  local msg=$1; shift
  git add "$@" 2>/dev/null
  if git diff --cached --quiet; then say "  (nothing to commit)"; return 0; fi
  git commit -q -m "$msg" -m "$ATTRIB" && say "  committed: $(git log --oneline -1)"
}

# Waits for the access_chain bisect too, which the maintainer put ahead of
# this one: it is the experiment with a structural payoff, this is a
# no-regression check on a change that already shipped.
say "space check queued; waiting for the morning queue and the access_chain check"
while $PY scripts/gate_running.py --match morning.sh --quiet \
   || $PY scripts/gate_running.py --match access_chain_check.sh --quiet; do
  sleep 60
done
say "machine free; starting"

run_ab "space-abilities-off" \
  '{"version": 1, "weights": {"space_ability_2": 0.0, "space_ability_4": 0.0, "space_ability_6": 0.0, "space_ability_8": 0.0}}' \
  "7600-7639" "7640-7679" "The Space Race ability pricing, as a weight A/B at 80 seeds" \
  "c0ccd95 priced the four ability boxes because space_race_expected_vp returned exactly 0.0 for boxes 2, 4 and 6, so space_value read an attempt as a pure cost -- a zero-VP wall in front of every box that does pay. Zeroing the four weights restores that wall, so this measures the change itself without a baseline snapshot, which is what the normal gate would have used and which no longer loads for any base older than c0ccd95. A no-regression check, not a strength measurement: the change touches 1.6% of plays and is not resolvable at any affordable sample."
commit "docs: the Space Race ability pricing, checked as a weight A/B" docs/notes/claude

say "space check finished"
grep -E "score |FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
