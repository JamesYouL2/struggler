# Strategic bot experiment plan

Date: 2026-09-20
Publication base: `316b5af92b75d89f3c51b3dad7f3c3617ae10418` (`main`).
Scope: turn the experiment discussion into a prioritized, falsifiable plan.
This is a planning note, not a fresh correctness audit or experiment result.
No tournaments or implementation changes were performed for this note.

## Current context and corrections to the discussion

Main has advanced since the September 19 audit discussed in chat. Do not
repeat already completed work or treat old findings as newly verified:

- PR #18 merged the fast `potential_delta` implementation. At the publication
  base, a search of `policy.py` finds its definition but no call to it. A
  merged evaluator primitive is not evidence that the live ranking uses it.
  Trace all intended consumers before defining the activation experiment.
- PR #20 merged `vp_swing=3.0`; use that current default in the baseline,
  rather than rediscovering the same tuning result on previously used seeds.
- PRs #19 and #21 merged ranking-loop and sandbox-budget performance work.
  The [sandbox note](../claude/2026-09-20-the-stall-is-the-drain.md) records
  an anchored 1024-seed comparison and distinguishes tail improvement from
  whole-game speed. Do not claim that reducing planner nodes makes the
  entire bot proportionately faster.
- The [last-exit measurement](../claude/2026-09-19-last-exit-instrument.md)
  already provides a hand-planning diagnostic: seven cornered seat-games
  among 256, all ending in nuclear loss in that sample. This is association,
  not proof that an allocator would have prevented all seven losses.
- Ortega/Tear Down geographic risk and double-counted DEFCON event risk
  were raised in the prior discussion. Their status has not been re-audited
  here. Reproduce on the pinned implementation before opening repair work.

Existing rebuild and architecture notes contain historical status statements.
Use current call paths and exact SHAs to establish integration status. Before
implementing, inspect relevant active branches and handoffs to avoid duplicate
work; the remote branch inventory was checked while preparing this note.

## Priority and experiment definitions

### 1. Establish a safe comparison baseline

Recheck the previously reported risk issues with minimal reachable positions.
If still reproducible, fix each independently and add focused regressions.
Compare corrected and uncorrected policies to measure impact, but do not
retain a known correctness bug merely because a noisy strength result is flat.

Carry shared engine and safety repairs into both arms of later experiments.
Record both exact commit SHAs. Separate forced/unavoidable nuclear losses
from avoidable choices when a replay supports that distinction; otherwise
label the classification unknown.

Done when: historical findings are marked fixed, reproduced, or unverified;
regressions cover confirmed repairs; subsequent arms share those repairs.

### 2. Activate the VP evaluator and measure decision changes

Question: does coherent expected-VP ranking improve decisions over the current
live heuristic, given the same legal candidates and search settings?

First trace placements, removals, coups, realignments, event sandboxes, direct
VP, and risk pricing. Do not run a strength gate between two arms that both
still use the same old policy. Complete common-unit accounting before calling
an arm the integrated rebuild. Preserve terminal outcomes and avoid counting
banked VP, regional tiers, or control uncertainty twice.

Compare the current ranking with the integrated candidate on a fixed position
suite and then in paired games. Keep opening policy, candidate generation,
opponent, and search settings fixed for the initial evaluator comparison.
Log top-action disagreement, component values, fallback frequency, and a small
replay set explaining consequential changes. Do not overwrite the reference
corpus before recording the differences.

Done when: the intended live paths demonstrably use the new evaluator,
accounting checks pass, and fresh-seed evidence supports adoption under the
project's existing gate policy. An inconclusive result remains inconclusive.

### 3. Measure runtime alongside evaluator activation

Question: is the integrated evaluator affordable, and where is its cost?

Use identical early-, mid-, and late-game positions, including expensive
hand-planning and event-sandbox states. Measure median, p95, and maximum
decision latency, evaluator calls, planner states, and fallback rates. Include
complete games: corpus ranking alone missed the sandbox-budget effect.

Measure both arms on the same otherwise-idle machine with the same worker
count. Repeat timings and record machine and contention metadata. Hosted
strength results are useful; their shared-runner clocks are not portable
speed claims. Profile the current merged implementation before proposing
native code or repeating the already merged optimizations.

