# Finishing the VP rebuild, and deleting `battleground`

> **DONE for the country layer, 2026-09-21.** Steps 1-4 have all landed:
> `battleground`, `control` and `country_value`'s un-fitted half are
> deleted and `country_vp_scale` ships at 2.795. The arm that unblocked
> step 4 is in
> [the fresh-block note](2026-09-21-the-fresh-block-answers-the-fit.md)
> (+0.054 [+0.031, +0.078] paired against `bc5ef93`). **Step 5 -- the
> `potential` term, its 1024-seed verdict, and the sandbox gap in
> `_delta`'s contract -- is untouched and is what is left of this plan.**
> Everything below is kept as written, including the two branches that
> were not taken, because the reasoning is what made the fourth dispatch
> the right one.

2026-09-20. What is built, what is missing, and the order to do it in. The
hook itself was already described in
[the margin deletion note](2026-09-19-delete-the-region-margin.md); this is
what that note left open, plus one gap nobody has written down.

## What "deleting `battleground`" actually means

Two different things share the name, and only one of them goes.

- **`w.battleground` / `w.control`** -- the two guessed weights that say a
  battleground is worth 5.0 and a plain country 1.5. **These are the
  deletion target.**
- **`t.battleground[i]` / `info.battleground`** -- the board fact that a
  country is a Battleground. That is a rule. It stays forever, and
  `defcon.py` alone reads it five times to answer "can the opponent Coup a
  Battleground and lower DEFCON". Nothing about the VP rebuild touches it.

The weights have exactly **two readers in the whole bot**:

    evaluator.py:354   importance()  -- the live one, the un-fitted branch
    policy.py:1686     StrategicBot.importance(info)  -- no callers in src

The second is **dead**. Nothing in `src/` calls it; it is kept alive by one
line of `tests/test_strategic.py` (line 406) asserting
`bot.importance(Malaysia) == bot.weights.control`. It is a second copy of a
rule that the live path states differently, which is bug shape "a rule
written down twice" waiting to happen -- it just has not happened yet
because nobody calls it. **Delete it and its assertion first**, on its own,
before any of the rest: it is free, it cannot change a value, and the parity
corpus proves that.

That leaves one reader, and it is a three-line branch:

```python
def importance(t, w, urgency, i, s=None):
    if w.country_vp_scale and s is not None:
        return w.country_vp_scale * fitted_importance(t, urgency, i, s)
    return (w.battleground if t.battleground[i] else w.control) * urgency[i]
```

plus the `country_value` / `_fitted_country_value` pair, which are two
implementations of the same four terms. **Deleting `battleground` is
deleting the un-fitted half of both.** The code is ready; it is one
`if` in each place. Nothing else in the bot changes, because everything
downstream multiplies `imp`.

## Found while doing step 1: `access` was never on the fitted scale

`country_value` has four terms that multiply a country's importance --
control, progress, the reserve, and `access` -- and
`_fitted_country_value`'s docstring calls them "the same four terms". Three
of them were on the fit. `access` was not.

    evaluator.access(...)  ->  importance_fn(t, w, urgency, n)     # no side

`importance`'s fitted branch is guarded on `s is not None`, so a call
without a side takes the tier path **whatever `country_vp_scale` says**.
Measured on seed 4000's opening board, the fit at the matched 2.795:

| | fit off | fit on |
| --- | ---: | ---: |
| `importance(Italy)` | 5.000 | **7.136** |
| `access(Italy)` | 1.3963 | **1.3963** |

`access` did not move at all. So the fitted arm was running **two scales
inside one `country_value`**: control, progress and the reserve in fitted
VP, and the battlegrounds `access` reaches still on the guessed tiers, with
`w.access` (1.5) multiplying the stale half. That is bug shape 6, and
`access` is [the tiebreaker](2026-09-12-access-is-the-tiebreaker.md) -- the
term that decides rankings when the rest are close.

**This is a candidate explanation for the intransitivity**, and it is why
the arms should not have been dispatched as they stood: they would have
re-measured the same mis-scaled bot and produced another -0.031 to explain.
It is a candidate, not the answer -- a mis-scaled tiebreaker is the right
*shape* for a diffuse loss that changed 548 of 1024 seeds, but only the
rerun says whether it is the size.

