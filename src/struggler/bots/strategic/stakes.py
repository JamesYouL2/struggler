"""What winning and losing are worth: one parameter, everything else derived.

The bot had **four** numbers for the same fact and no two agreed --
`LOSS` at a million, `GAME_SWING_VP` at 40, `region_vp`'s Europe Control
stand-in at 100, and an unimplemented win-probability ceiling. They are one
quantity seen from different angles: what it is worth to turn this position
into a certain win. Tuned separately, they drift, and three of the four had
no recorded derivation at all.

So there is one parameter here, `AUTO_VICTORY_VP`, and the rest are
expressions in it. The maintainer's instruction was explicit that having a
single parameter matters more than its exact value ("I think it probably
doesn't matter too much"), and the measurement agrees: over all 547 corpus
positions from both seats, the distance to auto-victory averages **20.0 VP**
with a median of 20, in every slice -- overall, and among the positions
holding three or four European Battlegrounds where Control is actually in
reach. Anything in the maintainer's 20-to-40 range is defensible; 20 is
where the board actually sits.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# THE parameter.
# ---------------------------------------------------------------------------
# Half the VP track. The game ends the instant the track reaches +/-20, so
# this is what converting a position *at par* into a certain win is worth,
# and `20 - vp` is what it is worth from anywhere else.
AUTO_VICTORY_VP = 20.0

# ---------------------------------------------------------------------------
# Derived. Change `AUTO_VICTORY_VP` and these follow.
# ---------------------------------------------------------------------------

# The whole -20..+20 track: certain defeat to certain victory. What
# `game_value` prices, and the bound `priced()` clamps a certain outcome to.
#
# It is deliberately symmetric and therefore an overstatement: the swing
# actually reachable from VP `v` is `AUTO_VICTORY_VP - v` upward and
# `AUTO_VICTORY_VP + v` downward, equal only at par. Making it directional
# is a change with a wide blast radius -- every sentinel bound depends on it
# -- and wants its own gate. See docs/CLAUDE_NOTES.md, "The game is not worth
# 40 VP from where you are standing".
GAME_SWING_VP = 2 * AUTO_VICTORY_VP

# How much more than the arithmetic swing a defeat must be priced at for
# the bot to avoid it. **Measured, and the measurement was a surprise.**
#
# `game_value` was a flat `2 * AUTO_VICTORY_VP` (40) from every position.
# Replacing it with the honest reachable swing -- 20 at par, since you fall
# from 0 to -20 rather than 40 -- was REJECTED by the gate on nuclear
# losses: 21 against the 16 allowed, pooled score 0.464. The same failure
# had killed an earlier reprice at 0.434 with 13.
#
# Twice is a result, not an accident: pricing defeat at its arithmetic
# value leaves this bot too willing to risk it. Whether that is a flaw in
# the bot or a real feature of the game -- a loss costs you the rest of the
# match, not just the VP -- is open, but the number is not arbitrary any
# more, and it is separated from the swing so that the swing can stay
# honest.
RISK_PREMIUM = 2.0

# What `evaluator.region_vp` returns for Europe Control, a tier the rules
# give no scoring value because it simply wins.
#
# It stood at an arbitrary 100. Note that the number is not what makes
# Europe Control cheap today: it is multiplied by `w.region * urgency /
# vp_value` ~ 0.027, so it reads as 0.5 VP of board value here and read as
# 2.7 at 100. A terminal outcome priced as a very large scoring is the
# defect; the constant is only the part that can be made honest cheaply.
EUROPE_CONTROL_VP = AUTO_VICTORY_VP


def value_of_win_probability(p: float) -> float:
    """A win probability as VP above par -- the calibration link the
    maintainer asked for between the VP constant and the win-probability
    function, so that the two cannot drift apart.

    Certain victory is `AUTO_VICTORY_VP` above par and certain defeat the
    same below, so an even position is worth nothing and the map between
    them is linear in `p`."""
    return (2.0 * p - 1.0) * AUTO_VICTORY_VP


# How confident a win-probability estimator is allowed to be. The
# maintainer: you cannot force a win, so even a dominant board at the start
# of a turn is 0.75 to 0.90, and lower as the USSR "because USSR has to die
# more". A model fitted to outcomes alone will happily report 0.99 and
# invert the term it feeds -- the whole point of knowing you are behind is
# to start taking DEFCON and Europe Control shots. So this is a constraint
# on the output, not something the data teaches.
#
# The USSR asymmetry is NOT yet measured: `defcon_1` endings split 8 to 5
# over a 192-game hunt, which is thirteen events. It is a per-seat constant
# and the mirror gate cannot see those, so it stays symmetric until measured.
WIN_PROBABILITY_CEILING = 0.90
WIN_PROBABILITY_FLOOR = 1.0 - WIN_PROBABILITY_CEILING


def clipped_win_probability(p: float) -> float:
    """`p` held inside the ceiling. Always use this on an estimator's output."""
    return min(WIN_PROBABILITY_CEILING, max(WIN_PROBABILITY_FLOOR, p))
