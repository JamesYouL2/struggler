# The weight A/B one queue item runs. Sourced, not executed.
#
# ONE COPY, deliberately. `overnight.sh` had `run_weight_ab` and
# `overnight2.sh` had `run_ab`; they were the same operation and they
# drifted, which is shape 4 in docs/notes/claude/bug-shapes.md -- two
# implementations of one rule, four recurrences. The drift was not
# cosmetic: only one of them passed `--decide` and `--held-seeds`, so half
# the queue could not stop early, and on 2026-09-12 an ablation ran to 511
# of 512 games and then hung on the last one for four hours with nothing
# able to curtail it. Add a flag here or nowhere.
#
# The caller defines: PY, RUN, STATUS, and say().

# SAMPLE SIZE: 128 by default, 256 the ceiling. Both are the maintainer's
# call and both have a reason that is not "it felt right".
#
# 128, and the binding reason is early stopping rather than resolution.
# ACCEPTANCE['min_games'] is 150 pooled games, so an 80-seed run is 160
# games and leaves `--decide` ten games of slack: it can save at most 6%
# however obvious the answer. Measured on 2026-09-12, the vp_swing run
# stopped at 153 of 160 -- seven games, 4%. Below about 100 seeds early
# stopping is decorative. At 128 (256 games) there are 106 games above the
# floor, so a decisive result curtails properly and an ambiguous one pays
# full price -- which is the right way round, since the ambiguous run is
# the one that wanted the precision.
#
# 256 as the ceiling because past it the clock buys very little. Half-width
# falls as 1/sqrt(n): the measured pooled figure was +/-0.072 at 78 seeds,
# so 128 buys about +/-0.056 and 256 about +/-0.040, while 512 would take
# four and a half hours for +/-0.028. Anything needing better than +/-0.04
# is not a sample-size problem -- it is asking the wrong question of a
# paired-seat score, and the answer is a diagnostic on corpus positions,
# which costs no games at all.
QUEUE_SEEDS_DEFAULT=128
QUEUE_SEEDS_MAX=256

# Counts the seeds in a `lo-hi` range, or a bare seed.
_seed_count() {
  case "$1" in
    *-*) echo $(( ${1#*-} - ${1%-*} + 1 ));;
    *)   echo 1;;
  esac
}

run_ab() {  # run_ab <slug> <json> <seeds> <held-seeds> <title> <context>
  local slug=$1 json=$2 seeds=$3 held=$4 title=$5 context=$6
  # The ceiling is enforced, not asked for. A run that quietly grows past it
  # spends hours nobody agreed to, and the machine is the scarce resource
  # here -- every queue in this repo is serialised behind it.
  local total=$(( $(_seed_count "$seeds") + $(_seed_count "$held") ))
  if [ "$total" -gt "$QUEUE_SEEDS_MAX" ]; then
    say "  $slug REFUSED: $total seeds is over the $QUEUE_SEEDS_MAX ceiling."
    say "    Past 256 the half-width improves as 1/sqrt(n) and buys almost"
    say "    nothing for the clock. If you need better than +/-0.04, the"
    say "    question wants a corpus diagnostic, not more games."
    return 2
  fi
  say "  $slug: $json over $seeds + $held ($total seeds)"
  echo "$json" > "$RUN/$slug.weights.json"
  # --decide AND --held-seeds, both of them. `_decided` is gated on a held
  # sample existing, so passing --decide alone does nothing. --stall-timeout
  # is defence in depth rather than the same guard twice: early stopping is
  # only evaluated when a game *finishes*, so it cannot rescue a hang.
  if $PY -m struggler.bots.benchmark --bot strategic \
       --bot-weights "$RUN/$slug.weights.json" --opponent strategic \
       --seeds "$seeds" --held-seeds "$held" --held-report "$RUN/$slug.held.json" \
       --decide --stall-timeout 1200 \
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
