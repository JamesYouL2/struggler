# Correctness, remaining strength ideas, and freeze readiness — 2026-09-28

Reviewed main/default branch: `0085ba06004fe1e84b2d416c483e91e3048b4756`.
Previous audit source baseline: `5ab9eab4417080d167359f06a381eab8865891f0`; its publication update was `9a8f6c5d476b76b137f97f30199bcdd12df26e3f`.
Current strength anchor: `v0.6.0` = `dfc1e2bcb9158d8f283d7996f7901d7f1beab234`.
Historical baseline: `v0.1.0` = `50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9`.

## Assessment

The five September 27 findings have fixes on main. This review found no new default-Strategic or engine-rule defect in the sampled paths. It did reproduce two problems in MCTS and its experimental interpretation, plus an offline measurement mismatch. Fix these before presenting the current MCTS experiments as a clean test of adding search to Strategic.

There is no supported claim that a cheap remaining change will add five percentage points of win rate. Interpret the requested five percent as five absolute points against a fixed opponent, not a relative percentage increase. The most useful remaining small correctness job is to repair the leaf and isolate search from its live continuation policy. Its playing-strength effect is unknown. Starting a write-up now is sensible; freeze the default Strategic reference separately from the experimental search.

This is a bounded follow-up source audit, not an exhaustive survey of every card. Reviewed recent engine fixes, final scoring, strategic caches/evaluation, MCTS/rollout boundaries, the new outcome collection/fitting pipeline, and experiment notes/ledger. LLM adapters, physical-mode interactions beyond golden replay, and all event combinations were not re-audited. No implementation changes or tournaments were made.

## F1 — P1 for MCTS: banked VP uses a stale price from the previous ranking

Locations: `src/struggler/bots/mcts.py:262–276`; `bots/strategic/policy.py:evaluate` (1303), `vp_value` (1673).

`leaf_return` calls `policy.evaluate(obs)` and then `policy.vp_value(obs)`. The first call temporarily prepares the leaf, then restores the previous board and `_vp_price`/`_ops_values`. The second call consequently prices the leaf's banked VP using the previous ranking's board-dependent Op price. Passing the leaf observation only changes the turn multiplier; it does not invalidate that cached price.

This is reachable in ordinary search, not just an artificial call sequence. Start at corpus record 31 (zero-based), seed 4000, USSR T3 AR1. Run four simulations, horizon 1, safe root, and inspect each leaf with a fresh player prepared on that leaf as the independent price reference. The first leaf has US VP +14:

| Quantity | Existing search | Fresh leaf context |
| --- | ---: | ---: |
| VP price | 19.4541460886 | 9.8628041831 |
| Leaf return | -0.3940707965 | +0.7288068595 |

All four sampled leaves differed. The fourth also changed sign (-0.5689961458 versus +0.2138321016). A separate same-position/prior-ranking probe returned -0.99, -0.729852, and -0.420473 for the identical T9 leaf.

The existing `test_leaf_value_does_not_depend_on_what_was_ranked_before` uses a fixture with zero banked VP, so the stale price is multiplied by zero. It cannot detect this defect.

Smallest useful correction: calculate board value and banked-VP price inside ONE prepared leaf context with cold per-position caches, restoring the caller afterward. A shared evaluator returning both would also stop the collector and search from drifting. Do not merely delete the restoration in `evaluate`; it protects other callers. Extend invariance coverage to nonzero VP, both seats, different boards/prices, and actual reached search leaves.

This is an experimental-MCTS blocker, not evidence that ordinary `StrategicPlayer.choose_action` is broken. It also remains in `exp/mcts-leaf-scale` at `581ba573904254103ad8dfbcff70f4daf4a45ed2`.

## F2 — P2: AR1-only MCTS changes live policy outside AR1

Locations: `bots/mcts.py:279–292`, `continuation`; `bots/rollout.py:RolloutPolicy.coup_survival_risk`, `_served`.

`choose_action` routes EVERY non-`ACTION_ROUND_PLAY` decision to `continuation` before checking `rounds`. That continuation uses the cheaper `RolloutPolicy`. The AR filter falls back to Strategic only for the card choice. Setup, headlines, play modes, Ops and event subdecisions still go through RolloutPolicy, including on turns/rounds where no search occurred and when reconstruction fell back.

Concrete default-policy mismatch: corpus record 354, seed 4002, US T5 AR3, `COUP_TARGET`. A fresh Strategic player picks **Honduras**. `MCTSPlayer(rounds=[1])`, with no prior search or target intent, picks **Panama**. The first difference appeared among 162 sampled non-AR1 subdecisions. That is a constructed replay of a real corpus decision, not a measured whole-game frequency or proof either target is better.

