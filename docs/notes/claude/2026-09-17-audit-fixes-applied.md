# 2026-09-17 — The correctness/speed audit's F1–F5, applied

What was done with `docs/notes/codex/2026-09-17-correctness-speed-audit.md`.
Every finding in it was independently reproduced at `d541db2` before being
touched; every fix has a test that fails with the fix reverted. The audit's
own reproductions were accurate in mechanism throughout, and in exact
numbers wherever I could rebuild the fixture.

## What was applied

| | Finding | Fix | Gate |
| --- | --- | --- | --- |
| F1 | Yuri and Samantha's event writes `turn_effects`; the engine's coup resolution and the bot's `coup` read `game_effects` | both consumers read the turn dict | `test_yuri_and_samantha_scores_ussr_on_us_coups` (driven through the real event now), `..._can_end_the_game_on_the_coup_it_scores`, and the static scan `test_no_effect_is_read_from_the_dict_that_does_not_hold_it` |
| F2 | The Southeast Asia one-shot took bucket 1 *and* bucket 3 | a one-shot has no recycled share at all | `test_a_one_shot_never_accumulates_more_than_one_lifetime_play`, `test_a_held_one_shot_fires_this_turn_and_never_again` |
| F3 | The exhausting deal was dropped from `cycle_deal_masses` and only its recycled half priced | the deal is in the cycle walk at mass 1 (the engine empties the pile before reshuffling), and bucket 3 is conditioned on the card being in the recycle (`exhausting_deal_share`) | `test_a_card_in_the_pile_is_certainly_dealt_by_the_deal_that_empties_it`, `test_a_discarded_card_still_takes_the_whole_recycled_walk`, two rewritten walk tests |
| F4 | Next-turn replies kept this turn's roll modifiers | one `policy.reply_context(obs, when)` behind legality, modifiers and VP consequences; the raw valuation keeps the live observation | `test_an_expiring_roll_modifier_reaches_this_turn_and_not_the_next` (SALT and Death Squads, each in a region where it bites) |
| F5 | `scoring_potential` raised under Formosan, ignored `side`, omitted the SEA term | flags not overrides; sign for the seat asked about; `_potential_total` summed from `_region_term` + `_sea_term` instead of re-deriving them | three wrapper-level tests in `test_board_potential.py` |
| B | `_urgency_for` keyed on stability, which the sum stopped reading | key is (region, South East Asia) | `test_the_urgency_memo_is_keyed_on_everything_the_weight_reads` |
| C | `tier_e_minus` declared `dict`, returned a tuple | annotation corrected | `ty` |

Plus F1's reply half, which the audit asked for and which falls out of F4's
context: a same-turn US reply Coup pays us the VP, a next-turn one does not,
and `_may_coup` refuses an answer that would hand us the 20th VP outright
(`_coup_loses_outright`, also applied to our own `coup`).

## What the corpus says about each

385 records, rebuilt per record. **Measured before overwriting anything**:

- **Everything in `policy.py` together — F1's consumer, F4's reply context,
  F5, and the urgency memo key — moves zero records.** Not one value, not
  one order. That is three separate facts: the memo-key change is exactly
  behaviour-preserving (a far stronger check than the argument for it); F5
  really is off the ranking path; and **F4 has no corpus coverage at all** --
  no captured position has SALT or Death Squads live with a next-turn reply,
  so the new unit tests are the only thing holding it.
- **The schedule fixes (F2 + F3) move 257 of 385 records (66.8%)**, 76 of
  them (19.7%) changing the chosen order, largest key move 60.3 at seed
  4003 turn 5 headline. That is the live urgency consumer, and it is the
  whole of the delta.

The corpus was recaptured for the new masses; the count is in the recapture
commit. Nothing else about the capture changed.

## What was NOT done, and why

- **Speed A, the exact conditional-payout coefficients.** The algebra is
  right (payout is linear in the changed member's triple, so three
  coefficients replace a scan of thousands of count states) and the audit's
  2,856-states-to-three probe at 2.665e-15 is worth keeping. But it
  optimises the potential-delta path, which is **descoped** -- nothing on
  the ranking path calls it. Optimising code nothing runs, before the
  native-kernel call is made, buys nothing measurable and adds an
  invalidation surface (reach at neighbours, promoted/ignored scoring
  members, horizon, other-member features) to a path with no consumer to
  protect it. It is step 3 of the audit's own order, behind everything
  above.
- **B's second half, preparing the diagnostic masses lazily.** Measured
  rather than assumed: `prepare` is 233 us after the memo-key fix, of which
  `shaped_masses` is 77 us, and five corpus rankings call `prepare` 38 times
  — 0.52% of their 0.56 s. The change would have to touch the save/restore
  dance in `evaluate`, which is this repo's most-recurring defect class
  (shape 1, seven times). Not worth 0.5%.
- **"Carry the fixes into the frozen comparison baseline."** There is no
  baseline artifact in the tree to carry them into: `gate.sh` snapshots a
  committed revision. The actionable form is a scheduling instruction for
  whoever runs the next gate — take the post-fix revision as the baseline,
  so the arms differ only in what is being tested — not a change to make.
- **Strength gates (the audit's step 6).** Hours of wall clock and they must
  run alone. The maintainer's call. **This matters here**: F2 and F3 move
  two thirds of the corpus, so the factor-2 verdict (0.543) was measured
  against masses now known to be wrong in two places, and the next gate is
  the first honest reading of the schedule consumer.
- **The 26 ruff and 114 `ty` advisories.** The audit is explicit that 114
  diagnostics are not 114 defects. Only the `tier_e_minus` annotation was
  worth the edit, and it was made.

## One thing the audit got slightly wrong

Its F4 table gives raw 11.4147845440 and reply-adjusted -2.4799629292 /
1.0049628109. Rebuilding the fixture from its description
(`_overprotected_lebanon`, US turn 5, AR 7, `_ars_played=14`, DEFCON 2,
three points into Lebanon) reproduces the raw value to every digit but
gives -7.9828565996 without SALT and -4.6274832890 with it. The defect is
identical in mechanism and direction -- an expiring modifier changes a
next-turn answer's price -- and 3.36 raw on a term written to discourage
poking is not small. The sign flip is a property of their fixture, not of
the one described. Worth saying because "it flips the sign" is the sort of
claim that gets repeated.
