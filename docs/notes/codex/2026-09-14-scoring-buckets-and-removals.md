# 2026-09-14 — Five-bucket schedule widening + contested-zero/scoring-flat bundle

Branch: `experiment/scoring-five-bucket` (three commits: widen, removals, recapture).
Gate: ONE gate of the branch head vs `main`, `decide=0 vary=0` (dispatched, see tail).

## Why this order, and why one gate

Widen first: the widening rewrites the loop the holding bonus multiplies
inside (`StrategicPlayer._scoring_weight_uncached`), so removing
`scoring_hand` first is work redone. The widening is behaviour-preserving
by construction (buckets 1+2 at half weight sum to exactly the old
this-cycle term; bucket 3 is the old post-reshuffle term), so gating it
alone burns an hour to measure 0.500. `access_contested` lives in the
independent access term (`evaluator.access`) and rides free in the same
commit. Both removals are the already arm-tested defaults
(`access_contested` 0.0: 0.512 +/-0.043; `scoring_hand` 1.0: 0.503
+/-0.038, both 192-seed old-model dead heats), so a joint failure is
unlikely -- and splittable if it happens.

## What each commit does

- `82ae3ef` widen: new `public_cards.scoring_buckets` derived from
  `scoring_schedule` (turns==0 -> buckets 1+2, later -> bucket 3).
  Bucket 4 named, zero mass (no second-reshuffle timing yet -- factor 2's
  job); bucket 5 stays on `final_scoring_odds`. Consumer loop iterates
  buckets with identical totals: 300/300 bit-exact on a turn/card/state
  sweep, corpus green on the commit (4 passed, `logs/bucket-widen-corpus.log`).
  Pinned by `test_scoring_buckets_name_five_terms_and_reproduce_the_schedule`.
- `06e212e` removals: `access_contested` 0.25 -> 0.0, `scoring_hand`
  1.2 -> 1.0. Parameters survive as knobs (provenance values + notes
  updated, source/determination flip to gate/bounded on verdict); full code
  deletion waits for the factor rebuild. `test_contested_reach`
  (`contested < exclusive`) still holds at 0.0.
- `8b1a264` recapture: 499 records (was 472), seeds 4000-4003,
  `logs/corpus-recapture.log`.

## Assumption worth flagging

"Remove access_contested" is implemented as the arm-tested 0.0 (contested
reach prices at zero), NOT as deleting the discount (which would be 1.0 --
treating contested as exclusive -- and was never tested). If removal meant
deletion, say so and the gate re-runs against that.

## Gate (pending at time of writing)

Dispatched as run 34926032664 (base pinned to origin/main
35182ef, `decide=0 vary=0`, default 128+128 seeds). A first dispatch
(34925988205) failed in 15s on `fatal: not a valid object name: main` --
the runner checks out only the branch ref, so the base must be a SHA, not
`main`. Infra failure, not a verdict.
Verdict to be appended. On ACCEPT: full local suite, merge, then update
provenance source/determination + counts for the two weights. On REJECT:
split the bundle and re-gate each half.

## Stacked 2026-09-15: reply-coup revert (Path B)

Instead of merging the ACCEPTED bundle, the reply-coup revert stacks on
this branch and the joint state gates once. Bundle-only ACCEPT stays as
evidence; a joint REJECT isolates to the revert.

- The opponent's answer is the retake only, at the constant max Ops any
  card can carry (`reply_ops` 2.0 -> 4.0, `reply_model` 3 -> 1). Deleted:
  `_may_coup`, `_coup_reply`, the unseen-pool budget distribution
  (`_reply_budgets` collapses to the constant; the pool walk was 11% of a
  ranking). Rationale: per-placement coup pricing roughly doubled ranking
  cost; 30 minutes a suite is not worth it.
- Considered and rejected: max over the opponent's possible hand instead
  of the constant 4. Thirteen 4-Op cards means the pool max is 4 in
  virtually every position, and a single-budget reply at 4 vs 3 differs
  only for exactly-4-Op retakes -- while the test helper's budget knob
  (`budget=5` for the doubling-rule leg) stops working.
