#!/usr/bin/env bash
# The overnight queue. One item at a time, on a machine to itself, committing
# after each -- the maintainer's instruction, so that a machine that dies at
# 3am still leaves every finished result in git.
#
# NOT `set -e`. A failed item must not abandon the queue: nothing after step 2
# depends on an earlier verdict, which is the property that makes the queue
# safe to run unattended in the first place. Failures are recorded and the
# queue continues.
#
# Order is the maintainer's: 4x vp_swing, then the access ablation, then
# space. Sizes are chosen from the effect expected, not from habit -- see
# docs/notes/claude/ on why the space change is a no-regression check rather
# than a strength measurement (it touches 1.6% of plays).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/overnight/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

commit() {  # commit <message>
  git add -A
  if git diff --cached --quiet; then
    say "  (nothing to commit)"
    return 0
  fi
  git commit -q -m "$1" -m "$ATTRIB" && say "  committed: $(git log --oneline -1)"
}

say "overnight queue starting; logs in $RUN"

# --- 0. let any capture finish -------------------------------------------
while pgrep -f "[c]apture_corpus" >/dev/null 2>&1; do sleep 20; done
say "corpus capture idle"

# --- 1. the suite decides whether anything gets committed ----------------
say "step 1: full test suite"
if $PY -m pytest -q > "$RUN/suite.log" 2>&1; then
  say "  suite PASSED: $(tail -1 "$RUN/suite.log")"
else
  say "  suite FAILED -- committing nothing and stopping."
  say "  $(grep -E '^FAILED|^ERROR' "$RUN/suite.log" | head -5)"
  exit 1
fi

# --- 2. land the night's work --------------------------------------------
# The gate in step 6 must compare against the tree as it stood BEFORE tonight's
# code change -- and steps 3-5 each commit a note, so by then HEAD~1 is a
# docs commit and the space change would be on both sides of the comparison,
# which reports a dead heat by construction. Shape 3: the measurement
# comparing something against itself, six recurrences. Pin the base now.
BASE_SHA=$(git rev-parse --short HEAD)
say "gate base for step 6 pinned at $BASE_SHA"
commit "feat(bots,gate): price the Space Race ability boxes, share the rules
arithmetic, and move the drift canary out of the gate

