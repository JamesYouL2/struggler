# Why the bot buys exactly one point: `_investment` keeps the smallest tie

The full placement ranking at seed 4001 T9, USSR to move, by value per Op
-- which is what the greedy chooses on:

```
 1 Thailand  0.213  1 pt @2  THEIRS  US 21 SU 19   needs 2 more to flip
 2 Pakistan  0.213  1 pt @2  THEIRS  US  9 SU  7   needs 4 more
 3 India     0.197  1 pt @2  THEIRS  US  3 SU  0   needs 6 more
 4 Japan     0.176  1 pt @2  THEIRS  US  4 SU  0   needs 8 more
 5 Cuba      0.176  1 pt @2  THEIRS  US  3 SU  0   needs 6 more
 6 Chile     0.164  3 pts@1  EMPTY                 takes it outright
 7 Saudi     0.147  3 pts@1  EMPTY                 takes it outright
```

The top five are **one-point buys into opponent Battlegrounds**, and one
of them puts a single point into Japan where the USSR needs eight. The
maintainer's rule is "4-Op breaks into stability-2 countries are a thing,
but you have to spend all your Ops, because otherwise you make it too
easy for the opponent". The bot spends the minimum, which is the one
amount that is strictly worse than not breaking at all.

**The mechanism is in `_investment`:**

```python
gain = self.delta(obs, cid, own=points) / spent    # value PER OP
if gain > best[0]:                                  # strict: ties keep the FIRST
    best = (gain, points)
```

It maximises value per Op, and `progress_curve` is 1.0, so progress
toward control is **linear**: `delta` and `spent` both grow linearly and
the ratio is flat across point counts. A flat rate plus a strict `>`
means **the smallest investment wins every tie.**

In an *empty* country the rate is not flat -- control is a step, so the
rate jumps at the threshold and the greedy buys all three. In a
*contested* one there is no reachable step, the rate is flat, and it buys
one. So the bot fully invests exactly where investment is cheap and
safe, and token-invests exactly where the maintainer says you must commit
or stay out. Precisely inverted.

**Two candidate fixes, and they are not equivalent.**

1. `>=` instead of `>`, keeping the *largest* point count on a tie. One
   character, and it makes flat-rate investments go all-in rather than
   all-out. Cheap to gate, and it does nothing to the empty-country case
   where the rate is genuinely peaked.
2. The maintainer's **half-action-round forward search**: value a
   placement by the position after the opponent's cheapest reply. The
   inert Thailand point then evaluates at ~0 without any new term,
   because the reply restores the margin for two Ops. This also gets the
   all-or-nothing structure for free -- a full break survives the reply
   and a partial one does not.

(1) is a patch that happens to point the right way; (2) is the actual
model. Worth trying (1) first only because it is a one-line gate.

**And two legitimate reasons to break that neither fix should destroy**,
both from the maintainer: breaking Middle East countries as the USSR to
set up Muslim Revolution, and breaking South America to set up Latin
American Debt Crisis (rarer -- Late War, and the discard option). Those
are *instrumental* breaks whose value is in a card in hand, not in the
board. A forward search sees them only if the reply model knows the card
is coming, which it does not.
