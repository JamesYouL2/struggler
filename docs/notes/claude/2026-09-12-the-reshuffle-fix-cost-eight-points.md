# The reshuffle fix was correct and cost eight points

A four-anchor drift bisect, run as one parallel CI matrix, localised a
regression to a single commit -- and it is not the one anyone suspected.

## The reading

`drift_check.sh` reports HEAD's score against the anchor, so **lower means
the anchor is stronger**. 128 seeds, 256 games each, same seeds for every
anchor.

| # | anchor | what it is | HEAD scores | verdict |
| ---: | --- | --- | ---: | --- |
| 4 | `26bddbe` | before the opening book change | 0.467 +/-0.047 | pass |
| 5 | `3955b3e` | **book -> 4/3/3, made default** | **0.422** +/-0.042 | **DRIFT** |
| 7 | `05b6690` | before the reshuffle fix | **0.422** +/-0.042 | **DRIFT** |
| 8 | `9b90ef0` | **the reshuffle estimate fix** | 0.504 +/-0.045 | pass |

Two steps, and the flat stretch between them is what makes it a bisect
rather than a guess: `3955b3e` and `05b6690` read *identically* at 0.422,
so nothing in the two commits between them moved strength at all.

## The opening book was an improvement

0.467 -> 0.422 across `3955b3e` means the anchor got HARDER: the 4/3/3 book
is worth about 4.5 points over West-Germany-to-5. The standing hypothesis --
that replacing the book caused the v0.2.0 drift reading -- was exactly
backwards, and is retired.

## The reshuffle fix is the regression

0.422 -> 0.504 across `9b90ef0` means the anchor got WEAKER by about 8
points, and it is isolated to that commit.

`9b90ef0` is *"fix(bots): the reshuffle estimate ignored the cards that join
the deck"* -- the commit that corrected `ENTERING` from 46 to 49 Mid War
cards. **That fix is right.** `test_entering_matches_what_the_engine_adds`
plays a game and checks the constant against the engine's own log line; the
old value was three cards short per period, and the docstring carrying the
stale 46 was corrected this morning (e384ba7).

So a correct model is measurably weaker than the wrong one it replaced,
which is the interesting part and not a reason to revert.

### THE HYPOTHESIS BELOW WAS TESTED AND FAILED

`scoring_discount 0.93` -- the value derived below as restoring the
pre-regression turn-3 urgency -- measured **0.428 +/-0.075 over 76 seeds**
against the shipped 0.8. It is worse, not better. With `0.55` having measured
0.463 +/-0.064 earlier the same day, BOTH directions from 0.8 are worse and
0.8 is a local optimum.

So the 8 points are real and isolated, and the discount is not the parameter
that recovers them. The reasoning below is left standing because the
arithmetic in it is correct and the conclusion drawn from it was not: turn-3
urgency really does fall 22.7%, and that really is equivalent to steepening
the discount, and restoring the urgency by shallowing the discount
nevertheless loses. Something else absorbs the horizon change.

What that implies: `scoring_discount` is not "the parameter fitted around the
old estimate". Either several are, and moving one alone is a net loss, or the
regression is not about scoring urgency at all and the 22.7% is a coincidence
of size. The next probe should hold the discount and look at what else reads
`turns_to_reshuffle`.

### The hypothesis that fits (superseded -- see above)

`turns_to_reshuffle` feeds `scoring_schedule`, which is the turn-discount
factor in every scoring card's valuation. The old estimate was *early* --
`9b90ef0`'s own note records it predicting a reshuffle at 7.5 when it came
at 9, "under-discounting the second scoring by about 1.4x". Every other
weight that touches scoring urgency was tuned while that was true:
`scoring_discount`, `scoring_hand`, `scoring_final`, the whole urgency
vector.

Correcting one input of a fitted system de-tunes the rest. The 8 points are
not the cost of being right; they are the cost of being right in one place
while the parameters fitted around the error stay where they were.

That is a specific, testable claim, and it is the same structure the
value x probability x turn_discount rebuild exists to fix -- factors 2 and 3
have been standing in for each other, so a change to one shows up as a loss
until the other is refitted.

## What this does not say

HEAD is not broken. Against `v0.1.0` HEAD scores **0.584 +/-0.046** -- two
days of work is clearly ahead of where it started. The coherent story is:
the bot improved from v0.1.0, gained again on the opening book, lost about 8
points at the reshuffle fix, and still nets out ahead. Peak measured
strength in this window was `3955b3e`-`05b6690`.

Nor does it say revert. The estimate is correct now and reverting would
trade a right model for a lucky one. What it says is that the weights fitted
around the old estimate are now fitted around nothing, and refitting them is
worth about 8 points.

## Two notes on method

**The bisect only exists because the jobs ran in parallel.** Sequentially
this is four 45-minute runs and a decision after each; as a matrix it is one
50-minute wall-clock and the whole shape arrives at once. The flat stretch
between `3955b3e` and `05b6690` -- the part that proves the isolation -- is
only visible with all four in hand.

**A duration prediction failed, and is recorded because it was offered as a
test.** The four jobs ran 44m31s to 50m56s, and the hypothesis was that
anchors lacking the reshuffle fix would run longer games and finish last.
`9b90ef0`, the one anchor WITH the fix, finished third of four. No pattern;
the spread is runner variance.
