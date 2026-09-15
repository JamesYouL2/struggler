# 2026-09-14 — Value-function rebuild plan (value x probability x turn_discount)

Parent: `docs/notes/claude/2026-09-12-value-times-probability-times-discount.md`
(the design) and `2026-09-14-battleground-value-three-terms.md` (the
maintainer's correction to factor 1). This is the execution plan now that
the retention discount has merged (`8da1000`).

## What the merged branch settled, and what it did not

Settled (foundation the rebuild builds on):

- Factor 3 has the right shape: per-scoring-cycle compounding, not a
  scalar power of turns. The discount no longer smuggles in factor 2's
  "that scoring may never happen".
- `RETENTION_P` (provenance: measured/determined) is factor 2's P(hold)
  input, with the contested-vs-pooled split documented as the refinement
  path.
- Urgency is per-country (stability-keyed), so the double sum can multiply
  per-country value x per-country retention directly.

Not settled (scaffolding the rebuild throws away):

- The `j in {1,2}` cycle-indexing conflates buckets 1+2 and cannot name
  bucket 4. Bucket-widening rewrites that loop regardless.
- `scoring_discount` survives as a dead knob; the rebuild deletes it.
- Factor 1 is still the guessed `w.battleground`; factor 2 outside
  retention does not exist.

## Dependency order (from the parent note, updated)

1. **Widen `scoring_schedule` to the five buckets** (this turn /
   pre-reshuffle / post-reshuffle-1 / post-reshuffle-2 / final).
   Behaviour-preserving check first: buckets 1+2 at equal probability
   with the current retention must reproduce today's numbers exactly
   (parity corpus holds the line). The `vp_swing` deletion rides along
   if still pending.
2. **Factor 1**: per-scoring VP from `region_vp`'s own accounting --
   bg value (1 VP) + adjacency (1 VP, rule 10.1.2) + the tier swing --
   with `region` at par. The tier swing enters turn-smoothed per future
   scoring (`margin_basis`-shaped partial credit inside the sum, not one
   reading of the current board). This is where `battleground`
   (provenance: known-wrong) gets fixed.
3. **Factor 2**, one bucket at a time. Bucket 1 is free (card in hand
   scores this turn with P = 1); bucket 5 has measured odds; buckets
   2-4 need the deck model `public_cards.py` now has the inputs for.
   Retention supplies P(hold) everywhere.
4. **Factor 3 last**: delete `scoring_discount`, recalibrate from the
   measured retention now that it prices only time.

## Release discipline (unchanged from the parent note)

One rebuild, one corpus re-capture, one gate. The two-state merge burned
a cycle deliberately (measured foundation, not a calibration); no further
installments land before the rebuild proper. Measurements taken meanwhile
-- including the running `region-par` / `scoring-hand-flat` /
`access-contested-off` arms -- are readings of the superseded model:
admissible as evidence, never shipped as calibration.

## Gate proposal for the merged retention discount (not dispatched)

`decide=0 vary=0` vs the pre-merge main, same seeds as the reply gates
(4000-4003 block already in the corpus is fine -- the gate plays games,
it never reads the corpus). Ship criterion: not measurably worse
(upper bound >= 0.500), same as B. Dispatch needs explicit approval.
