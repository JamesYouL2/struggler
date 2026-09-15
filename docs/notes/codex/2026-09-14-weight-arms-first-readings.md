# 2026-09-14 — Weight arms: first readings (old model, do not ship)

Two of three `experiments.yml` inline arms are complete (logs:
`logs/exp-20260914/`). Both ran pre-two-state-merge, so per the rebuild
plan these are readings of the superseded model: evidence, not
calibration. Nothing ships off them.

- `scoring-hand-flat` (`{"scoring_hand": 1.0}` vs 1.2): pooled 0.503
  +/-0.038 over 192 seeds. The +20% holding bonus buys nothing
  measurable. Candidate for deletion with the rebuild (step 2
  re-derives what holding is worth anyway); not before.
- `access-contested-off` (`{"access_contested": 0.0}` vs 0.25): pooled
  0.512 +/-0.043 over 192 seeds. Dead heat with a slight upward lean;
  no case for removal, no case for keeping -- the rebuild's access
  accounting (conversion already in, contested split documented as the
  refinement path) decides it.
- `region-par` still running at time of writing.
