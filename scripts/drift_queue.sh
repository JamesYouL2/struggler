#!/usr/bin/env bash
# The drift canary, queued behind whatever else is holding the machine.
#
# Settings, and why these:
#
# ANCHOR v0.1.0, not v0.2.0. Not merely because it is the longer lever --
# both are days old, this repo is young. The reason is 3df73a2: from the
# package split (136a8c6, 2026-09-10 07:07) until this morning, every gate
# ran a baseline made of its own policy.py and the CANDIDATE's evaluator,
# defcon, public_cards, greedy and rollout, because the snapshot finder was
# rooted one level too deep and resolved nothing. A change confined to any
# of those files was compared against itself and could only come back a
# dead heat. v0.1.0 is dated 2026-09-10 20:14, thirteen hours into that
# window, so it brackets essentially all of it. v0.2.0 (2026-09-11) sits
# almost entirely INSIDE the window and is the weaker test of the same
# question; it is the right anchor for bisecting if this one trips.
#
# SEEDS 128, not the default 80. drift_check.sh has no early stopping --
# no --decide, no held sample -- so the sample costs what it costs either
# way, and the verdict is one-sided: drift is called only when
# score + halfwidth < 0.500. At 80 seeds the half-width is about +/-0.046,
# so HEAD has to read below 0.454 to trip; at 128 it is about +/-0.036 and
# 0.464 trips it. That is the difference between catching a 5-point
# regression and a 3.5-point one, and this run is the only independent
# check on the blind window above, so it is worth the extra ~20 minutes.
# It is still a tripwire and not a measurement: a smaller real regression
# sits under it and reads as "no measurable drift".
#
# Not changed here: drift_check.sh's own defaults. This script passes
# arguments; it does not edit the canary, because the canary's defaults are
# the documented ones and a standing run should not silently redefine them.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/drift-queue/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

# Wait for BOTH, in case the space check has not started yet: it is itself
# waiting on the morning queue, so asking only about it would race.
say "drift check queued; waiting for the morning queue and the space check"
while $PY scripts/gate_running.py --match morning.sh --quiet \
   || $PY scripts/gate_running.py --match space_check.sh --quiet; do
  sleep 60
done
# One seed first, through the SAME script rather than a hand-rolled copy of
# its setup -- the snapshot and worktree cost seconds, and a second
# implementation of the setup is shape 4. This is not the defence against a
# broken baseline (that is the invariant inside load_module: a silently
# empty finder imports perfectly and resolves nothing). It is only here to
# keep a 50-minute run from discovering in minute 1 that the anchor cannot
# play at all, which is what happened to the gate at 07:27 today.
#
# Exit codes matter here. 3 is "the benchmark crashed" and is the thing
# being checked for. 1 is "drift called", which at one seed is noise and
# must NOT stop the real run -- the half-width at n=1 is enormous, so the
# one-sided rule can fire on nothing.
say "smoke: one seed against v0.1.0 before committing to 128"
scripts/drift_check.sh v0.1.0 6000-6000 8 > "$RUN/smoke.log" 2>&1
SMOKE=$?
if [ "$SMOKE" = "3" ]; then
  say "  SMOKE FAILED: the anchor cannot play. Not running the full check."
  tail -n 20 "$RUN/smoke.log" | sed 's/^/    /' | tee -a "$STATUS"
  exit 3
fi
say "  smoke ok (exit $SMOKE; 1 is a meaningless verdict at one seed, not a failure)"

say "starting drift check against v0.1.0 over 128 seeds"

if scripts/drift_check.sh v0.1.0 6000-6127 8 > "$RUN/drift.log" 2>&1; then
  say "  no measurable drift"
else
  say "  drift check exit $? -- see $RUN/drift.log"
fi
sed 's/^/    /' "$RUN/drift.log" | tee -a "$STATUS"

# The canary is advisory: it never gated anything, which is why it left the
# gate in the first place. Report it and let the maintainer read it.
say "drift check finished"
