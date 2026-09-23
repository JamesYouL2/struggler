# Current state and experiment-boundary audit

Date: 2026-09-22. Repository: JamesYouL2/struggler.
Reviewed main: `cec39ca958cd774ead806690e84b4c83e5cc1064`.
Previous audit: `316b5af92b75d89f3c51b3dad7f3c3617ae10418`, published on
`394bfdd219becae9645e810aa045ca78043f250f`.
Historical baseline: `v0.1.0` = `50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9`.
This is a bounded follow-up, principally reviewing changes since the previous
audit, not an exhaustive audit of every card since v0.1.0.

## Assessment

The live bot is materially further along than the September 20 audit. Both
reported safety defects are fixed on main, and the fitted country-value layer
is shipped. The largest missing policy capability is a joint value-side hand
allocator: the existing whole-hand search optimizes survival, while space,
hold, UN Intervention, headline, and scoring timing remain per-card prices
and guards. The optional stochastic regional potential is implemented but off.

No new engine or default-policy correctness defect was verified in this
bounded review. Three experiment-boundary defects were verified below. Passing
component tests did not cover the actual producer/consumer contract.

## Current implementation and previous findings

- **F1, restricted borrowed-coup latent hazards: fixed.**
  `DefconPlanner.borrowed_coup_threat` is shared by direct event risk and
  `latent_hazards`; Ortega and Tear Down This Wall retain their geography and
  DEFCON exceptions. Merged fix `a282dff` is an ancestor of reviewed main.
- **F2, duplicate post-event transition: fixed.** `_after_event` carries back
  the resolved state, and `continuation_risk` consumes the play without firing
  the event a second time. Merged fix `220170c` is an ancestor of reviewed main.
  The Duck/CIA, Bear Trap, Fidel, and restricted-coup regressions pass.
- **Country-value rebuild: shipped.** `country_vp_scale = 2.795`; the old
  guessed `battleground`/`control` weight branches were deleted. Repository
  experiment notes report a fresh-block paired gain of +0.054
  [+0.031, +0.078], 1020 shared seeds, against `bc5ef93`. This is recorded
  evidence, not an experiment rerun in this audit, nor proof against humans
  or all other opponents. The notes disclose four missing seed pairs across
  arms; the incompleteness issue below does not by itself erase that gain.
- **Region potential: implemented, default off.** `potential = 0.0` and
  `potential_refresh = 0.0`. The sandbox gap is already repaired in `15caae4`;
  the nearby weight comment and opening status in the rebuild note are stale.
  The earlier approximate-potential reading was inconclusive. The registry
  contains new `potential-verdict-*` arms for the corrected path; no completed
  result for those arms was verified here. Do not restart the implementation
  or call the pre-fix result a verdict on the corrected version.
- **Hand planning: survival search exists; joint value allocation does not.**
  `DefconPlanner._solve` searches the hand under explicit priors and a node
  budget. `un_card`, `space_card`, `value_as_held`, and `_score_card_play`
  still make separate value decisions. Safe-card state canonicalization
  remains an optimization proposal, not an implemented speedup to claim.
- **Rules fidelity remains qualified.** Existing limitations include forced
  scoring-card play excluding an alternative immediate winning play, and
  incomplete persistent hand visibility for Aldrich Ames. These are documented
  existing limitations, not newly discovered defects.

## Verified findings

### F1 — P2: paired experiments never reach their intended stopping test

Locations: `scripts/pool_reports.py:main` and
`scripts/wave_verdict.py:decide`; caller:
`.github/workflows/experiments.yml`, `interim` job.

The producer serializes `{'arms': result, 'paired': pairs}`. The consumer
looks up `pooled_json.get('pairs')`. The workflow passes the file unchanged.
Consequently every `compare_to` comparison becomes “no readable paired
difference” and continues, even when the actual paired statistic is decisive.
This wastes the second wave; it does not falsely promote the candidate.

Reproduction through the actual pooling CLI: write 40 complete paired seeds
for each arm, base score 0 and candidate scores alternating 0.5/1.0. Pool to
JSON and pass that JSON into `decide`. Both arms return `proceed=True, z=None`.
Adding the consumer's expected key with the unchanged producer's paired list
returns `proceed=False` for both, at z=18.735. The unit tests manually construct
`pairs`, so they pass without exercising this boundary.

