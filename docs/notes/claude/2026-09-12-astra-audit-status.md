# Astra's audit, item by item, at `7902bb1`

Astra (Codex) sent two defect lists on 2026-09-11 -- five reproduced defects
audited at `96b2e78`, then eight ordered tasks rechecked at `ca29fa5`. Both
reached this repo only as messages pasted into a Claude session, never as a
file: `docs/notes/codex/` stops at 2026-09-09. So they were invisible to the
2026-09-13 handoff and to the overnight queue built from it, which is the
reason this note exists.

**Superseded in part, same evening,** by Codex's full audit
(`docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md`), which is the
current list. In particular its F7 REOPENS item 5 below: `FrozenPayload`
does not override `|=`, and the decision `context` is still shared, so an
observation can still move the engine's Ops budget and legal options. Read
the rows below as the state of the 2026-09-11 lists only.

The eight tasks contain all five defects, so there are eight items. Status
re-verified against HEAD `7902bb1` on 2026-09-12 by reading the tests, not
from the 2026-09-11 status table (which predates three of the fixes).

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `setup_bonus` survives replay | **closed** | `2f5a8fe`; `test_replay_and_isolation.py` 31-59 (seed-42 replay, legacy logs) |
| 2 | No private options in shared history | **closed, one gap** | `2f5a8fe`, then `293dd1f` (Blockade keyed its cards `choice`); `test_history_privacy.py` checks card-id *values*, context included. Gap: it drives `HistoryBuilder` directly, not `runner.play_game`'s player interface, which is what Astra asked for |
| 3 | Headline secrecy across resume | **closed, one gap** | `test_resuming_between_headline_picks_does_not_reveal_the_first` covers before and between. Gap: resumed vs uninterrupted histories *after* both picks are not compared |
| 4 | `observe(non-acting seat)` hides the actor's options | **open, recorded blocker** | strict xfail, `test_replay_and_isolation.py:101`. `observe()` serves both "what a Player may see" and "the board from this seat"; `benchmark.expert_check` needs the second (US-signed valuations while the USSR moves). Closing it needs a separate analysis view -- a design change. No production path reaches the leak |
| 5 | Observation mutation cannot reach the engine | **reopened** by the 2026-09-13 audit, F7 | `FrozenPayload` and tests at 167 and 175 close assignment and `update`; `|=` and the shared `context` still reach the engine |
| 6 | Profiler attribution after the package split | **closed** | `28abb40`; `tests/test_tooling_paths.py` |
| 7 | Deterministic Ops-war fixtures | **closed** | `7f60270` |
| 8 | Thin multi-opponent comparison entry point | **open, not started** | nothing in `benchmark.py` or `scripts/` takes several opponents |

## What is left, in the order I would take it

1. **Item 2's gap** -- one test through `runner.play_game` with two recording
   players, asserting what each was handed. Small, and it tests the
   boundary where the leak actually happened rather than the builder behind
   it.
2. **Item 3's gap** -- extend the resume test past the second pick.
3. **Item 8** -- tooling. It is what would have caught the drift the
   2026-09-12 four-anchor bisect had to find by hand, so it is worth more
   than its size suggests, but nothing is blocked on it.
4. **Item 4** -- a design decision for the maintainer: split `observe()`
   into a player view and an analysis view, or keep the documented xfail.

None of these is overnight-queue material: each is a code change whose
review is the point. The queue built the same night runs measurements only.

## Still open from Codex's 2026-09-09 reassessment

Re-read against HEAD, not re-verified in code:

- `_event_helper` does not follow a replaced weights object (conditional).
- `OPS_TYPE`'s influence branch uses best-single-country average gain while
  `ops_value` uses the greedy multi-country spend.
- Flag-only persistent effects: `_resolve_sandbox` now reads the sandbox's
  own scoring flags (Formosan Resolution, Shuttle Diplomacy), which covers
  the named examples; whether every flag-only effect is priced was not
  checked.
- The silent sandbox fallback is no longer silent (`log.warning` plus
  `sandbox_failures`), but nothing *reads* it in a gate -- which is exactly
  why the Blockade RecursionError (2026-09-13 handoff, 4c) has no stack.
  The overnight queue's self-play tracer is the first thing that keeps one.
