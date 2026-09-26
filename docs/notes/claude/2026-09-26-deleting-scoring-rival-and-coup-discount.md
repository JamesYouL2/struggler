# Deleting `scoring_rival` and `coup_discount`: the rule, before the number

These are the other two deletion candidates from the 2026-09-24 sweep
([the scorecard](../pi/2026-09-24-the-weights-what-each-one-is-worth.md),
rows 12-13). Both covered 0 there:

- `scoring_rival` at 0: +0.006 [-0.014, +0.026];
- `coup_discount` at 1.0: -0.005 [-0.025, +0.015].

Those were paired over 1150 seeds on the sweep-era bot (`region` 1.3,
`military` 1.0). The third candidate, `access`, covered 0 in the same
sweep and then measured -0.055 at 2048 seeds on the current bot
([the access note](2026-09-26-deleting-access.md);
[why it moved](2026-09-26-why-access-moved.md)). So neither of these is
deleted on the sweep's evidence alone.

The maintainer's sizing (2026-09-26) is 1024 seeds, not 2048: "those
terms just matter less". `scoring_rival` shapes how scoring mass is timed
around a card the opponent may hold. `coup_discount` is a 10% haircut on
Coup and Realignment value.

## The arms: weight arms, exact by construction

Each "off" value removes its term exactly, so a weight arm measures the
deletion itself, with no branch needed:

- `scoring_rival` 0 skips the only branch that reads it
  (`if card not in obs.hand and w.scoring_rival`, in `policy.py` and
  `valuation.py`);
- `coup_discount` 1.0 is a multiplication by one at both of its reads.

All arms play current main (post-#62, identical in play to the access
run's base) against `bc5ef93`, on the fresh block 145000-146023 with
reserve 146100-146227, and waves off:

- `rc-base`: the shipped bot;
- `rival-off`: `{scoring_rival: 0.0}`, compared to `rc-base`;
- `coup-flat`: `{coup_discount: 1.0}`, compared to `rc-base`.

## THE RULE, not moved after the number, for each arm separately

1. **Delete** (the code branch goes through its gate) if the paired
   interval covers 0 or lies above it, AND the bot's DEFCON-1 losses
   (both seats summed) do not exceed the base's by more than half.
2. **Keep** if the upper bound is below 0, or if the veto fires.
3. The record states what 1024 seeds can see: about +/-0.02. A deletion
   under (1) has ruled out only a loss larger than its lower bound.

## The readings

(Filled in at read time.)
