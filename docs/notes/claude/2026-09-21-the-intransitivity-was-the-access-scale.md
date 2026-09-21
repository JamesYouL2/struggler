# RETRACTED: the intransitivity was NOT the access scale leak

> **Correction, 2026-09-21, run 35550341433.** This note's title claim is
> **wrong**. The isolation arm it proposed has now run, and the access scale
> leak costs **nothing measurable**:
>
> | arm | vs `07d553a` | US | USSR |
> | --- | ---: | ---: | ---: |
> | `leak-iso-buggy` (leak present) | 0.569 [0.552, 0.586] | 0.632 | 0.505 |
> | `leak-iso-fixed` (leak fixed) | 0.558 [0.541, 0.575] | 0.603 | 0.513 |
>
> **Paired: +0.011 [-0.007, +0.029] over 1024 seeds** -- the *buggy* bot
> reads a hair better, and the interval contains zero. The prediction
> written down before the run was "near -0.069 and the leak explains the
> whole flip; near zero and the flip was the block or the bot". It came back
> near zero. **The flip was the block or the bot, not the leak.**
>
> What survives: the `+0.038` reading below is a clean paired measurement
> and still stands. The access fix is still a correct fix -- two scales
> inside one `country_value` is a defect whatever it costs -- and it is free
> (its gate was a dead heat). What does **not** survive is this note's
> causal story, and the sentence below claiming the 2026-09-18 `-0.031`
> "was an artifact" of the leak.
>
> See [the correction note](2026-09-21-the-leak-cost-nothing.md).
> The filename is left alone because
> `.github/experiments.json` cites it by path.

2026-09-21. Run 35545821069, `fit-intransitive-base` / `fit-intransitive-on`,
1024 seeds each (62000-63023) against `07d553a`, paired, 16 shards, none
stalled. Step 2 of
[the VP rebuild plan](2026-09-20-finishing-the-vp-rebuild.md), measured on
the bot with [the access scale leak fixed](2026-09-20-finishing-the-vp-rebuild.md).

| arm | score | one-sided 95% | US seat | USSR seat | signed VP | nuked US/USSR |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `base` (fit off, as shipped) | 0.537 | [0.520, 0.554] | 0.601 | 0.474 | -0.59 | 23/35 |
| `on` (`country_vp_scale` 2.795) | **0.575** | [0.558, 0.592] | 0.634 | 0.517 | -0.77 | 21/24 |

**Paired: +0.038 [+0.015, +0.061] over 1024 seeds.** The lower bound clears
zero, so this is a measurable gain, not a level reading.

## The sign flip

The same switch, against the same anchor, measured twice:

| | reading | block | bot |
| --- | ---: | --- | --- |
| 2026-09-18, before the fix | **-0.031** [-0.053, -0.009] | 30000-31023 | main @ 2026-09-18 |
| 2026-09-21, after the fix | **+0.038** [+0.015, +0.061] | 62000-63023 | main @ `30aa9e8` |

Both intervals exclude zero, in opposite directions. The swing is 0.069 --
larger than any single change measured this week.

~~**So the `access` scale leak was not merely a candidate explanation for
the intransitivity. Fixing it turned the fitted weights from a measurable
loss into a measurable gain**, and the loss that reverted them on
2026-09-18 was an artifact of three of `country_value`'s four terms being
on fitted VP while the fourth -- the tiebreaker -- stayed on the guessed
tiers.~~

**RETRACTED.** The isolation arm says the leak is worth +0.011 [-0.007,
+0.029], i.e. nothing. The paragraph above was the inference this note
itself flagged as confounded, stated as if it were settled. It was not, and
it was wrong.

## What this reading cannot say

The two readings differ in three ways at once: the fix, the seed block, and
about 0.10 of bot strength gained in between (the region-margin deletion,
`vp_swing` 3.0, the hand safety). **The 0.069 swing is therefore not a
clean measurement of what the leak cost.** It is confounded, and honestly
so.

