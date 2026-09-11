# One source of truth for what winning is worth

The maintainer: "all of the 'win the game' constants should either be
static or based off win probability. I guess, ideally, it's better to
just have one win probability function. But I think it might be
practically better to have the VP constant. At the very least, the VP
constant should calibrate what the win probability is."

There are currently **four** of them and no two agree:

| Constant | Value | Where |
| --- | --- | --- |
| `LOSS` | −1,000,000 | the certain-outcome sentinel |
| `GAME_SWING_VP` | 40 | `game_value`, the whole VP track |
| `EUROPE_CONTROL_VP` | 20 | `region_vp`'s stand-in |
| the win-probability ceiling | 0.75–0.90 | not implemented |

They are supposed to be the same fact seen from different angles: what it
is worth to convert this position into a certain win. The directive is
that they be made consistent -- and that whichever is chosen as primary
calibrates the others, rather than each being tuned where it sits.