Smallest correction: settle on one field and add a producer-to-consumer
integration regression, using the actual file emitted by `pool_reports.main`.
Cover decisive, inconclusive, and unreadable comparisons. Preserve fail-open
behavior for genuinely missing evidence.

### F2 — P2: pooling loses incomplete-run evidence and cannot count absent artifacts

Locations: `scripts/pool_reports.py:load`, `pooled`, and `markdown`;
`scripts/wave_verdict.py:_level` and `decide`.

`load` takes only `report['games']`, discarding `summary.stop_reason`,
`planned_games`, and `unfinished`. A stalled shard with a partial report is
counted as an “ok” shard. A shard with no artifact directory is never visited
by `root.glob('experiment-*')`, so it is absent from `missing` too. Only a
directory that exists but lacks its report gets marked missing.

Reproduction: provide one shard with metadata `of=2`, 40 complete seeds,
`stop_reason='stalled'`, `planned_games=82`, and two unfinished seat-games;
omit the second shard directory entirely. Pooling reports `shards=1`,
`missing=[]`, `seeds=40`, and no incomplete status. It prints “1 ok”. A
non-paired arm with score 0.75, SE 0.04 from this entry stops at z=6.25 instead
of following the documented missing-evidence fail-open rule. Once F1 is
repaired, paired arms are exposed to the same missing-metadata problem.

The complete-pair filter works: it excludes singleton seat results. That
does not make outcome-dependent missing games ignorable or establish that
the planned sample finished. This finding is about lost evidence and stopping
eligibility, not a claim that every partial estimate is unusable.

Smallest correction: pass the expected shard manifest into pooling and retain
per-shard completion status. Distinguish complete, partial, missing, and
intentionally skipped after an interim decision. Keep descriptive partial
statistics, but mark them incomplete and continue when required evidence is
missing. Acceptance tests must include absent directories, partial JSON,
one missing seat, and intentional wave-2 skips.

### F3 — P3: final reporting does not use the advertised sequential boundary

Locations: `scripts/wave_verdict.py:FINAL_BOUNDARY`,
`scripts/pool_reports.py:paired`, `pooled`, and
`.github/workflows/experiments.yml:collect`.

The two-look design computes a final threshold of 1.677952711, but collection
always uses `ACCEPTANCE['confidence'] = 1.645`. `FINAL_BOUNDARY` is printed in
the interim summary and never applied by the final pooling path. Thus the
claimed approximately 2% widening is not delivered. A final z=1.66 clears the
reported bound while failing the design's own final threshold. Early-stopped
arms likewise get an ordinary fixed-sample interval without stage-aware
qualification.

This matters for near-threshold significance claims, not for arithmetic of
the raw scores. F1 currently prevents paired interim stops, so do not assert
that it already induced selection bias in every paired run. Independent arms
can stop now; repairing F1 makes stage-aware paired reporting necessary too.

Correction: carry design/stage metadata into reporting and distinguish fixed
sample descriptive intervals from sequential decisions. Use the appropriate
boundary for the actual look; validate information fractions when shard counts
are odd or evidence is incomplete. Test a final z between 1.645 and 1.678,
an early stop, and `waves=false`. This is smaller priority than F1/F2, but it
belongs in the same experiment-contract repair before trusting marginal gains.

## Reproduction fixture

No implementation was modified. The following constructs reports, not games
or strength evidence, and exercises the real producer. Run with `uv run python`:

```python
import contextlib, io, json, runpy, tempfile
from pathlib import Path
P = runpy.run_path('scripts/pool_reports.py')
W = runpy.run_path('scripts/wave_verdict.py')
def game(i, side, result):
    return dict(seed=i, bot_side=side, finished=True, turn=10, reason='vp',
                result=result, winner=side, signed_vp=0, projected_vp=0,
                total=0, bg_diff={}, value=0, defcon=2, seconds=1, searches=0)
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    for slug in ('base', 'on'):
        d = root / f'experiment-{slug}--0'
        d.mkdir()
        games = [game(i, side, (0.5 if i % 2 else 1.0) if slug == 'on' else 0.0)
                 for i in range(40) for side in ('US', 'USSR')]
        summary = dict(stop_reason='stalled', planned_games=82,
                       unfinished=[[40, 'US'], [40, 'USSR']])
        (d / f'{slug}.json').write_text(json.dumps(dict(summary=summary, games=games)))
        (d / 'arm.json').write_text(json.dumps(dict(
            slug=slug, shard=0, of=2, compare_to='base' if slug == 'on' else '')))
    with contextlib.redirect_stdout(io.StringIO()):
        P['main']([str(root), '--json', str(root / 'pooled.json')])
    data = json.loads((root / 'pooled.json').read_text())
    print(list(data), W['decide'](data))
    print(W['decide']({**data, 'pairs': data['paired']}))
    print(data['arms']['on'])
    print(W['FINAL_BOUNDARY'], P['ACCEPTANCE']['confidence'])
```

