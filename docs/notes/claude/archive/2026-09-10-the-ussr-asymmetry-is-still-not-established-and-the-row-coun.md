# The USSR asymmetry is still not established, and the row counts lied

Tested against the win-probability data, because it was the one part of
the ceiling the maintainer gave that had no measurement behind it.

The row-level split looks decisive: **US 0.579, USSR 0.421** over 936
rows, and at near-level positions 0.718 against 0.390. It is an artifact.
Rows are one per turn per seat and every row of a game carries that
game's outcome, so they are perfectly correlated within a game and the
count weights by game length rather than by evidence.

**Game-level: the US seat won 33 of 60, 55%, two-sided p = 0.52.**
Nothing. Resolving a genuine 58/42 split at p < 0.05 needs roughly 150
games. So the asymmetry stays out of `stakes.py`, where
`WIN_PROBABILITY_CEILING` remains symmetric, and stays listed as
unmeasured in `models/provenance.json`.

This is the third time this session that a promising number has come
from counting correlated observations as if they were independent -- the
first was "96% pool efficiency" from summing wall-clock across workers,
the second the turn-10 worst card at −8.55 from a ten-sample mean with
one −78 outlier. Same shape each time: **the denominator was not what it
looked like.**

What the data *does* support is the ceiling's magnitude. The best
populated buckets top out at 0.90 for the US and 0.82 for the USSR,
against the maintainer's stated 0.75 to 0.90 -- consistent, with the same
correlation caveat attached.
