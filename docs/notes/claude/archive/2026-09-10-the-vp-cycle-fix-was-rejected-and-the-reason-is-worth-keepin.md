# The VP-cycle fix was rejected, and the reason is worth keeping

`a12d2af` priced a VP off the placement spend instead of `ops_value`,
breaking the `coup -> vp_value -> ops_value -> coup` cycle. Gate:

| Sample | Seeds | Score | Nuclear losses |
| --- | ---: | ---: | ---: |
| tuning | 32 | 0.320 | 6 |
| held out | 63 | 0.492 | 7 |
| pooled | 95 | **0.434 +/- 0.033** | **13** |

**REJECTED** -- upper bound 0.489, and thirteen nuclear losses against
nought to two in every recent gate. Reverted.

The mechanism is one line: `game_value = GAME_SWING_VP * vp_value`. The
placement-only price is *lower* than the better of a placement and a
Coup, so cheapening a VP cheapened **losing the game**, and the risk that
`safety_key` prices against it became affordable. The bot bought fatal
risk at a discount. Thirteen nuclear losses is not a side effect of the
change, it is the change.

Two things to take from it.

**The cycle is load-bearing.** It is not an accident to be tidied away:
the VP price is the numeraire for risk as well as for value, and any
change to it moves how much the bot will pay to avoid dying. A future
attempt has to hold `game_value` fixed while breaking the cycle -- for
instance by pricing the *risk* numeraire separately from the *value* one
-- rather than redefining what an Op is worth.

**The order-independence test is scoped by this.** It re-establishes the
VP price first, as `rank_actions` does, so it asserts what production
guarantees. Asked genuinely cold the values still differ, and that is now
a known, deliberate limitation with a gate result behind it rather than
an oversight. Recorded in the module docstring.

A cheaper reading: I found a real inconsistency, fixed it in the obvious
direction, and the obvious direction cost 0.07 and a nuclear loss every
seven games. The parity corpus said 8 positions changed their action and
the expert table said nothing changed at all. **Neither instrument could
see this; only the games could.**
