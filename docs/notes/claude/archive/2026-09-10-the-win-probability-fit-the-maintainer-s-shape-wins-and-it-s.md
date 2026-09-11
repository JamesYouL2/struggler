# The win-probability fit: the maintainer's shape wins, and it saturates

936 rows from 60 self-played games, one per turn start per seat, labelled
with the eventual result (`scripts/collect_winprob.py`). The maintainer's
proposed shape was "VP difference plus board VP position times a
turn-based factor".

**The data has signal, and it is not just banked VP.** Win rate by banked
VP runs smoothly from 0.11 at −12 to 0.93 at +12. But among *near-level*
positions (|VP| ≤ 3, n=410) the board splits them 0.37 / 0.48 / 0.73 —
so board value predicts independently, which is what makes the term worth
having at all.

**And the proposed shape beats both the simpler and the more general
alternative:**

| Model | logloss | accuracy |
| --- | ---: | ---: |
| vp only | 0.5844 | 0.663 |
| vp + board | 0.5204 | 0.721 |
| **vp + board x turn/10** | **0.4976** | **0.746** |
| vp + board + turn | 0.5195 | 0.728 |

`logit(p) = -0.077 + 0.158*vp + 0.510*(board_vp * turn/10)`

Turn as a *multiplier on the board term* beats turn as its own feature,
which is the non-obvious part and is exactly what was specified: the
board matters more as the game shortens, rather than the turn mattering
on its own.

**The ceiling warning is confirmed, empirically and on the first try.**
The most confident prediction this model makes on its own training data
is **0.999**. The maintainer's ceiling is 0.75 to 0.90 -- "you cannot
force a win" -- and a term fed 0.999 inverts: the bot would stop taking
DEFCON and Europe Control shots exactly where a strong player judges the
position not yet safe. `stakes.clipped_win_probability` was written
before this fit existed, on their word alone, and it is the only thing
between the fitted model and that failure.

Caveats worth keeping with the number. These are 60 bot-versus-bot games,
so the label is "did this bot beat this bot", not "would a strong player
win"; the fit is on training data with no held-out split; and the
`board_vp` feature is measured against `vp_value`, which the section
above establishes is anchored to the best Coup on the board and therefore
moves. All three push the same way: the coefficients are a starting
shape, not a calibration.
