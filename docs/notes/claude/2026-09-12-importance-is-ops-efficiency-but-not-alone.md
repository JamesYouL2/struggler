# Importance is a function of Ops efficiency, and that alone makes the bot worse

The maintainer: *"Not only does ops efficiency (2 or 1 stab country) matter
for ops efficiency, it matters for importance... importance is a function of
ops efficiency."*

That is right about the direction and, tried on its own, it is a net
regression. Both halves are worth recording, because the reason it fails is
the other half of the fix.

## What `importance` does today

    importance(i) = (battleground if bg else control) * urgency[i]

No stability term. `access` divides by stability and `country_value`'s
progress term uses `margin / stability`, so Ops cost appears around the tier
value but never in it. A stability-2 battleground and a stability-4
battleground are worth the same to the term that prices control.

## Measured against the maintainer's own ranking

`models/expert_valuations.json` carries `placement_rank` -- which country a
seat should put its first Op into on the opening board -- and the gate scores
the bot against it every run. Dividing the tier value by `stability ** k`:

| k | US inversions | USSR inversions | total |
| ---: | ---: | ---: | ---: |
| 0 (shipped) | 5 | 7 | **12** |
| 0.25 | 7 | 6 | 13 |
| 0.5 | 9 | 5 | 14 |
| 0.75 | 9 | 5 | 14 |
| 1.0 | 10 | 5 | **15** |

**The USSR side improves monotonically, 7 -> 5, and the US side degrades
faster, 5 -> 10.** Every positive exponent is a net loss. The insight is
doing real work on one seat and being swamped on the other.

## Why the US side breaks, and what it implies

The expert's US order begins:

| rank | country | stability | region |
| ---: | --- | ---: | --- |
| 1 | **France** | **3** | **EUROPE** |
| 2 | Pakistan | 2 | ASIA |
| 3 | Egypt | 2 | MIDDLE_EAST |

**The first pick is the MORE expensive country.** France at stability 3
ranks above two stability-2 battlegrounds, so on the US side the expert is
not maximising Ops efficiency at all -- and dividing by stability pushes
France down, which is exactly the inversion that appears.

France is European. It ranks first despite costing more *because Europe is
most important*, which is the maintainer's other stated target and one the
model does not currently meet (Europe ranks 3rd of 6).

So the two are coupled:

- **Ops efficiency alone** sinks France and costs five US inversions.
- **Europe's weight alone** would lift France but leave the USSR side, where
  Israel at stability 4 still ranks first against an expert who puts it last.

Neither lands on its own. A fix has to carry both, and the joint version is
the thing to try -- not another exponent.

## The measurement to keep

12 total inversions, 5 US and 7 USSR, at the shipped weights on seed 4000's
opening board. The gate prints it every run. Any change to `importance` is
answerable against that number in seconds, which is why this whole
investigation cost no games at all.

One caution on it: `placement_rank` is defined on ONE opening board, so a
change tuned to drive this to zero is overfitting to a single position. It
is a sharp signal for direction and a poor one for a final value.