Isolating the leak takes a third arm: the fit on *with* the leak
reintroduced, on one block and one bot, paired. **Registered and dispatched**
as `leak-iso-fixed` / `leak-iso-buggy` (66000-67023 against `07d553a`), the
buggy arm being `exp/access-leak-isolation` by `bot_ref` -- current main
with exactly two changes, the fix reverted and `country_vp_scale` defaulted
to 2.795, because `experiments.yml` forbids `bot_ref` with `weights`.

**A local probe first**, over the 401-record parity corpus ranked with the
fit on under both revisions:

| | |
| --- | ---: |
| rankings the leak changes | **52 (13.0%)** |
| top actions it changes | **6 (1.5%)** |

So the leak bites on a minority of decisions. That is enough to be worth
measuring in games and not enough to call 0.069 attributed without doing
so -- the corpus ranks one decision per record and cannot see compounding,
which is exactly the limit the
[sandbox note](2026-09-20-the-stall-is-the-drain.md) records. If the paired
arm comes back near -0.069 the leak explains the whole flip; near zero and
the flip was the block or the bot, and the intransitivity claim needs
different evidence again.

What *is* clean is the reading itself: +0.038 [+0.015, +0.061], one block,
one bot, paired seed by seed, with the fix in both arms' base.

## The seat split, read against the baseline

The italy/austria self-play baseline is US 0.621 / USSR 0.379, so seat
scores are read against that
([why](2026-09-20-since-v0.2.1.md)):

| seat | base | on | change |
| --- | ---: | ---: | ---: |
| US | 0.601 | 0.634 | **+0.033** |
| USSR | 0.474 | 0.517 | **+0.043** |

**Both seats gain, and the USSR gains more.** That matters because the
2026-09-18 loss was *entirely* in the USSR seat -- the seat that was being
hurt is now the seat that benefits most, which is the pattern a fixed
mis-scaling would produce and a genuinely bad weight set would not.

The USSR seat's nuclear losses also fall, 35 to 24 of 512. Not asked for,
not gated, and worth watching rather than claiming: one reading.

## What it selects

The plan's two branches were "it still loses -> refit" and "it reads level
or better -> take it to `bc5ef93`". This is the second branch, more
strongly than the branch anticipated.

**Next: the same pair against `bc5ef93`**, the strongest anchor and the one
HEAD is only level with. `07d553a` sits *inside* the regression this
project spent two days bisecting, so beating it is the weaker of the two
tests -- exactly the trap
[the since-v0.2.1 note](2026-09-20-since-v0.2.1.md) names as explanation
(1) for why individually-positive features have not summed. A gain that
does not survive `bc5ef93` is a gain against a weakened opponent.

Registered as `fit-bc-base` / `fit-bc-on` on a fresh block (64000-65023).

Only if that holds does step 4 -- deleting `battleground`, `control` and
the un-fitted half of `country_value` -- become a normal change with an
anchored arm behind it. The property test
`test_the_fit_owns_the_whole_country_layer_and_the_guessed_tiers_are_not_read`
is already in place and is what makes that deletion checkable.

## The lesson worth keeping (which also did not survive)

A term was added to the value function, measured, found wanting, and
reverted -- and the measurement was right about the numbers and wrong about
the cause. What it actually measured was **a bug in the wiring of the thing
being tested**, not the thing being tested.

~~The 2026-09-18 note called the -0.031 "the clearest statement this repo
has that beating the current bot is not the objective function". That
reading now has a simpler explanation available.~~

**RETRACTED.** The simpler explanation was tested and is false. The
2026-09-18 `-0.031` does **not** have a known cause, so the claim it was
used to support is neither confirmed nor refuted -- it is back to being an
open question, on weaker evidence than either this note or the 2026-09-18
one asserted.

The lesson that does survive is smaller and about method, not about
`access`: **this note stated an inference it had itself labelled
confounded, in its own title.** The isolation arm was already registered
and dispatched when the title was written. Waiting one run would have cost
nothing.
