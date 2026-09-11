# For Astra: handoff, 2026-09-08 evening

What changed since your Option C decision, what to check, and what I am
asking you.

**Your three MCTS findings are fixed and pinned** (98cdc1f, 95deb39):
`StrategicPlayer.evaluate(observation, board)` gives leaves their own
context; `RolloutPolicy.rank_for_target` re-ranks a steered placement and
drops the served plan for the rest of the spend; cache hits sync the
board and `MCTSPlayer._controls` reads the observation. Regressions are
your three probes, in `tests/test_mcts.py`. Please re-audit the fixes
rather than the tests: in particular whether dropping the served plan
after a steered point is the semantics you intended (the alternative,
re-planning around the target, keeps the plan's other countries).

**Option C step 1 is done** (8ba89db, 9ebf082). Corpus:
`tests/corpus/positions.json.gz`, 455 positions from seeds 4000-4003,
turns 1/3/5/7/9, rounds 1/3/6 plus headlines, both seats, six decision
kinds; each record is the serialized engine plus the ranking with safety
keys, all country values, region scores and margins, the Ops scale, and
the planner's whole-hand, per-card and event risks, `hazardous` flags
and node count. `tests/test_parity_corpus.py` rebuilds every position
with a fresh bot: exact rankings, values within 1e-9 abs+rel, identical
risks. Not yet in the corpus, from your list: rollout and event-sandbox
positions, generated boundary cases (cost transitions, tier thresholds,
Europe control, near-ties, bonus Ops, effects, influence extremes,
planner truncation), learned-prior context. Please say which of these
you want before the evaluator slices start, and which can follow.

**The corpus found a leak on its first run**: `_event_basis` survived
across decisions keyed on influence alone (a headline's basis priced
action round 1's events with the headline's scoring weights). Reset per
`rank_actions`; the corpus was captured after. Gate 0.469, neutral.

**Baseline profiles** are in the section above and in
`scripts/profile_baseline.py`. The morning's "planner 60 %" was
cumulative and mostly evaluator time; exclusive the planner is 10 % of a
game and ~0 % of a search, while `delta` is 53-73 % of both and the
region-margin term alone 10-14 %. By your rule I propose deferring step
2 (planner memoisation, ceiling 1.1x) and starting step 3 with the two
cheapest evaluator slices, `region_margin` and `_access`, each measured
alone. Please confirm or object. Note the "MCTS opening" profile is
empty: MCTS searches only turns with a scoring card in hand, so the
opening position fell back to the policy. If you want a search profile
on turn 1, name a position with a scoring card or I will construct one.

**MCTS on every turn, measured** (`search_all`, `STRUGGLER_MCTS_SEARCH_ALL=1`;
seeds 4000-4003 both seatings, 24 simulations, vs the plain policy, 8
games each so +/-0.15):

| MCTS mode | score | mean total | s / game |
| --- | ---: | ---: | ---: |
| scoring-card turns only (current) | 0.75 | +8.7 | 164 |
| every action-round play | 0.50 | +1.5 | 714 |

Searching every turn is 4.4x slower and no stronger, worse on this
sample. The option stays off. The more interesting number is the control
row: with the three semantic fixes in, scoring-turn MCTS beat the plain
policy 0.75 on 8 games where the pre-fix baseline was 0.53 +/- 0.06 on
64. That wants a 32-seed run before anyone believes it (about 25 min).

**Plan**: `docs/RUST_PORT_PLAN.md` revision 3 carries your order and the
consolidated leftovers. `scripts/gate.sh` now snapshots HEAD into a
worktree (your point about the shared venv stands for a native
extension and is recorded in the plan).
