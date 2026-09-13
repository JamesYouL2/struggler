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

    importance(i) = swing(i) * [ p_this_turn(i)
                               + (rest_of_cycle(i) + later(i)) * retention(i) ]

    swing(i) = direct(i) + tier(i)

VP PER SWING, SPLIT BY WHEN IT ARRIVES, on the maintainer's call -- and
"immediate" means THIS TURN, not this cycle. Measured over corpus positions:

| when | value | share |
| --- | ---: | ---: |
| this turn | 0.187 | **15.8%** |
| rest of this cycle | 0.359 | 30% |
| later cycles | 0.637 | 54% |

Only a sixth of a country's scoring value arrives this turn. A first attempt
put it at 54% by taking `scoring_schedule`'s `turns == 0` as immediate --
that is THIS CYCLE, and it fuses buckets 1 and 2 exactly as
`2026-09-12-value-times-probability-times-discount.md` warned. The two are
separable because SCORING CARDS CANNOT BE HELD past end of turn, so a card
in either hand fires now: `p_this_turn` is `p_opponent_holds` if they might
hold it, and **close to 1, not 1**, if we do.

Not 1, because four cards take a scoring card out of a hand without it
scoring for its holder:

| card | who picks | how |
| --- | --- | --- |
| Five Year Plan | chance | USSR randomly discards; a scoring card so discarded does not fire |
| Terrorism | chance | opponent randomly discards, twice after Iranian Hostage Crisis |
| Ask Not | the holder | the US may VOLUNTARILY discard one, per FAQ 5.0 |
| Aldrich Ames Remix | the OPPONENT | USSR sees the US hand and names the card the US must discard |

Aldrich Ames is the maintainer's second point and the sharpest of the four,
because it is the only one where *the side that loses by the card scoring*
chooses what goes. The other three are chance or self-inflicted; this one is
aimed. `events.py` offers `tuple(us_hand)` unfiltered and the handler files
the pick with `fired=False`, so a scoring card in the US hand is a legal and
usually correct target. It is also one-sided and late: USSR, 3 Ops, Late War,
so only a US-held scoring card is exposed to it, and only after the Late War
deck is in.

Ask Not is the maintainer's point and is a deliberate play rather than an
accident. `events.py` includes scoring cards in its choices on purpose,
quoting FAQ 5.0 -- *"The illegal act would be holding the scoring card. If a
player can find a way to force himself to discard a scoring card, he is free
to do so"* -- and records that dumping one which would score for the opponent
is among the strongest things the card does.

`cards.json` said the opposite ("non-scoring hand cards") and that summary is
fed to the LLM bot's prompt, so the bot was being told it could not make the
card's best play. Corrected.

Grain Sales is the near miss and belongs in a different term: the card still
scores, but the OPPONENT plays it.

So `p_this_turn` for a card we hold is one minus the chance one of those
four fires on it this turn. Small, and worth carrying rather than rounding
away, because the cards that break it are exactly the ones a strong player
aims at a scoring card on purpose.

**This is where retention belongs, and only here.** If the region scores this
turn you hold it now and no flip risk applies; everything else must survive
to be scored. So retention discounts 84% of the value, not all of it and not
half of it. Applying it to the whole term -- tried 2026-09-12 -- over-
discounted and cost an inversion, making Israel MORE attractive rather than
less.

Still missing: retention is measured against ONE horizon, "when the region
next scores". Holding until the end of this cycle is easier than holding
until the second reshuffle, so the `rest_of_cycle` and `later` buckets want
different retention curves. That is the same measurement with the horizon as
a parameter, not a new one.

### The two terms of `swing`

Two terms, and the split is the point: they answer different questions and
only one of them is about being a battleground.

    direct(i) = 2 * ( 1.0 if bg(i)                  [10.1.2, per battleground]
                    + 0.5 if adj to enemy SP )      [10.1.2, one-sided, hence half]

    tier(i)   = 2 * tier_share(i)                   [threshold contribution]

`direct` is what the country pays by existing under your control. `tier` is
what its control does to the presence/domination/control thresholds, and
EVERY country has it -- a non-battleground earns no 10.1.2 VP at all, so its
whole worth is `tier`.

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

### The non-battleground ratio: measured, and it disagrees

The maintainer: *"Non bgs scaling to being worth a lot less than bgs seems
weird... it should be worth at most a 1/3rd of equivalent bg, preferably
less than a quarter. We should test/measure that, not fake it."*

Measured by difference through `region_vp` -- for every country, the
two-sided swing from *they hold it* to *we hold it* -- over 60 corpus
positions:

| kind | mean swing | n |
| --- | ---: | ---: |
| battleground | **4.425** | 1740 |
| non-battleground | **2.057** | 3300 |

    measured ratio  0.465
    shipped         0.300   (control 1.5 / battleground 5.0)
    target          <= 0.333, preferably < 0.250

**The two-term split makes this exact rather than a preference.** The
measurement decomposes almost perfectly:

    non-bg swing  2.057  =  tier alone (no 10.1.2 VP to earn)
    bg swing      4.425  =  tier + direct
    difference    2.368

and rule 10.1.2's 1 VP per battleground is 2.000 two-sided -- so 2.368 is the
direct award plus 0.368 for a battleground ALSO gating domination and
control. The rules account for the gap between the two kinds of country to
within a third of a VP.

Which means the ratio is DERIVED, not set:

    non-bg : bg  =  tier / (tier + direct)

    at the measured direct of 2.37  ->  0.465
    to reach 0.333                  ->  direct must be 4.12   (1.7x the rules)
    to reach 0.250                  ->  direct must be 6.17   (2.6x the rules)

So the maintainer's target is the claim that **a battleground is worth about
two to three times its printed scoring value**, and that is not obviously
wrong: a battleground also gates control outright, absorbs coups, and is what
wars and events aim at, none of which is scoring VP. It is now a single
number with a single meaning -- a multiplier on `direct` -- which is
sweepable against the inversion count and gateable, where "non-bgs feel
underweighted" was neither.

**The rules value non-battlegrounds HIGHER than either the shipped weight or
the target.** That is a real disagreement and this plan does not average it
away. Three candidate explanations, and they are distinguishable:

1. **The measure is incomplete.** It captures the scoring swing and nothing
   else. It does not capture that CONTROL requires every battleground -- a
   gate no non-battleground can satisfy at any count -- nor that
   battlegrounds are what get couped and contested. Flipping each country in
   isolation assumes a freedom of choice the game does not give.
2. **Controllability belongs inside it**, the maintainer's reading: how
   easily a battleground can be taken is part of what makes it important.
   The per-stability split is suggestive and not clean -- battleground swing
   runs 3.16 / 4.27 / 5.19 across stability 1-3 and then falls to 3.50 at 4,
   which may be composition rather than signal (n=180 there).
3. **The rules-swing is simply the wrong quantity** for what `importance`
   should carry, and 0.30 is right for reasons this measure cannot see.

Breaking the tie is a measurement, not a decision: score the swing again
holding CONTROL of the region fixed as a requirement, so the all-battlegrounds
gate is counted. If the ratio falls under 0.333 that settles it in favour of
(1); if it does not, (2) and (3) remain and the ratio wants a strength
measurement rather than a derivation.

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
