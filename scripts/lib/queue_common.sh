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

run_ab() {  # run_ab <slug> <json> <seeds> <held-seeds> <title> <context>
  local slug=$1 json=$2 seeds=$3 held=$4 title=$5 context=$6
  say "  $slug: $json over $seeds + $held"
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
