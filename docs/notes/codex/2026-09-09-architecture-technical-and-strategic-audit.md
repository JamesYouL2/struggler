# 2026-09-09 — Architecture, technical and strategic audit

Read-only audit anchored to committed `7cb9fbe` (which removed the stale
country/access memos). An untracked `src/struggler/bots/evaluator.py` and
changes to `strategic.py` were being edited concurrently. Observations about
that extraction are provisional integration risks, not findings against a
finished implementation. No implementation files were changed for this
audit. Numerical event findings below were reproduced with focused runtime
probes; the broader assessment is based on code inspection, not a new full
suite or strength tournament.

Overall assessment: the architecture has a solid foundation, but evaluation
consistency is currently a bigger constraint than search speed. Increasing
MCTS depth before resolving that consistency risks searching more deeply
with misleading values.

### Architecture

**The observation boundary is sound in the inspected paths.** StrategicPlayer
selects from supplied legal actions and reconstructs simulations from public
observations. No direct access to the live opponent's hand or RNG was found.
Keeping legality in the engine and DEFCON survival in a separate planner are
good boundaries. This was not an exhaustive hidden-information audit.

**High priority — explicit evaluation context and state contract.** The
committed player mixes observation preparation, board mutation, evaluation,
event simulation and policy selection. `value(board, side)` also depends on
the player's previously prepared observation. Consequently a local-looking
change can alter distant callers. Numerical kernels should receive explicit
position, weights and context, with cache ownership and lifetime defined at
the boundary.

The pure evaluator extraction is promising, but the inspected wrapper keeps
both `board.influence` and an indexed position. Every mutation must update
both. At inspection time, `RolloutPolicy._placement_plan()` still wrote
influence directly; cached-ranking synchronization paths also deserve an
audit. These callers must be checked before accepting the new snapshot
representation. A pure kernel does not by itself make its stateful wrapper
correct.

**High priority — benchmark isolation after extraction.** `scripts/gate.sh`
extracts only the baseline's `strategic.py` and imports it inside the
candidate's package environment. Once both versions import `evaluator.py`,
the baseline can silently use the candidate evaluator. Compare complete
revision-specific implementations, including evaluator dependencies, rather
than a single historical source file.

### Technical correctness

**High — event valuation omits indirect board changes.**
`StrategicPlayer._resolve_sandbox()` refreshes only countries whose influence
changed, although `country_value()` reads neighboring influence and, when
wipe weights are enabled, global coup-target counts. Removing the old memos
does not repair this separate reuse of the event basis.

Reproduction on `7cb9fbe`: an engine with US influence 2 in Egypt, 1 in
Israel and 1 in Mexico, with a US placement observation, values Nasser at
**-67.8296875** through `_public_event_value()`. Full before/after board
recomputation gives **-65.8890625**. Israel's **+1.940625** change is omitted
because its own influence did not change. This can misrank events against
Ops. Recompute the full affected dependency set, or use full board
recomputation as a correctness reference before optimizing it.

**Medium — event helpers retain old weights.** `_event_helper()` constructs
its policy once using the parent's weights. Replacing `bot.weights` leaves
the helper on the previous weights, so simulated choices and their
evaluation can use different weights. This was reproduced by creating the
helper, replacing the parent's weights, and checking the helper's weights.
The existing weight-change regression does not exercise that helper. This
affects reused players whose weights change, rather than every normal game.

**Medium — unexpected simulation failures are hidden by generic estimates.**
`event_value()` catches every `Exception`, logs at debug level and substitutes
an allegiance/Ops estimate. A programming error can therefore produce a
plausible number instead of a visible failure. Distinguish expected
unsupported simulations from implementation errors, and make fallback use
observable in diagnostics and validation.

**High — gate completion is not gate acceptance.** `gate.sh` reports scores
but does not enforce strength or nuclear-loss acceptance thresholds. A zero
exit status establishes successful execution, not strategic acceptance.
The earlier handoff's statement that the region-margin gate "passed" was
too strong: the 32-seed run completed with the recorded neutral results,
which still require interpretation. Define explicit acceptance criteria and
compare expert-check changes before describing a candidate as passing.

### Strategic quality

**High — persistent effects are systematically undervalued.** Flag-only
events commonly receive zero. This is an acknowledged limitation in
`docs/STRATEGIC_AI.md`, not a newly introduced regression, but it matters
strategically. In a probe with US-controlled Taiwan and USSR-controlled
Thailand, Formosan Resolution and Shuttle Diplomacy both received event
value **0**, while improving immediate Asia scoring by **1 VP** and **4 VP**
respectively. Prioritize high-impact effects whose benefits can be evaluated
from public state.

**High — scoring urgency has an incomplete horizon model.**
`public_cards.scoring_schedule()` treats unseen scoring cards as scoring now
and again after an estimated reshuffle. It does not cap those predictions
at game end or explicitly include final scoring. Late-game investments can
therefore be priced against opportunities that never occur. Use a bounded
remaining-game horizon and distinguish current-cycle uncertainty from
mandatory final scoring.

**Medium — card and operations selection use different placement models.**
`ops_value()` uses a greedy multi-country spend; the influence branch of
`score(OPS_TYPE)` extrapolates the best single-country investment across all
Ops. A card can be selected based on one allocation estimate, followed by an
operations-mode choice based on another. Align the spend evaluator used by
these decisions while keeping the engine's legal actions authoritative.

**Medium — local gains miss sequencing and counterplay.** Average gain per
Op cannot fully capture combinations, defensive timing or the opponent's
next response. This is intentional tactical scope, not an implementation
defect. Weight tuning alone cannot solve it. Targeted continuation search
for consequential decisions is more promising than a blanket increase in
simulation count.

**Medium — repeated benchmark reuse encourages overfitting.** Selecting
successive changes on the same seeds against recent predecessors can favor
narrow improvements. Keep paired seeds for debugging and attribution, but
reserve untouched seeds and multiple opponent styles for promotion. This is
a methodological risk, not proof that any particular improvement overfit.

### Recommended order

1. Finish the evaluator state contract and audit every rollout/sandbox
   mutation and synchronization path.
2. Correct event recomputation and expose unexpected simulation failures;
   update event-helper weights when the parent changes.
3. Repair full-revision benchmark isolation and define explicit gate
   acceptance criteria.
4. Correct scoring horizons and price the highest-impact persistent
   effects.
5. Evaluate targeted MCTS improvements on held-out seeds at equal wall time.

This audit supersedes the prior handoff's recommendation to immediately
optimize `_access`: the subsequent memo-removal commit and concurrent
evaluator extraction change the baseline, and correctness/integration now
take priority. Earlier timing numbers describe their named revisions only.
