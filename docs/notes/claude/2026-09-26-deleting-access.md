# Deleting `access`: the rule, written before the number

`access` prices the uncontrolled battlegrounds a holding lets its side
reach: each one's value over its stability, shared across the routes into
it by the measured conversion rate. It is the largest piece of the country
value that the ablations found unimportant. With it set to 0, the
2026-09-24 sweep read **-0.011 [-0.032, +0.011]**, paired over 1152
games (run 35937042894,
[the scorecard](../pi/2026-09-24-the-weights-what-each-one-is-worth.md),
row 11). That covers 0, which makes it a deletion candidate. The
maintainer asked for the deletion on 2026-09-26, measured at 2048 seeds
or more because the term is so large.

## What the branch deletes

`chore/delete-access` removes the following, in commit `1d067c7` with the
corpus recaptured in `4eaeed5`, stacked on PR #62:

- the `access` and `access_decay` weights;
- `evaluator.access`;
- the route decay, `CONVERSION_P` and its pooled rate;
- the access half of `country_value`.

`country_value` now reads only its own country, so **`VALUE_RADIUS`
falls from 2 to 0**. This was checked over all 84 countries and both
sides, and the dependents and `delta`-exactness tests pass. A trial
placement no longer re-values its neighbours. Removing the now-unreached
neighbour-cache machinery is a follow-up.

### Two costs known before the run

1. **Most rankings change.** Before the recapture, 447 of 532 corpus
   records mismatched somewhere and 23 changed their top action. The
   recaptured corpus has 426 records, because the games are shorter.
2. **One expert judgement is lost.** On the opening board,
   De-Stalinization's event now reads 59.2, against 80.6 for its 3 Ops.
   With access included, the event beat its Ops, and
   `models/expert_valuations.json` prices it at 7 Ops.
   `test_de_stalinization_is_simulated_and_beats_its_ops` is a strict
   xfail on the branch rather than a weakened test.

## The arms

Both arms play against the anchor `bc5ef93` on the same seeds, paired
seed by seed. This is the region-margin precedent: the same code with and
without the term, each pinned by SHA.

- `access-base-vs-bc5ef93`: `bot_ref` `e434b93`, the parent. It plays
  identically to main after #61, and the parity corpus is the proof.
- `access-deleted-vs-bc5ef93`: `bot_ref` `4eaeed5`, with `compare_to`
  set to the base.

Seeds 140000-142047: **2048 a side, 4096 games an arm**, on a fresh
block. The reserve is 142100-142227, two spare shards. The run uses
`waves: false`, so every seed plays; no early stop.

## THE RULE, not moved after the number

Read `access-deleted` paired against `access-base`.

1. **Delete** (merge the branch through its gate) if the paired interval
   covers 0 or lies above it, AND the bot's DEFCON-1 losses (both seats
   summed) do not exceed the base's by more than half. The bar is "not
   measurably worse", as for the region margin, because deleting a term
   buys simplicity and speed, which a dead heat does not have to pay for.
2. **Keep** `access` (close the branch unmerged) if the upper bound is
   below 0, or if the nuclear veto fires.
3. A reading that covers 0 with a lower bound below -0.010 still deletes
   under (1). The note that records it must say that a loss of up to that
   size was not ruled out.

What it cannot settle:

- **Whether the De-Stalinization miss matters.** One card's price is
  about 1% of the decisions a game makes.
- **The speed win.** The radius-0 `delta` is cheaper, but a runner's
  clock is not a timing. If the deletion lands, that is a local
  measurement of its own.

## The reading

(Filled in at read time.)