Therefore the reported experiment measures the MCTS wrapper INCLUDING a different live continuation policy; it does not isolate the marginal benefit of searching AR1. `search_override_rate` counts card choices and misses this source of changed play. This does not make the observed wrapper scores fictitious or establish the cause of its nuclear losses.

Smallest useful correction: use the full Strategic policy for live fallback decisions outside an explicitly active searched-card intent; keep the cheap policy inside simulations. Decide explicitly how searched-card subdecisions implement the chosen intent. Add a no-search wrapper control and a decision-by-decision parity check with Strategic across a full game, including setup and event interruptions. Alternatively retain the hybrid policy but compare search ON versus OFF with that same hybrid continuation and label it accurately. Preserve survival checks.

## F3 — P2 for reporting: offline “leaf as-is” omits the actual leaf cap

Locations: `scripts/fit_winprob.py:155`; `bots/mcts.py:273`.

The fitter computes `(1 + tanh(raw/100))/2`. Actual MCTS first caps tanh to [-0.99, +0.99], limiting its nonterminal, pre-risk probability to [0.005, 0.995]. At raw=1000 the fitter reports 0.99999999794; the real transform gives 0.995. Log loss is particularly sensitive to this difference. The saved 1.0382 “leaf as-is” loss should not be quoted as an exact measurement of the implemented MCTS leaf until recomputed with the cap. It is additionally a turn-start probe, not a sample of live searched leaves, and does not model optional `leaf_risk`.

Correction: use a shared raw-to-leaf transform, regenerate this report from the existing rows (no new self-play needed), and distinguish raw signal, exact capped heuristic, and risk-adjusted search leaf. The richer logistic-versus-calibrated-model comparison is not directly invalidated by this formula mismatch. The amount of change to the reported metrics was not measured here; the dataset is in CI artifacts, not this checkout.

## Previous findings and active work

- September 27 F1/F4: explicit war target-control flags and shared `Board.war_penalty` are merged. Direct threshold reproductions now pass for Brush War, Indo-Pakistani War, and Iran-Iraq War. Engine/scorer share superpower adjacency logic.
- F2: the China holder receives the final VP. Direct empty-board end-of-turn-10 checks pass for both holders and both availability states.
- F3/F5: digest-off delta caching is disabled; the placement memo includes phasing context. Inspected current code and regression tests; matching-SHA full CI covers them. Did not rerun the whole local pytest suite.
- Discovery included all fetched remote heads, confirmed against GitHub's branch list. Main is the remote default. Most old feature/fix branches are merged or historical experiment alternatives; their existence does not make them pending integration work.
- `exp/mcts-leaf-scale` tip `581ba573904254103ad8dfbcff70f4daf4a45ed2`, merge base `6e47bfdcfd8e6b09cff3daa9acd6731725821c29`: active unmerged implementation/results inspected. Temperature 500 was ALREADY tested, not a new suggestion. Its reported paired change versus 100 is -0.001 [-0.023, +0.021] on 512 seeds. Both shared the leaf/context and live-policy issues above. This is evidence about those implementations, not a general proof that calibrated leaves cannot improve search.
- The hand-assignment planner has been deleted; survival planning remains. Event-exposure/decay variants were measured and closed without a strength nomination. Do not revive these as untried low-hanging fruit.
- Known nonacting-seat observation visibility and forced scoring restrictions remain documented limitations. Neither is newly discovered here. A broader search/learning interface must respect the observation boundary; an evaluator-only port does not require solving every interface limitation first.

## What could still buy strength?

| Candidate | Current evidence | Recommendation |
| --- | --- | --- |
| Correct leaf pricing and isolate the MCTS comparison | Reproduced defects; one reachable leaf changes sign | First correctness work if continuing search. No +5-point promise. |
| Change leaf temperature 100 to 500 | Already tested on the active branch; paired interval spans zero | Do not repeat this alone. Repair semantics first. |
| More simulations/depth | Guarded h1 was 0.509 [0.484, 0.534] at 256 seeds; expensive | Defer until the corrected comparison shows useful overrides. |
| Headline plus AR1 follow-up | Existing proposal, not an established gain | A bounded tactical experiment, not a freeze prerequisite; must model intervening enemy headline where order requires it. |
| China hold value / late-war conditional event decisions | Concrete expert discrepancies, incomplete state-specific coverage | Review 10–20 consequential decisions first; implement only a narrow recurring error. Expert disagreement alone is not a correctness defect or win-rate estimate. |
| More event discount, general hand planning, arbitrary weight sweeps | Substantial flat/negative evidence already recorded | Stop this family for the freeze. |

