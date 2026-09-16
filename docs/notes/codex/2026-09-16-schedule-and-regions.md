# 2026-09-16 — Schedule + other regions: the rebuild's second step

Two extensions on top of the Africa prototype, still nothing wired into any
ranking (the safety gate on the unwired branch is running as this lands).

## `bots/strategic/schedule.py` (new): when each scoring can pay

Every future scoring opportunity as `(card, bucket, turns_lo..hi,
occurrence)` from the public deck state. Nine tests in
`tests/test_schedule.py`.

Occurrence mass, first version, all assumptions in the module docstring:

- Bucket 1: 1.0 when we hold the card (the engine forbids holding a scoring
  past end of turn -- `must_play_scoring` -- so it fires this turn), 0.5 for
  a live card of unknown holder.
- Bucket 2: 0.5 unknown holder / absent when held. The halves preserve
  exactly what the urgency consumer prices this cycle; they are holder
  uncertainty, not timing, so bucket 2's range overlaps bucket 1 at turn 0.
  Shaping by `p_opponent_holds` is factor-2 work.
- Bucket 3: 1.0 when the card returns post-reshuffle or enters a future
  period. Bucket 4: named, never emitted. Bucket 5: `final_scoring_odds`
  for the six region cards -- never Southeast Asia (`_finish_game` scores
  every *region*).
- Absent means zero: removed cards, spent one-shots, beyond-horizon timings
  (ranges are capped at the horizon -- a test caught bucket 2 escaping it).

The unmodeled part, stated not hidden: nothing discounts for the game ending
early (20 VP, Europe control, DEFCON, Wargames). These masses say what the
deck guarantees.

## Other regions: the prototype was already general

`forecast.py` takes the region throughout; the all-region immediate tests
pinned it. This step adds what was actually Africa-specific:

- `expected_southeast_asia_payout`: +2 Thailand / +1 others, linear and exact
  under any forecast, separate from Asia's tiers (pinned against
  `Engine._score_southeast_asia`, including a correction the engine forced:
  Malaysia is stab 2, one point does not control it).
- `europe_control`: names the automatic-victory condition (pinned against
  `Board.region_tier`), a query for the integration step, never a price --
  expected VP must not override a certain win.
- `Terrain.southeast_asia`: the 7 SEA indices on the static map (additive
  field, suite-pinned). Superpower adjacency needed nothing new -- the bonus
  term was already general, Africa just never exercises it.

## Docs

`STRATEGIC_AI.md` gains the schedule paragraph; the package lists six
modules. Ruff clean on all touched files (the one SIM103 in `evaluator.py`
is pre-existing on HEAD). Full suite green before commit (see commit).