## Next steps, in order

1. Repair F1/F2 and stage-aware reporting as bounded experiment-contract work.
   Test the real JSON/workflow boundaries, not separately fabricated schemas.
   Do this before spending another large paired experiment budget.
2. Build the smallest joint **space / hold / UN Intervention allocator** on
   frozen per-card prices. Enforce slot and action-round capacities, scoring
   deadlines, current space eligibility, and unique card assignment. Reuse
   the existing survival model; do not duplicate its event-risk rules. On
   small hands, compare against exhaustive allocation as an acceptance oracle.
   Start behind an opt-in flag; better assignment is a strength hypothesis.
3. Add headline allocation and bounded scoring-timing choices after the
   allocator is coherent. Replan after observations and random outcomes rather
   than executing an unconditional turn script. Deeper reply search is a
   separate hypothesis, not a prerequisite for this allocator.
4. Evaluate the already-built corrected regional-potential and refit candidates
   independently if still desired. Keep shared correctness repairs in both
   arms, pin candidate and anchor SHAs, hold openings/compute comparable,
   and report complete paired seeds, per-seat outcomes, nuclear losses,
   fallback rates, and wall time. Do not bundle these changes with hand planning.
5. Canonicalize interchangeable safe survival states only with proven
   equivalence, and profile the integrated policy before broader optimization.
   No language rewrite is justified by this audit.

## Branch inspection, validation, and limits

Remote heads were enumerated and fetched, not inferred from a main-only clone.
The remote default branch is main. Relevant remote tips that are already
ancestors of reviewed main (each is its merge base with main):

- `rebuild/value-function`: `ce1293dd1fcd871209dcc94e88ce1d8dbda57bb7`.
- `docs/whole-hand-planner`: `61f88214bded769071e828e96cb52dde766dc874`.
- `exp/potential-in-ranking`: `6ff8b2bdeebdbf649c5aeef754a205dedb28617e`.
- `fix/latent-hazard-geography`: `a282dffb14b2993fa6637cc3243a5a1650ed1326`.
- `fix/post-event-continuation`: `220170c74d52ea89e109774005ebca1095f7d6ef`.

Also inspected the unmerged handoff-only delta on
`claude/struggler-experiments-strategy-pjp7u0` at
`16d945e2f2a447907b0fead55e02067cecbd5417`; it is not an unmerged planner
implementation; its merge base is `52cdc55bdb3928fb45468cb4f718938e5ff50bbb`.
Other historical experiment branches were not exhaustively
reviewed. The connected PR search returned no open PRs.

Executed at reviewed SHA:

- `uv sync --frozen --extra test`: success.
- Focused suite covering survival, engine DEFCON chains, history privacy,
  forecasts, potential, benchmark pairing/stalls, waves, cache identity, and
  experiment workflows: **258 passed in 22.81 seconds**.
- Actual producer/consumer reproduction above, plus a non-paired incomplete
  arm stopping example and the z=1.66 reporting-boundary check.
- Full `uv run pytest -q`: **1158 passed, 4 skipped, 1 xfailed in 159.83 seconds**.

No tournaments, paid model calls, weight updates, or workflow dispatches were
performed. Full-suite results establish regression coverage, not playing
strength. Omitted: exhaustive card/rules survey, full MCTS/rollout/LLM/physical
mode review, and new performance or tournament measurements. Matching-main CI
was not established from the status connector (it returned no status entries).
Local test output and reproduction output are in `logs/audit-20260922/`.

Publication follows the standing documentation commit/push instruction in
`AGENTS.md`: a separate notes-only branch, no implementation changes or PR.
