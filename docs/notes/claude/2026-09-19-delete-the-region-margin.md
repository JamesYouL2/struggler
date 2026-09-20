# Deleting the region margin, and what else the model can lose

2026-09-19. The maintainer's question: what simplifies the model the most,
which variables can go, and what is the easiest way to hook the VP
valuation work to the bot. This note answers all three, and carries out
the first deletion.

## The three layers of the value function

`board_value` had three summands. After this change it has two, and both
are denominated in something:

| summand | unit | how it is set |
| --- | --- | --- |
| `country_value` over every country | country importance (a battleground's control value) | guessed tiers 5.0 / 1.5, or the fitted per-country VP weights with `country_vp_scale` |
| `region_potential` over every region | VP, weighted by when the region scores | the tiers the rules pay |
| ~~region margin~~ | neither | fitted to `expert_valuations.json`, deleted here |

That is why the margin was the right thing to delete first: besides being
measured inert, it was the only term that could not be stated in VP or in
importance, so it stood between the value function and being entirely
VP-denominated.

## The evidence

Run 35306328917, arm `margin-off`, 1024 seeds (20000-21023), paired seed
by seed against the same bot with the margin on, both against `07d553a`:
**+0.001 [-0.022, +0.024]**. Every other ablation in that sweep was a
measurable loss (Coup replies -0.059, the reply look-ahead -0.056, access
-0.038, rival urgency -0.025); this one was the only deletion candidate
the sweep produced, and the note that recorded it said so.

Deleted rather than set to zero. A weight at zero is a code path nobody
runs, and `bug-shapes.md` shape 5 is about exactly those.

## What went

- Four weights: `margin_presence`, `margin_battleground`, `margin_country`,
  `margin_live` (30 -> 26), and their four provenance entries (two guesses,
  two gate-bounded).
- About 105 lines of `evaluator.py`: `_contribution`, `_bg_total`, `_unit`,
  `_credit`, `margin_basis`, `margin_swapped`.
- `StrategicPlayer.region_margin`, `region_margin_after`, `_margin_basis`,
  and the `_base_margins` per-decision cache with its three reset sites.
- The margin summand on all three pricing paths (`board_value`, `delta`,
  the event sandbox), and the `margins` member of the event basis.

## The corpus delta, measured before overwriting it

Against the committed corpus, with the four weights stripped from each
record: **38 of 478 top actions change, 178 of 478 rankings reorder
somewhere.** Deleting a value term moves values, so the corpus is
recaptured on the same seeds (4000-4003) in the following commit. The
number is recorded here because the baseline rule is to measure the delta
before overwriting the baseline, not to discover it afterwards.

## What else can go, in order

1. **Reply-budget model 2 (the median) and `access_contested`.** Both are
   dead as shipped and neither can change a value: model 2 is unreferenced
   and is model 3 with the distribution thrown away, and `access_contested`
   is a multiplier at 0.0, so the branch it guards contributes nothing.
   **Done, in the follow-up branch `simplify/dead-value-paths`**, and proved
   by the parity corpus reproducing every recorded value unchanged.
2. **NOT reply model 1 or `reply_ops`, on inspection.** The 2026-09-19 arms
   condemned a flat budget of 4 as a *default*
   ([note](2026-09-19-reply-budget-best-card.md)), but model 1 is how
   `test_reply_lookahead.py` pins a deterministic budget. Deleting it would
   cost more test machinery than it saves code.
3. **NOT `retention_p`, on inspection.** It has no caller, but `RETENTION_P`
   is a measured table (1103-3573 observations per stability), not a
   guessed weight. It costs nothing at runtime and deleting it would throw
   away a measurement. Dormant data is not model complexity.
4. **`europe_curve` (0.0).** Measured 0.486 at k=10, leaning worse. Kept for
   now: it is the hook for a curve in every region, which fits the small
   regions better (Central America 0.62 -> 0.72).
5. **The `fit_*` switches** on `exp/fitted-variance`: do not merge them.
   `fit_shrink` was measured the worst of five.

The pattern in 2 and 3: **a switch with a live caller is not dead code, and
a measurement is not a weight.** What is worth deleting is a term the bot
evaluates on every board.

Each needs the same treatment as this one: an anchored arm against
`07d553a` **before** the merge, not after ([memory](../../../CLAUDE.md),
and PR #6's lesson).

## Hooking the VP valuation to the bot: it is one weight

The fitted per-country, per-side VP weights are already wired through the
one function that sets a country's tier:

    importance(t, w, urgency, i, s)
      -> w.country_vp_scale * fitted_importance(...)   when the scale is set
      -> (w.battleground if battleground else w.control) * urgency[i]   otherwise

Everything downstream multiplies `imp` -- progress toward control, the
reserve, and both access terms -- so setting `country_vp_scale` converts
the whole country layer at once, and `matched_scale` 2.795 keeps its total
at the tiers' level. No other call site changes. That is the cheap hook,
and it is built.

What it lacks is a verdict: the same switch read -0.031 against 07d553a on
one 1024-seed block and +0.021 on another
([note](2026-09-18-fitted-country-weights.md)). Before it goes on it needs
one block it was not fitted or tested on, with the base held fixed.

The exact version -- per-position linear weights from
`forecast.tier_weights`, which reproduce the DP to 1e-15 -- is the same hook
one layer deeper, and costs an estimated 8 s a game
([note](2026-09-18-the-potential-as-per-position-linear-weights.md)). It is
worth wiring only if the fixed weights prove out first, because it prices
the same thing more expensively.