The fix threads `s` through (`access` already has it: it is the side whose
access is being priced). **With the scale at 0 the argument changes
nothing**, which the parity corpus confirms unchanged -- so the shipped bot
is untouched and only the fitted arm moves. After it, `access(Italy)` reads
2.4783 with the fit on.

Gated by `test_the_fit_owns_the_whole_country_layer_and_the_guessed_tiers_are_not_read`,
which states the property the deletion in step 4 actually needs: **with the
fit on, moving `battleground` and `control` must move nothing.** Verified to
fail without the fix (971.22 against an expected 43.10).

(That test is now `test_the_guessed_tiers_are_gone_and_cannot_come_back`, in
the same file. Step 4 made its property unstateable -- there are no tier
weights left to move -- so what it asserts is the deletion itself: the
fields are absent and no strategic module reads them.)

## So what is stopping it: one measurement, not any code

`country_vp_scale` ships at **0.0**, and the reason is the only thing
between here and the deletion:

- vs the guessed tiers, head to head: the fit **wins**, 0.518 [0.502,
  0.534], 1024 seeds.
- vs `07d553a`, paired on the same 1024 seeds: the fit **loses**, -0.031
  [-0.053, -0.009], all of it in the USSR seat.

You cannot delete the fallback while the replacement loses to a bot from a
week earlier. That is the whole blocker. The arms are registered and
unrun: **`fit-intransitive-base` / `fit-intransitive-on`**, 62000-63023,
against `07d553a`, paired -- a block the fit was neither fitted nor tested
on, on a bot that has since gained ~0.10.

Two outcomes, two different next steps:

- **It still loses.** Then the fitted weights are wrong, not mis-scaled
  (half and double were both already measured worse). The suspect is named
  in the file itself: `source_revision` is `598e4d1`, so the weights were
  fitted on self-play positions from a bot **two structural changes ago**
  -- before the region margin was deleted and before `vp_swing` 3.0.
  Weights fitted on the positions one bot reaches need not price the
  positions another reaches. The next move is a **refit** at current main,
  not another scale sweep.
- **It reads level or better.** Then run it against `bc5ef93` too -- the
  strongest anchor, and the one HEAD is only level with -- and if that
  holds, the deletion is a normal change with an anchored arm behind it.

## The gap nobody has written down: the sandbox does not price the potential

This is the one that makes "the VP rebuild" unfinished as a *design*, not
just unproven as a *setting*.

`_delta`'s docstring states the contract the whole evaluator rests on:

> a sequence of placements sums to the difference of its end points
> whatever order it is taken in, and **an event that makes the same change
> (priced by `_resolve_sandbox`) is worth the same**.

With `potential` on, that second half is false. The placement path runs
`delta` -> `_with_potential` -> `potential_delta`. The event path
(`_resolve_sandbox`, policy.py:2460) values the resulting board as

```python
after  = sum(country_value(...))          # per country
after += region_potential(...)            # per region
result = after - before
```

and never calls `potential_delta` or `scoring_potential`. So **a placement
into Angola and an event that places the same influence in Angola are
priced on different scoring halves.** PR #24 names this as a known gap; it
is worth being explicit that it is a *correctness* gap in the contract,
not a rough edge. Every event in the game is mispriced relative to every
placement, by exactly the term being added.

Note that the *fitted weights* have no such gap: `_resolve_sandbox` calls
`ev.country_value`, which branches on `country_vp_scale` internally, so the
fitted path is already consistent across placement and event. **The gap is
specific to `potential`.** That is a good reason to finish the fitted
weights first and the potential second, independent of cost.

Closing it means `_resolve_sandbox` adding the potential of the after-board
minus the before-board. The pieces exist -- `scoring_potential` is the
whole-board total and is already what `value` adds -- so it is a
before/after pair around the block above, not new machinery. What it is not
is free: the sandbox runs a forked engine per die face, and the potential's
tables are the expensive thing in the profile.