If one more strength experiment is desired: after F1/F2, compare guarded h1 to a genuinely matched no-search control, paired seeds/both seats, fixed compute/search settings and a predeclared nuclear-loss veto. Use a modest pilot to decide whether a larger run earns its cost. Any finalist should face both corrected current Strategic and v0.6.0 on fresh held-out seeds. Fix rules in the shared engine for both sides. Do not claim general strength from one opponent or use the repeatedly tuned block as the final validation block. Report candidate compute cost as well as score; additional compute and smarter policy are different claims.

## Before freezing and writing up

1. **Freeze scope:** tag the corrected default Strategic/engine reference; mark MCTS experimental until F1/F2 are fixed or explicitly limit the write-up's conclusions to the tested hybrid implementation. No Rust port, neural network, or larger planner is required before writing.
2. **Close measurement claims:** correct F3 and preserve exact SHAs, configuration, opening books, core/reserve seed accounting, seat scores, intervals, nuclear losses and fallbacks. Existing drift evidence is historical; a final claim about the frozen revision needs a matching frozen-revision run. This audit did not dispatch one.
3. **Keep the evidence permanently:** retain outcome rows or an immutable dataset artifact with checksums, pooled results and representative decision traces. The current fit note says CI artifacts expire after 30 days. `fit_all` only exports rounded standardized weights, omitting means and standard deviations; that is not a deployable/reloadable fitted model. Export full-precision coefficients, intercept, feature order/definitions, means, standard deviations, regularization and train/validation/test seeds; verify reloaded predictions agree.
4. **State the limits:** self-play prediction quality is not playing strength; fitted turn-start outcomes need validation on searched mid-turn states before use as a search leaf. The rules/observation simplifications in `docs/LIMITATIONS.md` belong in the write-up.

## Validation

- Matching-SHA GitHub Actions: [tests run 36354018371](https://github.com/JamesYouL2/struggler/actions/runs/36354018371), job 108718016115. Read the actual job log: **1259 passed, 4 skipped, 5 xfailed**. This is CI evidence, not a local full-suite run.
- Local dependency setup: `uv sync --frozen --extra test` did not complete; offline retry reports locked `ruff==0.16.7` unavailable in cache. Local pytest is unavailable. Existing pinned CI provides the full-suite result.
- Direct checks used `PYTHONPATH=src uv run --no-sync python`: all three corrected war thresholds; four China holder/availability cases; all four golden replays via `run_with_checkpoints`; reachable four-simulation leaf mismatch; nonsearch continuation mismatch; exact cap formula mismatch. These completed successfully (mismatch probes assert the defects are present).
- No paid calls, new strength tournament or implementation edits. After the audit, the user authorized publishing these notes on a separate docs branch and opening a PR. Publication base matches the reviewed main SHA.

### Minimal reproducible search probes

Run from the pinned checkout using `PYTHONPATH=src uv run --no-sync python`:

```python
import gzip, json, logging, math
from struggler.engine import Engine, Side
from struggler.bots.mcts import MCTSPlayer
from struggler.bots.strategic import StrategicPlayer

logging.disable(logging.CRITICAL)
records = json.loads(gzip.open('tests/corpus/positions.json.gz').read())['records']
r = records[31]  # seed 4000, USSR T3 AR1 on the reviewed SHA
engine = Engine.deserialize(r['engine'])
obs = engine.observe(Side(r['side']))
bot = MCTSPlayer(simulations=4, horizon=1, rounds=[1], safe_root=True)
original = bot.leaf_return
differences = []

def checked_leaf(engine, side):
    actual = original(engine, side)
    if not engine.is_terminal:
        leaf = engine.observe(side)
        fresh = StrategicPlayer()
        fresh.prepare(leaf)
        raw = fresh.evaluate(leaf)
        raw += fresh.vp_value(leaf) * (1 if side is Side.US else -1) * engine.vp
        expected = max(-.99, min(.99, math.tanh(raw / 100)))
        differences.append(abs(actual - expected))
        print(actual, expected)
    return actual

bot.leaf_return = checked_leaf
bot.choose_action(obs, [])
assert any(d > 1e-9 for d in differences)

r = records[354]  # seed 4002, US T5 AR3 coup
engine = Engine.deserialize(r['engine'])
obs = engine.observe(Side(r['side']))
baseline = StrategicPlayer().choose_action(obs, [])
wrapper = MCTSPlayer(rounds=[1]).choose_action(obs, [])
print(baseline, wrapper)
assert baseline.payload['country'] == 'Honduras'
assert wrapper.payload['country'] == 'Panama'
```
