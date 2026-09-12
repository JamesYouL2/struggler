#!/usr/bin/env bash
# scoring_discount 0.93 against the shipped 0.8, at the 256-seed ceiling.
#
# WHY THIS VALUE, and why it earns the ceiling where the earlier discount
# experiment did not. 9b90ef0 corrected the reshuffle horizon at turn 3 from
# 1.55 turns to 5.10 -- the fix is right, `test_entering_matches_what_the_
# engine_adds` checks the constant against the engine. But at
# scoring_discount = 0.8 that shrank the second scoring's weight from 0.708
# to 0.320: urgency at turn 3 fell 22.7%, and a four-anchor drift bisect
# measured the commit costing about 8 points of strength.
#
# Lengthening the horizon is arithmetically the same as steepening the
# discount -- 5.10 turns at 0.8 equals 1.55 turns at 0.47 -- and that
# direction was measured independently the same day: scoring_discount 0.55
# read 0.463 +/-0.064, the worst result of the day. Two experiments, same
# sign. The model over-discounts distant scorings, and the corrected horizon
# exposed it rather than caused it.
#
# 0.934 is the discount that restores the pre-regression turn-3 urgency
# (1.708) at the correct horizon. 0.93 is that, rounded.
#
# So this is not a sweep: it is a prediction with a mechanism, an isolated
# 8-point regression it should recover, and a failed experiment at 0.55 that
# fits the same curve. See
# docs/notes/claude/2026-09-12-the-reshuffle-fix-cost-eight-points.md.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/discount/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }
. "$ROOT/scripts/lib/queue_common.sh"

commit() {  # commit <message> <paths...>
  local msg=$1; shift
  git add "$@" 2>/dev/null
  if git diff --cached --quiet; then say "  (nothing to commit)"; return 0; fi
  git commit -q -m "$msg" -m "$ATTRIB" && say "  committed: $(git log --oneline -1)"
}

say "scoring_discount 0.93 at 256 seeds"
run_ab "scoring-discount-093" '{"version": 1, "weights": {"scoring_discount": 0.93}}' \
  "8800-8927" "8928-9055" "A shallower scoring discount: 0.93 against the shipped 0.8" \
  "Predicted from the reshuffle regression rather than swept. 9b90ef0 lengthened the turn-3 reshuffle horizon from 1.55 to 5.10 turns -- correctly -- which at discount 0.8 cut the second scoring's weight from 0.708 to 0.320 and turn-3 urgency by 22.7%. A four-anchor drift bisect put that commit at about 8 points of strength. 0.934 is the discount restoring the pre-regression urgency at the correct horizon. The same direction was measured independently: 0.55, steeper, read 0.463 +/-0.064."
commit "docs: scoring_discount 0.93 measured against the shipped 0.8" docs/notes/claude

say "finished"
grep -E "score |FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
