# 2026-09-09 — Revised nuclear-loss policy and early stopping

The user noted that the absolute nuclear-loss cap was probably overtuned
and asked whether tournament statistics help. They argue against treating
a fixed historical bot count as a universal safety limit; they do not
identify a replacement candidate-loss threshold.

The official [WBC 2024 report](https://www.boardgamers.org/yearbook24/tws.html)
records 3 DEFCON endings in 56 games (5.4%); the
[WBC 2025 report](https://www.boardgamers.org/yearbook25/tws.html) records
7 in 60 (11.7%). These count nuclear endings across both players, not losses
by a designated candidate. Different rules, opponents and player strengths
also prevent directly converting those percentages into a bot allowance.
Nuclear defeat can result from opponent-created hand pressure, not just an
avoidable fatal move. For example, the notes for game 1 of
[BPA 2026 round 4](https://twstourney.wordpress.com/2026-round-4/)
describe a hand-pressure DEFCON defeat.

### Recommended acceptance policy

- Remove the absolute nuclear-loss cap from strength acceptance. Nuclear
  defeats already count as losses in the overall score; a separate cap can
  penalize the same outcome twice and reject a stronger policy.
- Keep candidate nuclear losses and opponent nuclear losses as separate
  diagnostics. Forcing an opponent into a nuclear defeat can be good play,
  not a reason to reject the candidate. Compare rates under matched rules
  and opponents; tournament percentages supply context, not pass/fail limits.
- Keep targeted safety regression tests strict. A known position with a
  safe alternative should not start choosing certain defeat. That is a
  correctness regression, unlike an aggregate nuclear-loss count.
- Use unusual nuclear rates to trigger replay review rather than automatic
  rejection. Inspect whether the change introduces avoidable failures or
  trades increased nuclear risk for a larger improvement elsewhere.

### Consequence for the proposed early-stopping design

The user accepts early stopping as an 80/20 calibration decision, not a
requirement to reproduce every full-run verdict with certainty. The earlier
proposal was paired predictive stopping: finish complete seed pairs, use
fixed checkpoints (provisionally 150, 170 and 192 games), model each sample's
paired-score distribution separately, and predict the full gate's verdict.
A small Dirichlet prior over scores 0, 0.25, 0.5, 0.75 and 1 permits unseen
outcomes, unlike resampling only the observed scores. Proposed initial
thresholds were 99% predictive rejection and 99.5% predictive acceptance,
with acceptance also requiring the observed gate to pass. These are settings
to calibrate, not statistical guarantees.

Revise that proposal to predict the full gate's **strength verdict without
a separate rare-event veto**. Continue collecting ending types for review,
but drop the proposed nuclear-loss model and immediate cap-based rejection.
There is no longer a need to predict whether the remaining games contain
"the second nuclear loss."

Validate in shadow mode: log proposed stops but finish the games. Measure
wall time saved and both kinds of verdict disagreement on held-out
revisions, including near-boundary cases. Compare against a simple fixed
160-game design; retain predictive stopping only if its measured tradeoff
is better. Periodically complete future gates to check calibration drift.

In short: **overall playing strength for acceptance, tactical regressions
for safety, tournament statistics for context**. The historical bot rate
describes that bot and its opponents, not a universal acceptable-risk limit.
This records a recommendation only; no gate code or thresholds were changed
in this documentation update.
