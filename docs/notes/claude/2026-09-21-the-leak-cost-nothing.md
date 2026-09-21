# The access scale leak cost nothing, and the prediction was wrong

2026-09-21. Run 35550341433, `leak-iso-fixed` / `leak-iso-buggy`, 1024 seeds
each (66000-67023) against `07d553a`, paired, 16 shards, none stalled.

| arm | score | one-sided 95% | US seat | USSR seat | signed VP | nuked US/USSR |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `leak-iso-buggy` (leak present) | 0.569 | [0.552, 0.586] | 0.632 | 0.505 | -0.91 | 24/25 |
| `leak-iso-fixed` (leak fixed) | 0.558 | [0.541, 0.575] | 0.603 | 0.513 | -1.64 | 25/21 |

**Paired: +0.011 [-0.007, +0.029].** The arm carrying the bug reads a hair
*better*, and the interval contains zero.

**The leak is worth nothing measurable.**

## The prediction, and that it failed

Written down before the run, deliberately, so the reading could not be
rationalised afterwards:

> near -0.069 and the leak explains the whole flip; near zero and the flip
> was the block or the bot, and the intransitivity claim needs different
> evidence again.

It came back at +0.011. **The second branch.** The
[preceding note](2026-09-21-the-intransitivity-was-the-access-scale.md) is
retracted in place: its title, its headline paragraph and its closing
"lesson" all asserted that the access scale leak explained the fitted
weights' -0.031 -> +0.038 sign flip. It does not.

The local corpus probe had already warned about this and was not weighted
heavily enough: the leak changed 52 of 401 rankings (13.0%) but only **6
top actions (1.5%)**. A defect that changes the chosen move once in
sixty-seven is not obviously worth 0.069 of strength, and now it measures
as worth nothing.

## What actually survives

- **The `+0.038` for the fitted weights stands.** It is a clean paired
  reading on one block against one opponent with one bot
  (run 35545821069). Nothing here touches it.
- **The access fix stays.** Three of `country_value`'s four terms on fitted
  VP and the fourth on guessed tiers is a defect whatever it costs; the
  property test that gates it states what step 4's deletion needs. And it
  is free: its gate was a dead heat, 150 games, signed VP 0.0.
- **`test_the_fit_owns_the_whole_country_layer_and_the_guessed_tiers_are_not_read`
  stays**, for the same reason.

What does not survive is the *causal story*, and with it the idea that the
2026-09-18 `-0.031` has been explained.

## So what did cause the flip?

Unknown, and it should be left unknown rather than re-guessed. The two
readings differ in three ways; one has now been eliminated:

| candidate | status |
| --- | --- |
| the access scale leak | **eliminated**, +0.011 [-0.007, +0.029] |
| the seed block (30000-31023 vs 62000-63023) | open |
| ~0.10 of bot strength gained in between | open |

The block is the more suspicious of the two survivors, but the evidence
for it is weaker than this note first said, and the correction matters
because it was the load-bearing claim.

**What was claimed:** three independent demonstrations that a level against
a fixed anchor moves 0.02-0.03 between blocks -- 0.534 against 0.559 from
[the status note's section 2](2026-09-20-status-and-what-to-run-next.md),
and `leak-iso-fixed` at 0.558 against `fit-intransitive-on`'s 0.575.

**What the arithmetic says.** Read the SE off the published halfwidths
rather than assuming one: these arms print +/-0.017 at the one-sided 95%,
and 0.017 / 1.645 is **SE 0.0103** per level. (A coin-flip model would say
0.0156; the benchmark's score counts a draw as a half and is tighter than
that.) The difference of two independent levels then has SE about 0.0146.
The two gaps are 0.025 and 0.017: **1.7 and 1.2 standard errors.** Those
are ordinary sampling error. They are consistent with blocks mattering and
equally consistent with blocks not mattering at all, and calling them
demonstrations was reading a pattern into noise -- in a note whose subject
is exactly that failure.

What survives is narrower and still enough for the conclusion here: a
-0.031 and a +0.038 measured on different blocks against different bots
**have not been shown to require a third mechanism**, because nothing has
been shown about blocks either way. That is weaker than "no third mechanism
is required" and it is what the data supports. Settling it needs a design
built for it: the same bot, the same anchor, two blocks, enough seeds that
0.02 would be visible -- which is not any arm that has run.

## What this costs the wider claim

The 2026-09-18 fitted-weights note and the status note both cite the
`-0.031` as this repo's clearest evidence that *beating the current bot is
not the objective function*. That citation is now on weaker ground than
either note or the retracted one claimed:

- It is **not** explained away as a defect (the retracted note's claim).
- It is **not** established as a strategic fact either, because a single
  cross-block level difference of that size is within what this repo has
  now three times measured blocks to do on their own.

**Intransitivity remains worth watching and is no longer evidenced here.**
Demonstrating it needs a design that blocks cannot fake: the same two bots,
the same block, against two different anchors, all paired. That arm does
not exist.

## The method lesson, which is the real finding

The isolation arm was already registered and dispatched when the retracted
note's title was written. The note even contained the sentence "the 0.069
swing is confounded and is not a clean measurement of what the leak cost"
-- and was titled *The intransitivity was the access scale leak*.

**Stating a confounded inference in a title, one run before the
disambiguating measurement lands, is the error.** It cost nothing here
because the arm was already running; the failure mode is when nobody runs
it and the title becomes the thing everyone cites.

The practice that worked, and should be kept: **write the prediction down
before the run, in a form that can fail.** It failed, and that was legible
within a minute of the pooled table appearing rather than being argued
about.