- Behavioural costs, both attributed by A/B probe, not guessed:
  (a) the ops-curve convexity at the iran probe flips to concave -- the
  old convexity was a ~4.1 flat Coup discount flattering the difference
  past the subtrahend by 0.03; `test_the_ops_curve_is_convex...` now pins
  on==off bit-identity (no phantom reply discounts) instead;
  (b) the poke off-arm falls to mean 4.5 (was 6.27) -- contested-zero
  took the cheap pokes out of the base values, so the negative control
  now loops all seeds (4001/4002 carry it).
- Test fallout fixed in the same commit: live==held pinned
  (`test_live_scoring_card...`), access trial geometry moved to
  uncontested Venezuela/Brazil, the five Coup-answer lookahead tests
  replaced by `test_no_answer_where_no_retake_can_reach`, ledger
  `reply_ops`/`reply_model` values + notes + summary counts.
- Provenance: `reply_ops` guess/inert -> guess/underdetermined (now read),
  `reply_model` gate/bounded -> guess/bounded (value 1 never gated; the
  old model-3 verdict does not cover it). Pending the joint gate below.

## Joint gate (pending at time of writing)

Recapture + full suite + one joint gate vs origin/main on the stacked
state. Verdict to be appended. On ACCEPT: merge `--no-ff`.

Dispatched as run 34987717417 (base pinned to origin/main 35182ef,
`decide=0 vary=0`, default seeds). Pre-merge suite on the joint state:
857 passed + 1 ty diagnostic (`answered * retake` where `ty` cannot see
answered-implies-priced -- stated as an assert in `4b4297c`), corpus
recaptured at `e06ce3a` (449 records, was 499).

## Re-gate on the combined base (rebased 2026-09-15)

The joint gate above ran against a stale base (35182ef, pre-italy). The
branch has since been rebased onto origin/main 339d5ac (italy default +
rival urgency) and re-verified from scratch:

- Fresh recapture on the combined base: 513 records (was 449), seeds
  4000-4003.
- Full suite green locally: 859 passed, 3 skipped, 1 xfailed in 9:06.
  The corpus oracle alone is ~8 min now -- late-turn positions keep
  getting more expensive as games run longer, not a product signal.
- Poke ceilings confirmed on the combined base: on-arm 0 on all six
  seats; off-arm median 3.5, max 9 (4001 US), every seed carries the
  separation (4000 {2,7}, 4001 {9,1}, 4002 {2,5}).
- Re-dispatched as run 35008792222 (base pinned to origin/main 339d5ac,
  `decide=0 vary=0`, default seeds). Verdict: REJECTED -- pooled 0.449
  +/-0.028 over 128 seeds, one-sided 95% upper 0.494, needs 0.500.
  Checkpoints clean (turn-3: 0.533 over 2 seeds); full games split
  0.469 vs-base / 0.430 vs-held-out, mean signed VP -2.23. The same
  stack ACCEPTED at 0.459 on the pre-italy base, so the delta is the
  stronger base (italy default + rival urgency), not the stack itself --
  but the verdict is the verdict: NOT merged. Next step per 2026-09-15
  discussion: bisect, prime suspect the reply-coup revert.

## Bisect: five-bucket + removals without the reply-revert

Branch `experiment/scoring-five-no-reply`: the combined-base stack with
the reply-coup revert (and its ty invariant) reverted away, isolating
the revert as the REJECT suspect. Revert fallout, both diagnosed as
removals pins riding in the wrong commit, re-applied and verified with
coup answers back: scored < live == held (deltas 34.46 < 68.03 == 68.03)
and the Venezuela/Brazil access geometry (trial moves 1.91). Poke arms
re-measured identical to the with-revert numbers (on 0 everywhere, off
median 3.5 max 9), so the poke prose stands. Corpus recaptured (420
records); suite 861 passed + 2 revert-fallout failures fixed, then green
on the rerun files.

Dispatched as run 35017324662 (base pinned to origin/main 339d5ac,
`decide=0 vary=0`, default seeds). Verdict to be appended. On ACCEPT:
the revert is the loser -- drop it from the five-bucket branch and
re-gate. On REJECT: the stack itself misses on the stronger base.