Done when: a measured strength/runtime trade-off is available, including tail
latency. Report ranking throughput separately from full-game time.

### 4. Joint space/hold allocation, then scoring/event sequencing

Question: can allocating disposal capacity across the whole hand prevent
entering dangerous states without sacrificing more valuable opportunities?

After the evaluator is integrated and viable, compare the existing planner
with joint space/hold allocation using that same evaluator in both arms.
Reserve space attempts and hold slots jointly; account for eligibility,
scoring deadlines, future compulsory plays, and legal event timing.

Reuse `scripts/measure_last_exit.py`. Record corner rate, risk-tail mass at
0.25, first lost exit, nuclear losses by side, and which play preceded the
corner. Its risk labels come from the planner's model, so inspect replays
against engine legality rather than treating the model as an independent
oracle. Also record opponent events triggered and scoring outcomes; event
count alone does not measure event cost.

Start with saved dangerous-hand cases for diagnosis, then test ordinary games
to measure prevalence and side effects. Rare corners require more evidence
than a small full-game sample. Add scoring/event sequencing as a separate arm
after allocation so the sources of any gain remain attributable.

Done when: the candidate reduces demonstrated avoidable traps and passes
fresh-seed strength validation without a material regression elsewhere.

### 5. Optional later experiment: evaluation versus more search

Keep this deferred until the earlier work is measured; it is not a request
to start MCTS or expand the current implementation scope.

Compare current and improved evaluators at shallow and deeper search settings
(a 2-by-2 comparison where feasible). First use fixed settings to isolate the
interaction, then compare the best alternatives at equal measured compute.
Respect hidden-information boundaries and use the same legal observations.

Done when: evidence identifies whether extra computation is better spent on
evaluation or search, rather than assuming deeper search must be stronger.

## Common measurement protocol

- Pin baseline, candidate, engine, configuration, opening policy, and anchor
  to exact revisions. Resolve the historical `07d553a` anchor to its full SHA
  before execution. Never use a moving branch name as the recorded identity.
- Start with 128 paired seeds, both seats: 256 games for a direct candidate
  versus baseline matchup. For anchored comparisons, run each policy against
  the same frozen opponent on the same seeds and seats: 512 games total for
  two policies. Record the actual denominator and incomplete games.
- This is screening, not enough to settle small gains. Confirm promising
  arms on a predeclared fresh block, typically 1024 paired seeds, under the
  existing gate policy. Do not tune on the confirmation block.
- Report score/win rate by side, draws, nuclear-loss rate, ending reason,
  completed/planned games, errors/timeouts, and decision latency. Report final
  VP by ending category; a pooled final-VP average can mislead.
- Compute uncertainty on paired seed-level differences, retaining both seats
  within each seed cluster. Use the established sequential rule if stopping
  early; otherwise finish the declared sample. Do not repeatedly peek with
  ordinary fixed-sample intervals and stop at the first favorable result.
- Use the immediate parent and a historical anchor. An anchored gain checks
  for opponent-specific exploitation but does not prove general strength.
- Save configs, exact commands, seeds, reports, and diagnostic replays under
  `logs/experiment-plan-20260920/` when running. Summarize durable findings
  in a new indexed note, including null and negative outcomes.
- Use existing CI for suites and strength comparisons; use a quiet local
  machine for quotable timings. Gate dispatch still requires the explicit
  authorization specified in AGENTS.md. This docs push does not dispatch one.

## Result record for each arm

Record: hypothesis; baseline/candidate/anchor SHAs; shared fixes; changed
factor; config; seed blocks; planned/completed games; paired score difference
and interval; seat results; nuclear-loss counts; runtime distribution; fallback
and error counts; replay examples; verdict; and the next decision it supports.

## Validation of this note

Read repository guidance, the notes index, rebuild plan, current source
references, recent merge history, and relevant measurement notes. Checked
Markdown paths and diff whitespace. Full-suite verification is delegated to
`tests.yml`, which runs on every branch push; no local suite or strength
experiment was run for this documentation-only change.
