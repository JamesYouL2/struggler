# 2026-09-14 — Battleground value is three terms, and the region term needs turn-smoothing too

## The formula function

`StrategicPlayer._scoring_weight_uncached`
(`src/struggler/bots/strategic/policy.py`) is the maintainer's double sum:
for each battleground, over each future scoring, `value x probability x
turn_discount`. Today it accumulates the discount alone; value and
probability are the rebuild described in
`docs/notes/claude/2026-09-12-value-times-probability-times-discount.md`.
The `experiment/turn-discount-two-state` branch is reworking the third
factor (measured retention `r ** j` per scoring cycle instead of scalar
`scoring_discount ** turns`).

## The maintainer's correction to factor 1 (value)

Value is three terms, not one per-scoring VP number:

    value = bg value + adjacency + region value

- **bg value**: 1 VP per controlled battleground (rule 10.1.2), which
  `evaluator.region_vp` already computes exactly.
- **adjacency**: 1 VP per controlled country adjacent to the enemy
  superpower (rule 10.1.2, the `is_bg + (i in home[1 - holder])` bonus
  term) -- also already exact in `region_vp`.
- **region value**: the tier VP (presence/domination/control) the
  country's control actually swings.

## The region term needs smoothing by turn as well

The tier swing is discontinuous -- one battleground short of domination
looks like three short until the tier flips -- so the raw swing cannot
enter the sum directly. Like the discount factor, it needs a
turn-dependent smoothing: weight the region term by how far off (and how
reachable) the tier flip is from here, not by whether the tier holds on
this board. The existing `margin_basis` machinery (partial credit toward
the next tier, capped at two of each margin) is the shape of that
smoothing; what changes is that it must be computed per future scoring
turn, inside the double sum, rather than once against the current board.

## Consequence for the in-flight work

The two-state branch prices what current control banks (`r ** j`) but
still multiplies it by the guessed `w.battleground` tier. The three-term
value and the turn-smoothed region term are the next rebuild on top of
it, not part of it -- finish and gate the retention discount first, then
replace factor 1 per this note.