Space: boxes 2, 4 and 6 award no VP, so \`space_race_expected_vp\` returned
exactly 0.0 and \`space_value\` read an attempt as a pure cost -- a zero-VP
wall in front of box 3 (2 VP), 5 (3) and 7 (4), none of which is reachable
without crossing one. The abilities are priced instead, in VP at par, on the
maintainer's numbers: 1.0 / 1.0 / 1.5 / 1.0. The premium applies only when we
would be first, because Engine._grant_space_ability pops the effect when the
opponent draws level. \`test_value_signs.py\` missed this for so long because
it parametrised over turns and always started from an empty track.

rules_math: nine pure functions of public state left greedy.py, where four
other modules imported them. benchmark.py runs GreedyPlayer as a baseline, so
a change made there for the strategic bot would have moved the thing it is
measured against. Verified inert: the parity corpus reproduces all 429
positions with the new ability weights forced to 0.0.

gate: the drift canary never decided anything -- acceptance runs against
HEAD~1 and never saw it -- and it cost the verdict 16 seeds, leaving early
stopping 5 seeds of headroom (the 2026-09-11 gate stopped at 153 of 160). It
is now scripts/drift_check.sh on a staleness schedule. HELD returns to
5000-5063. gate.sh gained a contention watch: every timing it prints is
quotable only if it had the cores to itself, and that is now recorded rather
than assumed.

bug-shapes: shape 9, a process check that matches the process doing the
checking. Four recurrences, including a guard written to prevent it."

# --- 3. fast measurements -------------------------------------------------
say "step 3: fast measurements"
$PY scripts/vp_spread.py logs/game-check/gate-*/full-vs-*.json \
    > "$RUN/spread.log" 2>&1 && say "  spread fit: $(tail -2 "$RUN/spread.log" | head -1)" \
    || say "  spread fit FAILED (see $RUN/spread.log)"
commit "docs: fit spread(t) from the VP traces the gate now records"

# --- 4. 4x vp_swing, the maintainer's first item -------------------------
run_weight_ab() {  # run_weight_ab <slug> <json> <seeds> <title> <context>
  local slug=$1 json=$2 seeds=$3 title=$4 context=$5
  say "  $slug: seeds $seeds"
  echo "$json" > "$RUN/$slug.weights.json"
  # --stall-timeout, because one game hung this script for four hours on
  # 2026-09-12 with nothing able to interrupt it. Early stopping cannot help:
  # it is evaluated only when a game finishes, and `_decided` is additionally
  # gated on a held sample this path does not pass.
  if $PY -m struggler.bots.benchmark --bot strategic \
       --bot-weights "$RUN/$slug.weights.json" --opponent strategic \
       --seeds "$seeds" --stall-timeout 1200 \
       --workers 8 --report "$RUN/$slug.json" \
       > "$RUN/$slug.out" 2>"$RUN/$slug.err"; then
    $PY scripts/report_note.py "$RUN/$slug.json" --title "$title" \
        --slug "$slug" --context "$context" >> "$STATUS" 2>&1
    say "  $slug done: $($PY -c "
import json;s=json.load(open('$RUN/$slug.json')).get('summary',{})
print(f\"score {s.get('score')} +/-{s.get('score_halfwidth')} over {s.get('seeds')} seeds\")")"
  else
    say "  $slug FAILED (see $RUN/$slug.err)"
    tail -5 "$RUN/$slug.err" | tee -a "$STATUS"
  fi
}

say "step 4: 4x vp_swing at 256 seeds"
run_weight_ab "vp-swing-4x" '{"version": 1, "weights": {"vp_swing": 4.0}}' \
  "7000-7255" "4x vp_swing against the shipped 2x, 256 seeds" \
  "A paired weight A/B: both sides run the same code and differ only in vp_swing, so no commit or snapshot is involved. 2.0 is what the scarcity of remaining VP supports; 4.0 is the total swing the retired three-step era rates implied, and the maintainer wanted it measured for swinginess and late-war variance reasons."
commit "docs: 4x vp_swing measured against the shipped 2x over 256 seeds"

# --- 5. the access ablation ----------------------------------------------
say "step 5: access ablation at 256 seeds"
# 0.01, NOT 0.0, on the maintainer's instruction and it is the better
# experiment as well as the safer one. Zero makes the term vanish, so
# positions that differed only in it tie *exactly* and whatever breaks ties
# explores far more -- which is almost certainly what made the 0.0 run hang
# for four hours on one game. At 0.01 the ordering survives while ~99% of the
# magnitude is gone, which separates "does this term's size matter" from
# "does this term discriminate at all". Zero conflated the two.
run_weight_ab "ablate-access" '{"version": 1, "weights": {"access": 0.01}}' \
  "7300-7555" "Ablating the access family to 1%, 256 seeds" \
  "All four access weights are guesses and all four are recorded underdetermined; access=1.5 is the master multiplier, so zeroing it removes the family in one move. It is also the expensive term -- it reads influence two hops out and has caused two of the seven caching defects -- so if this accepts, the family is a deletion candidate and every later game gets cheaper. At +/-0.020 this distinguishes 'worth nothing' from 'worth 2%'; it cannot rule out a smaller real effect."
commit "docs: ablate the access family over 256 seeds"

# --- 6. the space change, as a no-regression check ------------------------
say "step 6: space abilities, gate at 192 seeds"
if scripts/gate.sh "$BASE_SHA" 7600-7695 8 7700-7795 > "$RUN/gate-space.log" 2>&1; then
  say "  space gate ACCEPTED"
else
  say "  space gate exit $? -- see $RUN/gate-space.log"
fi
tail -30 "$RUN/gate-space.log" >> "$STATUS"
commit "docs: gate the Space Race ability pricing over 192 seeds"

# --- 7. the drift canary's first standalone run ---------------------------
say "step 7: drift check, 80 seeds"
if scripts/drift_check.sh v0.1.0 6000-6079 8 > "$RUN/drift.log" 2>&1; then
  say "  drift: no measurable drift"
else
  say "  drift check exit $? -- see $RUN/drift.log"
fi
tail -20 "$RUN/drift.log" >> "$STATUS"
commit "docs: first standalone drift check against v0.1.0"

# --- 8. the reliability curve --------------------------------------------
say "step 8: reliability curve from the VP traces"
$PY scripts/vp_spread.py "$RUN"/*.json logs/game-check/gate-*/full-vs-*.json \
    > "$RUN/reliability.log" 2>&1 \
    && say "  $(tail -2 "$RUN/reliability.log" | head -1)" \
    || say "  reliability FAILED (see $RUN/reliability.log)"
commit "docs: reliability of VP-at-turn as a win predictor"

say "overnight queue finished"
say "summary:"
grep -E "done:|ACCEPTED|FAILED|drift:" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
