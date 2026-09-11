# The yardstick is a coup: why the Battleground scale cannot be tuned

Trying to raise the Battleground scale to the maintainer's 4 VP produced
a result that killed the plan and then explained itself.

**Scaling `battleground` does nothing.** From 5.0 to 40.0, an eightfold
increase, the measured Battleground swing moves from 1.08 VP to 1.10.
The bot has no absolute scale: board value is denominated in Ops,
`vp_value` is `vp_era * ops_value(1)`, and `ops_value` is itself computed
from board terms -- so scaling the board scales the yardstick with it and
every ratio survives untouched.

**Only `vp_mid` moves it**, and only by redenominating: 1.0 to 0.25 puts
the swing at 4.44 VP. But the era rates are the maintainer's own rule and
the best-supported numbers in the project, so bending them to fix a
Battleground is the wrong repair.

**The actual cause is what sets the yardstick.** `ops_value` is the max
of the best placement and the best Coup, and the Coup wins at every Ops
level:

| | 1 Op | 4 Ops |
| --- | ---: | ---: |
| best placement | 0.24 VP | 1.15 VP |
| **best Coup** | **1.11 VP** (Nigeria) | **1.78 VP** (Zaire) |
| `ops_value` | 1.00 | 1.78 |

So `vp_value` -- the price of a VP, and therefore the denominator of
**every** VP figure in this project, including every measurement in these
notes -- is anchored to **the single most efficient Coup available on the
board**. At turn 4 that is Nigeria, stability 1, worth 4.6x the best
placement.

Two consequences.

**The "Battleground is 4x low" finding was measured against a coup.** The
swing reads 1.08 VP because a VP is priced at the best coup; against what
a *placement* buys it would read about 3.5, which is the maintainer's 4.
The Battleground weight may not be wrong at all. What is wrong is that
two different exchange rates are in use and nothing says which.

**And the rate is unstable.** One cheap Coup target anywhere sets the
price of an Op everywhere, for every decision. It jumps when DEFCON
changes, when a 1-stability country fills up, when a Coup prohibition
turns on. Every VP-denominated comparison moves with it -- including
`military_credit`, the China charge, `game_value`, and the sentinel
bounds.

Whether pricing an Op at its best use is right is a real question and not
obviously wrong. What is not defensible is that it is undocumented, that
the region calibration was being fitted against it without anyone
noticing, and that half the constants in `models/provenance.json` are
denominated in a unit that moves when Nigeria fills up.

**This supersedes the plan to rewrite the region weights.** The
calibration the maintainer supplied is sound; the yardstick it would have
been fitted against is not. Fixing the yardstick comes first.
