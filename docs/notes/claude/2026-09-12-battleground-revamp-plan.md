# The battleground revamp: every formula, current and target

Written 2026-09-12 after a day of measurement. Nothing here is shipped; the
retention work sits uncommitted in the tree. The point of writing the
formulas out is that three separate half-changes measured WORSE today, and
each time the missing half was visible only once both were written down.

## 1. What the code computes today

**Tier value.** A two-valued step function, times how much the region will
still score:

    importance(i) = (battleground if bg(i) else control) * urgency(i)
                  = (5.0 if bg(i) else 1.5) * urgency(i)

**Urgency**, the scoring schedule, summed over the scoring cards that count
`i`'s region and the turns each can still score at:

    urgency(i) = SUM over cards c counting region(i)
                   SUM over turns k in scoring_schedule(c)
                     scoring_discount ** k * (scoring_hand if held and k == 0 else 1)
               = SUM ...  0.8 ** k * (1.2 if held and k == 0 else 1)

**Country value**, the whole per-country term:

    country_value(i) = importance(i) * control_sign(i)
                     + progress * importance(i) * |margin/stability| ** progress_curve
                     - wipe_risk(i, ours) + wipe_risk(i, theirs)
                     + reserve * importance(i) * guard_band(i)
                     + first_mover * importance(i) / stability(i)      [contested bg only]
                     + access_weight * (access(i, us) - access(i, them))

    control_sign(i) = +1 if margin >= stability, -1 if margin <= -stability, else 0

**Reach**, summed over every adjacent battleground we do not control:

    access(i, s) = SUM over adjacent battlegrounds n, control(n) != s
                     access_decay ** (1 - k(n)) * contested_factor(n)
                       * importance(n) / stability(n)

    k(n) = routes into n: this holding, plus occupied neighbours, plus the
           superpower where n is home-adjacent, plus standing influence in n
    contested_factor(n) = access_contested (0.25) if they reach n else 1

**Board value:**

    board_value = SUM over countries country_value(i)
                + region * SUM over regions region_vp(region)
                + SUM over regions margin_basis(region)

## 2. What is measured, and what is still a guess

| quantity | value | basis |
| --- | ---: | --- |
| `access_decay` | 1.445 | **measured**, 1/(1-p), p=0.308 over 698 obs |
| retention by stability | 1 - 0.454 ** stab | **measured**, 587 obs |
| retention, contested penalty | 0.06-0.08 | **measured**, 255 obs at stability 2-3 |
| `battleground` / `control` | 5.0 / 1.5 | guess; the RATIO is deliberate |
| `region` | 1.3 | guess, scaling an exactly-known VP |
| `access` (master) | 1.5 | guess |
| `access_contested` | 0.25 | guess |
| `progress`, `reserve`, `first_mover` | 2.8 / ? / 0.6 | guess |
| `EUROPE_CONTROL_VP` | 40 | derived, = GAME_SWING_VP |

## 3. The target formulas

The frame is `value x probability x turn_discount`, summed over battlegrounds
and future scorings (`2026-09-12-value-times-probability-times-discount.md`).
Applied to the tier value:

    importance(i) = vp_per_scoring(i) * retention(i) * urgency(i)

**vp_per_scoring(i)** -- from the RULES, not a constant, and **DOUBLE-SIDED
throughout**: what matters is the swing from *they hold it* to *we hold it*,
not what we gain from nobody holding it. `region_vp` already computes
`Board.score_region` exactly, and its per-country term is rule 10.1.2.

    vp_per_scoring(i) = 2 * ( 1.0 if bg(i)
                            + 0.5 if i adjacent to enemy SP
                            + tier_share(i) )

**Why the battleground term is 1.0 and adjacency is 0.5.** 10.1.2 pays 1 VP
per controlled battleground and 1 VP per controlled country adjacent to the
enemy superpower, so at first glance they are equal. They are not, because
**no country on the board is adjacent to both superpowers** (checked: US-side
Canada, Japan, Mexico, Cuba; USSR-side Finland, Poland, Romania, Afghanistan,
North Korea, Turkey; intersection empty).

So a battleground pays whichever side holds it -- flipping it is a two-sided
swing of 2 VP -- while an adjacency VP can only ever be earned by one side,
a swing of 1. Half a battleground, in the same units. The outer `2 *` carries
the two-sidedness and the 0.5 corrects the one term that is not.

### tier_share(i), broken down

Not one quantity. Region scoring is three thresholds, and control of `i`
moves different ones depending on where the region stands:

    tier_share(i) = SUM over tiers T of  step(T) * P(i decides T)

with the steps being the VP actually gained by crossing each threshold, not
the tier's face value:

    step(presence)    = presence_vp                 [from nothing to presence]
    step(domination)  = domination_vp - presence_vp
    step(control)     = control_vp - domination_vp

