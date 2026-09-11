# Europe Control is priced as a scoring, not a win -- and the U-shape is already there

Measuring what the next European Battleground is worth, by how many the
US already holds (seed 4002, turn 4):

| Already held | Next one is worth |
| ---: | ---: |
| **0 of 5** | **2.30 VP** |
| 1 of 5 | 0.95 VP |
| 2 of 5 | 1.05 VP |
| 3 of 5 | 0.90 VP |
| **4 of 5** | **2.24 VP** |

The maintainer, independently: "the 0th BG and 5th BG in Europe are the
most important countries on the map, unless you need to gamble on DEFCON
or are looking to force 20 VP before Europe scoring comes back."

**So the bot already has the right shape and the wrong magnitude.** The
U is there -- the first and the last are worth twice the middle -- which
is more than the region model deserves credit for, and it comes out of
the tier structure rather than from anything anyone tuned. What is wrong
is that the fifth one *wins the game* and is priced at 2.24 VP.

The arithmetic of why:

```
region_vp returns 100 for Europe Control
  x w.region 1.3  x urgency 1.752  /  vp_value 83.8   =   2.7 VP
```

**Which is why capping the constant, as the maintainer asked, is right but
cannot help on its own -- and alone makes it worse.** 100 was arbitrary
and 20 is the honest value at par (`20 - vp`, up to 40 from behind), so
the constant is now `EUROPE_CONTROL_VP = 20.0` and named. But at 20 the
same arithmetic gives 0.5 VP for winning the game, against 2.7 before.
The parity corpus reproduces every ranking unchanged after the switch,
which confirms the point: **no position in 547 ever reaches the branch.**

The defect is the routing, not the number. Europe Control is a *terminal
outcome* and it is priced as a very large *scoring*, so it is discounted
by `urgency` (how soon the region will score -- irrelevant to a win) and
by `w.region` (a scoring weight). It belongs on `game_value`'s scale,
where `LOSS` and the certain outcomes already live.

**A correction to withdraw.** Before measuring, this looked like the
region term being ~37x under-scaled, and that was wrong. A full Africa
swing pays 22 VP by the rules and moves the bot's board value by 9.1 VP:
the bot sees **41%**, not 3%. `country_value` and the margin terms carry
most of the weight, and the region term is one contributor among three.
