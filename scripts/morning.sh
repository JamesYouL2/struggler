#!/usr/bin/env bash
# The morning queue: what the 2026-09-12 hang left unrun, in the order the
# maintainer set. Three items and a hard stop -- this runs while somebody is
# awake, not overnight, so it is sized to a morning rather than a night.
#
#   1. the space gate, standard size, FIRST
#   2. vp_swing 1.0, 80 seeds -- and the term comes out if it passes
#   3. scoring_discount 0.55, 80 seeds
#   4. scoring_final 3.0, 80 seeds
#   5. the reliability curve, from the traces the three above leave behind
#
# Why this order:
#
# - The space gate goes first because it is the only item that can reveal
#   something already broken. c0ccd95 shipped the Space Race ability pricing
#   and its gate never ran -- the access ablation hung ahead of it. Every
#   later measurement is taken against that code, so if it regressed, the
#   two A/Bs below are measuring a moving baseline. It is also the cheapest.
# - vp_swing goes first of the three A/Bs because it is the only one whose
#   passing outcome is a *deletion*, and the deletion is code work that can
#   be done while steps 3 and 4 are still running. The maintainer's call:
#   "I think 1.2 is closer to accurate, but I think simplification matters
#   more." The reliability curve anchored at T3 gives 8.07/6.63 = 1.22, and
#   4.0 measured 0.491 +/-0.026 -- no difference -- so the term is close to
#   inert in play and 1.0 is within noise of the supported value. At exactly
#   1.0 the curve `vp_base * vp_swing ** ((turn - 1) / 9)` collapses to
#   `vp_base`, so the deletion that follows is arithmetically inert and the
#   parity corpus proves it exactly. That is why this is gated once, here,
#   and not twice: the A/B decides the behaviour, the corpus decides the
#   refactor.
# - scoring_discount is third, ahead of scoring_final, because the
#   third-cycle defect in `scoring_schedule` is worth 9% of turn-1 urgency
#   at discount 0.8 and 0.6% at 0.55. Which of those is true decides whether
#   that defect is worth fixing at all, so the discount is measured before
#   it, not after. See
#   docs/notes/claude/2026-09-12-the-reshuffle-is-where-the-information-is.md.
# - scoring_final is third and independent of both: it is the only bucket
#   whose mass rises monotonically across the game (0.222 -> 1.0), so it is
#   the only lever that can make board value rise late. It is last of the
#   three because nothing waits on its result.
#
# Both A/Bs run at 80 seeds, not 256, on the maintainer's call: these are
# changes he is confident enough in to regression-gate rather than measure.
# 80 seeds is 160 games, which clears ACCEPTANCE's min_games of 150 -- the
# smallest sample that can still return a verdict rather than a number.
# What it buys and what it does not: the half-width goes from the measured
# +/-0.026 at 256 seeds to roughly +/-0.046, so this catches a change that
# makes the bot clearly worse and cannot resolve a small real gain. That is
# the trade a regression gate is, stated so nobody later quotes an 80-seed
# score as a measurement.
#
# The access ablation is NOT here, on the maintainer's call, and the reason
# is a finding rather than a scheduling preference: the family cannot be
# deleted whatever the ablation says, because it is what keeps countries
# with the same stability and region distinguishable at all. An experiment
# whose accepting outcome is unavailable is not worth 256 seeds. See
# docs/notes/claude/2026-09-12-access-is-the-tiebreaker.md.
#
# Standard gate size, not the 192 seeds overnight.sh asked for: the space
# change touches 1.6% of plays and is not resolvable at any affordable
# sample, so this is a no-regression check and the default 32+64 is what a
# no-regression check costs.
#
# NOT `set -e`. A failed item must not abandon the queue: the three are
# independent, so a surprise in one does not make the next the wrong thing
# to run. Failures are recorded and the queue continues.
#
# Staging is explicit, never `git add -A`: this may run while somebody is
# editing, and -A would sweep their work into an experiment's commit.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
RUN=logs/morning/$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
STATUS=$RUN/STATUS
ATTRIB='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS"; }

. "$ROOT/scripts/lib/queue_common.sh"  # run_ab, shared with the overnight queues

commit() {  # commit <message> <paths...>
  local msg=$1; shift
  git add "$@" 2>/dev/null
  if git diff --cached --quiet; then say "  (nothing to commit)"; return 0; fi
  git commit -q -m "$msg" -m "$ATTRIB" && say "  committed: $(git log --oneline -1)"
}

say "morning queue starting; logs in $RUN"

# --- 1. the space gate ----------------------------------------------------
# Base is 91f26d1, the commit BEFORE c0ccd95 shipped the ability pricing --
# not HEAD~1, which is now a docs commit and would put the space change on
# both sides of the comparison. Shape 3, the measurement comparing something
# against itself, six recurrences.
say "step 1: space abilities, gate at standard size against 91f26d1"
if scripts/gate.sh 91f26d1 > "$RUN/gate-space.log" 2>&1; then
  say "  space gate ACCEPTED"
else
  say "  space gate exit $? -- see $RUN/gate-space.log"
fi
tail -30 "$RUN/gate-space.log" >> "$STATUS"
commit "docs: gate the Space Race ability pricing at standard size" docs/notes/claude

