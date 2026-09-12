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


# --- 2. DROPPED: vp_swing at 1.0 ----------------------------------------
# Ran 2026-09-12 (0.497 +/-0.072 over 78 seeds), shipped, and the parameter
# was then REMOVED entirely -- per_vp is now the single constant vp_base.
#
# Left as a comment rather than deleted, because re-running it would have
# been worse than useless. `StrategicWeights.load` filters unknown keys and
# logs "ignoring retired fields", so `{"vp_swing": 1.0}` would be silently
# dropped and both arms would play the IDENTICAL shipped bot -- a dead heat
# by construction, reported as a result. That is shape 3, the measurement
# comparing something against itself, six recurrences. A dropped experiment
# whose weight no longer exists is an armed version of it.

# --- 3. the final-scoring weight -----------------------------------------
say "step 3: scoring_final 3.0 at $SEEDS_PER seeds"
run_ab "scoring-final-3x" '{"version": 1, "weights": {"scoring_final": 3.0}}' \
  "8100-8227" "8228-8355" "Tripling the final-scoring weight" \
  "Measured over 429 corpus positions, the expected-scorings mass in every other bucket is flat or falling across the game -- 'scores this turn' sits at 0.16-0.23 with no trend -- while final_scoring_odds is the only one that rises monotonically, 0.222 -> 0.750 -> 1.0. So it is the only term that can make board value rise late, which is what the maintainer's reading requires. scoring_final is 1.0 today, the same weight as one ordinary region scoring, for the one scoring that is certain if the game runs the distance."
commit "docs: triple the final-scoring weight, measured over 256 seeds" docs/notes/claude

# --- 4. DROPPED: a steeper scoring discount -----------------------------
# scoring_discount 0.55 ran on 2026-09-12 and read 0.463 +/-0.064 over 80
# seeds -- the weakest of the day and the only one that leaned clearly
# negative. Dropped on the maintainer's call rather than re-run larger,
# because the parameter is about to change meaning.
#
# `scoring_discount` is factor 3 of value x probability x turn_discount, and
# factors 2 and 3 have been doing each other's work: a discount raised to a
# power has been the ONLY way this model can express "that scoring may never
# happen", since factor 2 -- probability -- does not exist. So any value
# fitted now is fitting two effects at once, and the reading above is a
# measurement of the superseded model. Recalibrate it after the rebuild
# gives probability its own term, not before. See
# docs/notes/claude/2026-09-12-value-times-probability-times-discount.md.

say "follow-on queue finished"
grep -E "score |done:|FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
