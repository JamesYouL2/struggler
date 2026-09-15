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
