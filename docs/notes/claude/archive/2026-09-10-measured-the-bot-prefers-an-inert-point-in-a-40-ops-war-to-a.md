# Measured: the bot prefers an inert point in a 40-Ops war to an empty Battleground

The maintainer: "the bot doesn't fill empty BGs enough and also gets into
BG ops wars... assume the bot is doing something wrong if there are more
than 20 Ops in a country outside Europe/Thailand. Maybe there needs to be
a bonus for uncontrolled countries? Or will a single Ops penalty for
breaking handle that?"

Confirmed, and the mechanism is narrower than "ops wars".

**Every one of the eight most over-invested countries in the corpus is
stability 2:**

| Country | Influence | Stability |
| --- | --- | ---: |
| **Thailand** | **US 21, SU 19 — 40 points** | 2 |
| Algeria | US 13, SU 11 | 2 |
| Mexico | US 9, SU 11 | 2 |
| Egypt | US 9, SU 8 | 2 |
| Brazil | US 9, SU 8 | 2 |
| Pakistan | US 9, SU 7 | 2 |

At seed 4001 turn 9, with Thailand at US 21 / SU 19 and the USSR to move,
here is what the greedy placement ranks, by value per Op — which is what
it actually chooses on:

```
Thailand   BG  0.213 VP/Op   buys 1 pt at 2 Ops   (US 21 SU 19)   <- rank 1 of 69
Pakistan   BG  0.213 VP/Op   buys 1 pt at 2 Ops   (US  9 SU  7)
India      BG  0.197 VP/Op   buys 1 pt at 2 Ops   (US  3 SU  0)
Chile      BG  0.164 VP/Op   buys 3 pts at 1 Op   (US  0 SU  0)   <- empty
Saudi      BG  0.147 VP/Op   buys 3 pts at 1 Op   (US  0 SU  0)   <- empty
```

**The top-rated use of an Operation on the whole board is one point into
Thailand** — moving the margin from US+2 to US+1. It flips no control,
buys no reserve, crosses no tier, and the US restores it for two Ops. An
empty Battleground it could take outright ranks fourth.

**So the answer to the maintainer's question is: neither fix, quite.**

A bonus for uncontrolled countries would help by accident. A flat penalty
for breaking would help by accident. The actual defect is that
`progress` pays for movement toward a control that is not going to
arrive: at stability 2 the margin is always small relative to the
threshold, so every point looks like meaningful progress no matter how
many are already there. Nothing in the term knows that the fortieth point
in a country is not like the first.

And the engine is already charging correctly — the USSR pays **2 Ops per
point** in a US-controlled country, so Thailand costs double and *still*
wins. The economic disincentive exists and is not enough, because the
valuation overrates what it buys.

**The right term is the maintainer's own break-war observation**: the
value of a break should be discounted by the chance it survives the
opponent's reply. At US 21 / SU 19 a one-point break has essentially no
chance — the defender restores the margin for two Ops, and they will,
because the same valuation that made the bot spend there makes them
spend back. That is the feedback loop that produces forty points in a
stability-2 country, and it is why "the defender should win a huge
percentage of break wars" is the fix rather than a bonus anywhere else.
