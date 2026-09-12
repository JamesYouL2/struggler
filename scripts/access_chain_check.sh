#!/usr/bin/env bash
# Bisecting the access ablation: `access_chain` alone, at 128 seeds.
#
# The whole-family ablation was retired (2026-09-12-access-is-the-tiebreaker.md)
# because it had no available accepting branch: `access` is the master
# multiplier at evaluator.py:535, so zeroing it removes the family, countries
# identical in stability and region tie *exactly*, and the search loses its
# gradient -- which is what made the 0.0 run hang four hours on one game.
#
# `access_chain` is the opposite case on every count.
#
# SAFE: it does not gate the family, only the second loop inside `access()`.
# With it at zero, `access` still stands at 1.5 and the whole first-hop term
# is untouched, so countries stay distinguishable. No exact ties.
#
# EXPENSIVE: it is the sole contributor of the two-hop walk -- the only line
# the second loop reaches is `total += w.access_chain * ...`. Counted over
# the real board: 224 first-hop iterations against 670 second-hop and 2056
# third-hop reachability scans, so the chain walk is 92% of the traversal
# `access()` can do. (An upper bound; the early `continue`s prune it.)
# `access` is already the largest single term in the profile, ~11% of a game.
#
# SUSPECT: guess/underdetermined in models/provenance.json, like all four of
# the family -- "no recorded basis; could be wrong by a lot without anyone
# noticing".
#
# And the prize is structural rather than one deleted weight. If this
# accepts: the second loop can be guarded away, VALUE_RADIUS drops from 3 to
# 2, `dependents()` shrinks on every trial placement, and the two-hops-out
# read that made `access` unmemoisable -- the cause of two of the seven
# shape-1 caching defects -- stops existing.
#
# 128 SEEDS, and the reason is early stopping rather than resolution.
# ACCEPTANCE['min_games'] is 150 pooled games. At 80 seeds a run is 160
# games, so `--decide` has ten games of slack and can save almost nothing:
# the vp_swing run stopped at 153 of 160, which is 4%. At 128 seeds (256
# games) there are 106 games above the floor, so a decisive result can
# curtail properly. Resolution comes along for the ride: measured pooled
# half-width was +/-0.072 at 78 seeds, so 128 buys roughly +/-0.056 and a
# clear result costs well under its planned hour.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/access-chain/$(date +%Y%m%d-%H%M%S)
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

say "access_chain check queued; waiting for the morning queue"
while $PY scripts/gate_running.py --match morning.sh --quiet; do sleep 60; done
say "morning queue finished; starting"

run_ab "ablate-access-chain" '{"version": 1, "weights": {"access_chain": 0.0}}' \
  "8700-8763" "8764-8827" "Ablating access_chain alone, 128 seeds" \
  "The bisected access ablation. access_chain gates the entire two-hop walk inside access(): the second loop's only contribution is w.access_chain * contested * importance, so zeroing it silences that traversal while access=1.5 and the whole first-hop term stay intact -- countries remain distinguishable, which is exactly what the retired whole-family ablation could not promise. Counted over the board the chain walk is 92% of the traversal access() can do (224 first-hop iterations against 670 second-hop and 2056 third-hop scans), and access is the largest term in the profile at ~11% of a game. If this accepts the payoff is structural: the loop can be guarded away, VALUE_RADIUS falls from 3 to 2, dependents() shrinks per placement, and the two-hops-out read behind two of the seven caching defects stops existing."
commit "docs: ablate access_chain alone over 128 seeds" docs/notes/claude

say "access_chain check finished"
grep -E "score |FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