# --- 2. a flat VP curve, and the deletion behind it -----------------------
say "step 2: vp_swing 1.0, 80 seeds"
run_ab "vp-swing-1x" '{"version": 1, "weights": {"vp_swing": 1.0}}' \
  "7800-7839" "7840-7879" "A flat VP curve: vp_swing 1.0 against the shipped 2.0, 80 seeds" \
  "The reliability curve over 668 decided games is flat from turn 3: spread(T3)/spread(T10) = 8.07/6.63 = 1.22. The headline 3.13 is anchored on turn 2, where the logistic barely identifies (slope 0.048 against turn 3's 0.124) and turn 1 separates outright, and it moved from 2.32 to 3.13 when the sample grew -- so it is an artifact of the anchor, not a measurement. 4.0 measured 0.491 +/-0.026. This is a regression gate on simplification, not a bid to win more games: at exactly 1.0 the turn-dependence collapses to a constant and the weight comes out of the model."
commit "docs: a flat VP curve regression-gated over 80 seeds" docs/notes/claude

# --- 3. a steeper scoring discount ---------------------------------------
say "step 3: scoring_discount 0.55, 80 seeds"
run_ab "scoring-discount-055" '{"version": 1, "weights": {"scoring_discount": 0.55}}' \
  "8400-8439" "8440-8479" "A steeper scoring discount: 0.55 against 0.8, 80 seeds" \
  "The far buckets carry turn 1's mass (cycle 2 and cycle 3 are both at 1.0 there) and the near buckets carry turn 9's, so a steeper discount raises the urgency ratio across the game -- modelled, it moves T9/T1 from 1.51x at 0.8 to about 2.49x at 0.5, peaking there. It also decides whether the missing third cycle in scoring_schedule is worth fixing: that defect is 9% of turn-1 urgency at 0.8 and 0.6% at 0.55."
commit "docs: a steeper scoring discount regression-gated over 80 seeds" docs/notes/claude

# --- 4. the final-scoring weight -----------------------------------------
say "step 4: scoring_final 3.0, 80 seeds"
run_ab "scoring-final-3x" '{"version": 1, "weights": {"scoring_final": 3.0}}' \
  "8100-8139" "8140-8179" "Tripling the final-scoring weight, 80 seeds" \
  "Measured over 429 corpus positions, the expected-scorings mass in every other bucket is flat or falling across the game -- 'scores this turn' sits at 0.16-0.23 with no trend -- while final_scoring_odds is the only one that rises monotonically, 0.222 -> 0.750 -> 1.0. So it is the only term that can make board value rise late, which is what the maintainer's reading requires. scoring_final is 1.0 today, the same weight as one ordinary region scoring, for the one scoring that is certain if the game runs the distance."
commit "docs: triple the final-scoring weight, regression-gated over 80 seeds" docs/notes/claude

# --- the deck-cycling numbers, free -------------------------------------
# bc5ef93 added reshuffle_turns and removed_cards to every game record and no
# run has used them yet. These two reports are the first, so the deck note's
# open question -- does the bot really reshuffle at turn 9, and how many
# cards leave the game -- is answered by games that were going to be played
# anyway. Costs nothing; that is why it is here rather than in its own item.
say "deck cycling, from the games above"
$PY - "$RUN" <<'PYEOF' 2>&1 | tee -a "$STATUS"
import json, statistics, sys, glob, collections
rows = []
for path in sorted(glob.glob(f'{sys.argv[1]}/*.json')):
    if path.endswith('.held.json'):
        continue
    games = json.load(open(path)).get('games', [])
    turns = [g['reshuffle_turns'] for g in games if g.get('reshuffle_turns')]
    if not turns:
        continue
    second = [t[1] for t in turns if len(t) > 1]
    removed = [g['removed_cards'] for g in games if g.get('removed_cards') is not None]
    name = path.rsplit('/', 1)[-1]
    print(f'  {name}: {len(games)} games')
    print(f'    first reshuffle:  {collections.Counter(t[0] for t in turns).most_common()}')
    print(f'    second reshuffle: {collections.Counter(second).most_common()} '
          f'({len(second)}/{len(turns)} games reach one)')
    if removed:
        print(f'    cards removed:    mean {statistics.fmean(removed):.1f} '
              f'median {statistics.median(removed)}')
PYEOF
commit "docs: the bot's reshuffle turns and removal count, measured" docs/notes/claude

# --- 5. the reliability curve --------------------------------------------
# overnight.sh step 8, which never ran -- the hang blocked at step 5. It
# reads `vp_by_turn` out of every report it is given and fits spread(turn),
# so it costs no games at all: the three items above plus every gate report
# on disk are its input. Run last because the two A/Bs above add 320 games
# of traces to the pool.
say "step 5: reliability curve from the VP traces"
if $PY scripts/vp_spread.py "$RUN"/*.json logs/game-check/gate-*/full-vs-*.json \
     > "$RUN/reliability.log" 2>&1; then
  say "  done:"; sed 's/^/    /' "$RUN/reliability.log" | tee -a "$STATUS"
  cp "$RUN/reliability.log" docs/notes/claude/$(date +%F)-reliability-curve.txt
else
  say "  reliability FAILED (see $RUN/reliability.log)"
  tail -5 "$RUN/reliability.log" | tee -a "$STATUS"
fi
commit "docs: the reliability curve, fitted over every VP trace on disk" docs/notes/claude

say "morning queue finished"
grep -E "score |ACCEPTED|exit |FAILED" "$STATUS" | sed 's/^/  /' | tee -a "$STATUS"
