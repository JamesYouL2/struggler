# The poke count: the forward search does not yet work in play

The maintainer's test, and a far sharper instrument than the gate or the
control percentage: **how often does the bot break a Battleground with
the minimum two-Op placement?** Their expectation is about once a game.

Measured over 8 games:

| | search off | search on |
| --- | ---: | ---: |
| Battleground breaks per game | 24.50 | 24.12 |
| **...minimum 2-Op pokes** | **13.75** | **13.25** |
| ...committed, 3+ points | 1.62 | 0.50 |

**Fourteen times the expected rate, and the forward search barely moves
it.** Fifty-six per cent of every break the bot makes is the minimum
poke, which the `n : n-1` table says is its worst available version --
2 Ops spent, 1 Op to undo.

That is a much better measurement than either of the ones I reached for
first. The gate says 0.488 +/- 0.035, which is "not a measurable
regression". Turn-8 control says 78% to 82%, on populations of different
size. The poke count says 13.75 to 13.25, which is **nothing**, and says
it from 8 games.

**And the mechanism is not broken, which is the puzzling part.** On a
clean fixture -- Italy at US 2 / SU 0, the USSR placing one point -- the
reply discounts the gain by **70.7%**, from 2.99 VP to 0.88. It works
exactly as designed there.

In real games it fires on **7.2%** of calls and discounts **11.2%** when
it fires. So the gap is not that the discount is too small where it
applies; it is that it applies almost nowhere. The guard is "control
changes hands", and in play the overwhelming majority of candidate
placements do not change control -- but the *chosen* ones evidently
still are pokes, which means the pokes being chosen are somehow not the
ones being discounted.

Unresolved, and I would rather say so than guess again: three
explanations have suggested themselves tonight and two were wrong, so
the next step is to instrument which placements are actually chosen and
whether each was discounted, rather than reason about it.

**The instrument is the lasting result here.** A behavioural count with
a maintainer-supplied expectation -- "about one a game" -- caught in 8
games what a 96-seed gate and a 16-game control sweep both missed. It
belongs in the suite.
