# The 2x was the 10.1.2 bonuses, and Southeast Asia is the third exception

**The open factor of two is closed.** The maintainer:
"uncontested/uncontrolled is 2 Ops per VP, it's just that in mid war
everything is contested." Splitting the tier value from the 10.1.2
bonuses settles it:

| Region | BG Ops | tier VP | with bonuses | Ops/VP tier | Ops/VP with |
| --- | ---: | ---: | ---: | ---: | ---: |
| Middle East | 16 | 7 | 13 | 2.29 | 1.23 |
| Europe | 15 | 7 | 13 | 2.14 | 1.15 |
| Asia | 17 | 9 | 16 | 1.89 | 1.06 |
| South America | 9 | 6 | 10 | 1.50 | 0.90 |
| Central America | 7 | 5 | 8 | 1.40 | 0.88 |
| Africa | 8 | 6 | 11 | 1.33 | 0.73 |
| **mean** | | | | **1.76** | **0.99** |

**1.76 Ops per VP on the tier alone -- the maintainer's 2 -- and 0.99
with the bonuses, which is what the earlier fit measured.** Neither
number was wrong; they are different quantities. And the split is worth
knowing on its own: **about half the VP a region pays comes from the +1
per Battleground Controlled and +1 per country adjacent to the enemy
superpower, not from the tier.** Europe Control is 7 tier and 6 bonus.

The remaining gap to what a real game costs is contest, as they say:
uncontested is 2 Ops per VP, mid war is dearer because everything is
fought over, and the bot's era rates already encode the progression --
`vp_early 0.5, vp_mid 1.0, vp_late 2.0`.

**And Southeast Asia Scoring is a third exception, not a second.** It
has no tiers at all: `+2 VP for Control of Thailand, +1 VP per other
controlled Southeast Asian country`.

| Country | Stability | VP | Ops/VP |
| --- | ---: | ---: | ---: |
| Laos/Cambodia | 1 | 1 | **1.0** |
| Vietnam | 1 | 1 | **1.0** |
| Indonesia | 1 | 1 | **1.0** |
| Thailand | 2 | 2 | **1.0** |
| Burma, Malaysia, Philippines | 2 | 1 | 2.0 |
| **all seven** | **11** | **8** | **1.38** |

So four Southeast Asian countries pay **1 Op per VP** against a map
average of 1.76, and three of the four are not Battlegrounds. That
breaks two of the rules the region table rests on at once: "ignore
country count outside Asia" is false here, and a non-Battleground with
real VP value exists nowhere else on the board.

**The three exceptions, then, and all three are arithmetic rather than
judgement:**

1. **Thailand** -- the only Battleground scored by two cards, and worth 2
   on one of them.
2. **Europe** -- the only Control that is a win condition, worth `20 - vp`.
3. **Southeast Asia Scoring** -- the only card that pays per country with
   no tiers, making three 1-stability non-Battlegrounds the most
   Ops-efficient VP on the map.

Everything else sits on one line within 18%.