## The other two things `potential` still needs

1. **A verdict.** Its arm came back **+0.021 [-0.009, +0.052]** over 512
   seeds (run 35531902621): not measured to help, not measured not to. 512
   is half the registry's own stated default for "a question worth asking".
   At 1024 the interval roughly halves and would separate +0.021 from zero
   if it is real. One dispatch on a fresh block decides whether the term is
   worth the rest of this list.
2. **An answer on the refresh approximation.** `potential_refresh` rebuilds
   the linear tables once per action round instead of once per position --
   a named approximation that deliberately reads a table built on another
   board. Priced both ways: identical on 52-65% of deltas, p99 0.26 VP at
   turn 1, **max 3.73 VP at turn 1**. The shape is right (a round's
   staleness is how much influence moved during it) but a 3.7 VP error at
   turn 1 is a whole battleground. If the arm disappoints, the note's own
   suggestion is to refresh on *drift* rather than on the clock -- which
   would also shrink the sandbox problem above, since a sandbox fork moves
   the board a lot.

## The order

1. **Delete `StrategicBot.importance` and its assertion.** Free, cannot
   move a value, proved by the corpus. Do it regardless of everything
   below. **DONE.**
1b. **Thread the side through `access`** so the fit owns all four terms,
   with the property test above. Free with the scale at 0, corpus
   unchanged. **DONE, and it was not in this plan when the plan was
   written** -- see the section above. It has to land *before* step 2, or
   step 2 measures a bot with two scales in it.
2. **Run `fit-intransitive-{base,on}`** (registered, 62000-63023, 16
   shards), on the fixed bot. This is the gate on the whole programme.
   **DONE:** +0.038, which read level-or-better, so step 3 followed.
3. **If it loses: refit at current main** and re-run step 2. If it reads
   level or better: **run it against `bc5ef93`** before believing it.
   **DONE, and it took two blocks.** Block 64000 read +0.023 [-0.001,
   +0.047] and was held back on the pre-registered rule; block 68000 read
   **+0.054 [+0.031, +0.078]** and cleared it (run 35614516089). The
   refit branch was therefore NOT taken -- see the fresh-block note for
   why the -0.001 was the block rather than the weights.
4. **Delete the un-fitted branch** -- `importance`'s fallback,
   `country_value`'s un-fitted half, and the `battleground` / `control`
   fields -- with the anchored arm from step 3 as the evidence, *before*
   the merge, not after. **DONE 2026-09-21**, on a branch cut from the
   exact tree the arm played. `_fitted_country_value` is folded back into
   `country_value`, `importance` takes a mandatory side, and the parity
   corpus was re-captured because its records pinned a code path that no
   longer exists.
5. **Only then, the potential.** 1024-seed verdict first; if it earns its
   place, close the sandbox gap as part of turning it on, not after.
   **NOT DONE. This is the whole of what is left.**

Steps 1-4 are the VP rebuild for the *country* layer, which is the one
`battleground` lives in. Step 5 is the *region* layer, which is a separate
question and should not hold the deletion hostage: the fitted weights are
what replaces `battleground`, and `potential` is an additional term on top
of `region_potential`, not a substitute for the tiers.

## What could go wrong, stated in advance

- **The fit and the region term are not independent.** Removing the region
  term from under the fitted weights costs 0.067 -- far more than the
  fitted weights are themselves worth. So a deletion arm must hold the
  region term fixed, and "the fit replaces the region term too" is a
  separate hypothesis that the 2026-09-18 measurement already argues
  against.
- **`matched_scale` is a level, not a shape.** 2.795 exists to keep
  importance's overall level where the tiers had it, so an arm at that
  value tests the shape. If the shape is right and the level is wrong, that
  shows up as a scale sweep -- and half and double were both already
  measured worse, which is evidence the level is not the problem.
- **The deletion is one-way in a way the others were not.** The region
  margin could be deleted because it was measured inert. `battleground` is
  not inert; it is the current pricing. Deleting it while the replacement
  is unproven would not be a simplification, it would be shipping an
  unmeasured bot.
