# Correction: the three prices are functions, and the bug is the fixed multipliers

The maintainer: "ops_value, vp_value and game_value (which is basically
win probability) are not fixed in this game, they are related but change
over turns / position / VP difference."

Which corrects the plan in the section above. It proposed finding a
*stable anchor* for `game_value` so that `vp_value` could be repriced
without cheapening defeat. Wrong shape: none of the three should be
stable. Each is a different function of the position, and the defect is
that the code relates them by **constant multipliers**, which forces all
three to move together when they should move independently.

What the code does today:

```
vp_value(obs)   = vp_era             * ops_value(obs, 1)
game_value(obs) = GAME_SWING_VP (40) * vp_value(obs)
```

Two fixed multipliers in a chain. So a cheap Coup appearing in Nigeria
raises `ops_value`, which raises the price of a VP, which raises what
losing the game is worth -- three unrelated facts moved by one board
change. And it is why the earlier attempt to reprice a VP failed: the
gate saw the bot stop avoiding nuclear war, because `game_value` was
chained to it.

What each should actually depend on:

| Price | What it is | Varies with |
| --- | --- | --- |
| `ops_value(n)` | what n Ops buy **here** | the board -- correctly, since it is the best use available |
| `vp_value` | what a VP is worth **here** | the turn (era) **and the VP position**: the 20th VP wins, the 19th does not, and the 6th and 7th in the Late War are Wargames |
| `game_value` | what is still at stake | the VP difference and the win probability -- `20 - vp` upward and `20 + vp` down, and nothing at all once the game is decided |

So the fix is three functions, not one anchor:

1. **`game_value` stops being `40 * vp_value`** and becomes a function of
   the VP position directly. This is the step that makes the rest safe,
   because it is what chained defeat to the coup price.
2. **`vp_value` gains the VP-position term** -- the convexity and the two
   discontinuities -- instead of being one flat rate per era.
3. **`ops_value` is left alone.** Pricing an Op at its best available use
   is right; it only looked wrong because two other things were chained
   to it.

`stakes.py` is what makes (1) expressible: `AUTO_VICTORY_VP` is a stake,
not a price, and `value_of_win_probability` already maps a probability
onto the same scale. The maintainer's "ideally it's better to just have
one win probability function" is the end state -- `game_value` *is* win
probability times what is left to play for.
