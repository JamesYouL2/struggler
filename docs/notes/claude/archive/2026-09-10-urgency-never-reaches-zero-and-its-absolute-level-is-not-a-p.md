# Urgency never reaches zero, and its absolute level is not a parameter

Confirmed, as the maintainer expected. `_scoring_weight_uncached` ends with
`w.scoring_final * final_scoring_odds(obs)`, a floor for the end-of-game
scoring that no amount of played scoring cards can remove. Measured: the
floor is **0.75** (seed 4000, turn 9) and the turn-4 values are **1.75 to
2.95**. So it is stable across the game exactly as they said, and it never
drops to nothing.

Their suggested band was 0.5 to 1.5 and the actual is 0.75 to 2.95, but
**the absolute level is not a parameter at all**: importance is
`w.battleground * urgency`, and `w.battleground` is free, so scaling every
urgency by a constant changes nothing. Only two things about urgency are
real -- the ratio between regions, and the ratio between turns. Worth
recording before anyone "fixes" the range and finds the gate cannot see it.