and `P(i decides T)` the chance control of `i` is what puts the region over
that threshold. Holding `i` changes four counts:

    our countries  += 1        their countries -= 1 if they held it
    our bgs        += 1 if bg  their bgs       -= 1 if bg and they held it

which feed the three conditions `region_vp` already encodes:

    presence:    our_count > 0
    domination:  our_count > their_count AND our_bgs > their_bgs
                 AND our_count > our_bgs           [10.1.1: at least one non-bg]
    control:     our_bgs == total_bgs AND our_count > their_count

**So a battleground's tier_share is large only where a threshold is live.**
The same country is worth a lot in a region one country from domination and
almost nothing in a region already lost -- which is the discrimination the
flat 5.0 cannot express, and the reason Iraq and Israel currently score
identically.

`P(i decides T)` is computable by difference rather than modelled: evaluate
`region_vp` with `i` held and without, over the region as it stands. Two
evaluations per country, and `margin_basis` already walks the region for the
partial-credit term, so the counts are in hand.

Note what this makes of `region`, the 1.3 multiplier: it is scaling an
exactly-known VP quantity and should be 1.0. And note the 10.1.1 clause --
domination needs at least one NON-battleground -- which is a place where a
non-battleground can carry a whole tier on its own, and nothing in the
current model can say so.

**retention(i)** -- measured:

    retention(i) = 1 - flip_per_stability ** stability(i)      [0.454]
                   ... times a contested penalty, ~0.93, where they reach it

**urgency(i)** unchanged in form, but see the five-bucket rework: its terms
should each carry a probability, which they do not today.

And `region` at par (1.0), since `region_vp` is an exact VP quantity being
scaled by a guess.

## 4. What none of this explains, and must not be hand-waved

**The USSR ranking.** The maintainer's order is

    Iraq > Lebanon > South_Korea > Saudi_Arabia > Israel

and the bot's is nearly reversed (7 of 10 pairs). Israel is the case, and
the recorded reason is *"Israel is bad for the USSR because the US takes
Egypt first"*.

None of the formulas above produce that:

- **Not the tier value**: both are battlegrounds, both currently 9.31.
- **Not retention**: Israel at stability 4 retains 0.871 contested, Iraq at 3
  retains 0.882. Indistinguishable, and the stability term makes Israel
  *more* attractive, not less.
- **Not access as computed**: the bot already scores Iraq 4.27 against
  Israel 1.16 -- it SEES that Iraq opens more -- and ranks Israel first
  anyway.

The last point looked like the lead: access is computed correctly, and
`access_weight` is 1.5 against a tier value of 9.31, so a 3.7x access
advantage might be swamped by terms that treat the two countries as equal.

**Probed, and false.** Sweeping `access` against the inversion count:

    access  1.5  ->  12   (shipped)
            3.0  ->  13
            5.0  ->  13
            8.0  ->  13
           20.0  ->  14

Raising it makes the ranking WORSE, monotonically, and the USSR side goes
7 -> 8. Access is not being swamped. Thirty seconds to find out, which is the
argument for writing probes down as steps rather than carrying them as
plausible stories.

**So Israel is still unexplained**, and that is the honest state of this
plan. Every term examined so far -- tier value, retention, contest, access
weight -- fails to separate a country the maintainer ranks first from one
they rank last. The next probe is not another weight: it is a full
decomposition of `delta(Israel)` against `delta(Iraq)` from the USSR seat,
term by term, to find which one carries the 15.67-against-11.28 gap. Until
that is known, any revamp is being designed against a symptom nobody has
located.

## 5. Order, and the rule that governs it

**One change, one corpus re-capture, one gate.** Three half-changes measured
worse today -- a stability exponent without Europe's weight, retention
without contest, `scoring_discount` alone. Each time the measurement was
right and the conclusion would have been wrong. Land the whole thing.

1. **Decompose `delta(Israel)` vs `delta(Iraq)` from the USSR seat**, term by
   term. Seconds, free, and nothing should be designed until it is known
   which term carries the gap. (The `access` sweep that stood here was run
   and falsified -- see above.)
2. **Define `tier_share` by difference** through `region_vp`, and put
   `region` at par.
3. **Apply retention with the contested penalty.**
4. **Europe.** Not solved by EUROPE_CONTROL_VP (measured inert): Europe and
   Asia share 3/7 tiers and Asia's control of 9 is reachable. If Europe
   should lead, something must say so that is not a tier value.
5. **Re-capture the corpus, gate once**, against the revision before step 1.

## 6. How it is judged

**Fast signal, free:** the expert inversion count, printed by the gate every
run. Today: 5 US, 7 USSR, 12 total. Any change is answerable in seconds.

**Caveat, load-bearing:** `placement_rank` is ONE opening board. Driving it
to zero is overfitting to a single position; it is a sharp signal for
direction and a poor one for a final value.

**Arbiter:** a gate against the pre-revamp revision, 128 seeds on CI. And a
drift run against `05b6690` -- the strongest measured revision -- since that
is the bar, not HEAD.
