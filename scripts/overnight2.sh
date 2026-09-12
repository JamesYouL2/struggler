#!/usr/bin/env bash
# Follow-on queue: the maintainer's reading that vp_swing is a small effect
# and the board side is the large one.
#
#   "I actually think this isn't very large at all. Should experiment at 1x
#    or close to 1x actually. What is large is ops/vp changing because of
#    battleground/board vp mattering much less over time."
#
# Waits for scripts/overnight.sh to finish before starting: the machine's
# timings are part of every result, so two queues at once corrupt both.
#
# NOT `set -e` -- a failed item must not abandon the queue. Nothing here
# depends on an earlier verdict: all four are independent measurements, so
# a surprise in one does not make the next one the wrong thing to run.
#
# Staging is explicit, not `git add -A`: overnight.sh uses -A and would
# otherwise sweep whatever is written while it runs into an experiment's
# commit.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/overnight2/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'
SEEDS_PER=256

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

. "$ROOT/scripts/lib/queue_common.sh"  # run_ab, shared with overnight.sh

commit() {  # commit <message> <paths...>
  local msg=$1; shift
  git add "$@" 2>/dev/null
  if git diff --cached --quiet; then say "  (nothing to commit)"; return 0; fi
  git commit -q -m "$msg" -m "$ATTRIB" && say "  committed: $(git log --oneline -1)"
}

say "follow-on queue queued; waiting for the first to finish"
while $PY scripts/gate_running.py --match overnight.sh --quiet; do sleep 60; done
say "first queue finished; starting"

# --- 1. the diagnostic, minutes, and it says whether 3 and 4 mean anything
say "step 1: does scoring_discount move Battleground VP, or cancel?"
if $PY scripts/board_vp_by_turn.py --discounts 0.8,0.6,0.5,0.4 \
     > "$RUN/board-vp.log" 2>&1; then
  say "  done:"; sed 's/^/    /' "$RUN/board-vp.log" | tee -a "$STATUS"
  cp "$RUN/board-vp.log" docs/notes/claude/$(date +%F)-battleground-vp-by-turn-and-discount.txt
else
  say "  FAILED (see $RUN/board-vp.log)"; tail -5 "$RUN/board-vp.log" | tee -a "$STATUS"
fi
commit "docs: measure whether scoring_discount moves Battleground VP or cancels" \
  docs/notes/claude


# --- 2. vp_swing at 1.0 --------------------------------------------------
say "step 2: vp_swing 1.0 (flat) at $SEEDS_PER seeds"
run_ab "vp-swing-1x" '{"version": 1, "weights": {"vp_swing": 1.0}}' \
  "7800-7927" "7928-8055" "A flat VP curve: vp_swing 1.0 against the shipped 2.0" \
  "Fitting the win-probability slope per turn from the gate's VP traces gives spread(T3..T10) of 7.45 -> 6.86, a ratio of 1.09 -- essentially flat -- and the headline 2.32 comes almost entirely from turn 2, where every game sits at 0 VP and the logistic is barely identified. 4.0 measured 0.491 +/-0.026. With 1.0, 2.0 and 4.0 all measured the curve has three points rather than a guess and a rejection."
commit "docs: vp_swing 1.0 measured against the shipped 2.0" docs/notes/claude

# --- 3. the final-scoring weight -----------------------------------------
say "step 3: scoring_final 3.0 at $SEEDS_PER seeds"
run_ab "scoring-final-3x" '{"version": 1, "weights": {"scoring_final": 3.0}}' \
  "8100-8227" "8228-8355" "Tripling the final-scoring weight" \
  "Measured over 429 corpus positions, the expected-scorings mass in every other bucket is flat or falling across the game -- 'scores this turn' sits at 0.16-0.23 with no trend -- while final_scoring_odds is the only one that rises monotonically, 0.222 -> 0.750 -> 1.0. So it is the only term that can make board value rise late, which is what the maintainer's reading requires. scoring_final is 1.0 today, the same weight as one ordinary region scoring, for the one scoring that is certain if the game runs the distance."
commit "docs: triple the final-scoring weight, measured over 256 seeds" docs/notes/claude

# --- 4. a steeper discount ------------------------------------------------
say "step 4: scoring_discount 0.55 at $SEEDS_PER seeds"
run_ab "scoring-discount-055" '{"version": 1, "weights": {"scoring_discount": 0.55}}' \
  "8400-8527" "8528-8655" "A steeper scoring discount: 0.55 against 0.8" \
  "The far buckets carry turn 1's mass (cycle 2 and cycle 3 are both at 1.0 there) and the near buckets carry turn 9's, so a steeper discount raises the urgency ratio across the game -- modelled, it moves T9/T1 from 1.51x at 0.8 to about 2.49x at 0.5, peaking there. Whether that survives into Battleground VP rather than cancelling against ops_value(1) is what step 1 measures; this measures whether it is worth anything in play."
commit "docs: a steeper scoring discount measured over 256 seeds" docs/notes/claude

say "follow-on queue finished"
grep -E "score |done:|FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
