# The Space Race had a zero-VP wall in front of every reward

Asked to "consider space a flat constant vp_value", the maintainer gave
prices for the ability boxes. Applying them found the reason they were
needed: the bot valued three of the eight boxes at exactly zero.

## The defect

`_space_race_expected_vp` (in `bots/greedy.py`, imported by the strategic
policy) is rules-faithful:

```python
vp = box["vp_first"] if first else box["vp_second"]
return probability * vp
```

Boxes 2, 4 and 6 award **0 VP to both first and second** -- they grant
abilities instead. So the helper returns exactly `0.0` there, and
`value_as_space` returned `vp_value * 0`. `space_value`, which nets a flat
`0.4 * ops_value(ops)` charge, therefore read the attempt as **strictly
negative**.

The Space Race track is sequential. Every reward box sits behind an
ability box:

| from | to | ops | p | VP awarded | bot's E[VP] | ability |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 1 | 2 | 0.50 | 2 | 1.00 | |
| 1 | 2 | 2 | 0.67 | 0 | **0.00** | two attempts per turn |
| 2 | 3 | 2 | 0.50 | 2 | 1.00 | |
| 3 | 4 | 2 | 0.67 | 0 | **0.00** | opponent's headline revealed first |
| 4 | 5 | 3 | 0.50 | 3 | 1.50 | |
| 5 | 6 | 3 | 0.67 | 0 | **0.00** | discard a held card each turn |
| 6 | 7 | 3 | 0.50 | 4 | 2.00 | |
| 7 | 8 | 4 | 0.33 | 2 | 0.67 | an extra action round |

Box 3 (2 VP), box 5 (3) and box 7 (4) are unreachable without crossing a
box the bot prices below zero.

## Why the sign test did not catch it

`test_a_space_race_attempt_is_worth_more_than_nothing` exists precisely to
assert "space is better than nothing". It parametrises over **turns** --
1, 4, 8, 10 -- and always starts from a fresh `Engine.new_game`, so the
track is always at box 0, where `vp_first` is 2. It never entered an
ability box.

The dimension it varied was not the dimension that mattered. That is one
instance, not a pattern: the repo's rule is that recurrence is the signal,
so it does **not** get a numbered entry in `bug-shapes.md` on a single
sighting. Recorded here so the second sighting can be recognised.

## The fix, and where it had to go

The premium is strategy, not a rule, so it does **not** belong in the
shared helper. `greedy.py` owns eight private helpers that
`strategic/policy.py` imports, and `benchmark.py` runs `GreedyPlayer` as a
baseline -- editing the helper would move a comparison baseline silently.
(That double duty is itself worth fixing: those helpers are
engine-adjacent arithmetic living in one bot's file. A move to a shared
module is behaviour-preserving and the parity corpus verifies it for
free.)

So `StrategicPlayer._space_expected_vp` adds the premium, and four new
weights price the abilities in VP at par:

| box | weight | maintainer's price | ability |
| ---: | --- | ---: | --- |
| 2 | `space_ability_2` | 1.0 | two attempts per turn |
| 4 | `space_ability_4` | 1.0 | opponent's headline revealed first |
| 6 | `space_ability_6` | 1.5 | discard a held card each turn |
| 8 | `space_ability_8` | 1.0 | an extra action round |

Two details the rules force:

- **The premium applies only when we would be first.**
  `Engine._grant_space_ability` sets the effect only `if first` and *pops*
  it when the opponent draws level, so a box they already hold grants
  nothing. Gated by a test.
- **Box 6 dominates box 8**, which is not the intuitive ordering. The
  maintainer: an extra action round forces out the card you would
  otherwise have held, and the held card is your worst -- "negative more
  than half the time". Box 6 is its near-mirror, removing that card. Box 8
  is also marked **inert** in the provenance ledger on their rate estimate
  ("once in a hundred games"): a constant reached in ~1% of games cannot
  be moved by a 192-game gate, so it is priced for correctness and must
  not be tuned against results.

## What this interacts with

`space_value`'s flat `0.4 * ops_value(ops)` charge assumes the Ops given
up were worth having. The maintainer's hand-planner note says the Space
Race takes one of your two *worst* cards, whose Ops are worth negative --
so the real comparison is far more favourable than the code's. The zero-VP
boxes sat on top of that, and together they are why the bot spaced rarely.
Fixing the charge is the planner's job (gross per-mode values, step 2).

**This is a behaviour change and needs its own gate**, separate from the
VP curve.
