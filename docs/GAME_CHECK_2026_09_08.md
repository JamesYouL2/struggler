# Game testing: September 8, 2026

Tested revision `f044c36` with the bundled `event-value-v1.json` model.
No training or LLM calls were used. This checks the corrected engine; earlier
tournament results are not directly comparable.

## Results

| Matchup | Result |
| --- | --- |
| Strategic vs. greedy | Strategic won 6 of 8 |
| Event-value vs. strategic | Event-value won 4 of 8 |

Four seeds (2400–2403), both seat assignments per matchup. Optional cards
were enabled for odd seeds and disabled for even seeds. These eight-game
samples do not establish playing strength or a neural improvement.

All 16 competitive games finished, totaling 5,083 decisions. Eight ended
at DEFCON 1 and eight at the VP threshold; none reached Late War.

An additional 40 randomized engine games (seeds 2500–2539) exercised 14,764
decisions. Nine reached Late War and four reached final scoring. This test
driver uses full engine state to reject immediately losing actions when
possible, so it is **not** an observation-only bot or a strength benchmark.
It can still lose through delayed consequences and chance.

Across all 56 games:

- No crashes, illegal bot actions, deadlocks, negative influence, or missing
  or duplicated cards were detected; the shared test invariants ran after
  every step.
- Every complete action log replayed to exactly the same serialized state.
- Competitive games passed JSON save/load checks every 50 decisions.
  Randomized games compared restored and live continuations at every step.
- The separate full test suite passed: **422 passed, 3 skipped**.

These checks establish consistency on sampled paths, not exhaustive rules
correctness. Physical mode and live LLM integrations were not exercised.

## Major bot problems

1. **Voluntarily choosing DEFCON 1.** Both strategic variants fall through
   to equal scores for `How_I_Learned_to_Stop_Worrying` choices, selecting
   the first option, `1`. Three competitive games ended this way:
   seed 2400 (strategic US / event-value USSR), and both strategic/event-value
   seat assignments at seed 2403. Safe DEFCON choices were available.

2. **Missing direct event safety.** At seed 2401, strategic US played
   `We_Will_Bury_You` for Ops at DEFCON 2, while ahead by 11 VP, and lost.
   Space Race was a legal option at that decision, and two other cards
   remained available at card selection. This was avoidable immediately,
   not just a failure to plan the whole turn.

3. **Five Year Plan ignores dangerous discard outcomes.** At seed 2402,
   strategic USSR played it for Ops at DEFCON 2 with Duck and Cover among
   three remaining cards. The random discard triggered Duck and Cover and
   lost. Space Race was available. Greedy USSR suffered the same chain at
   seed 2400. A scoring-card escape is useful only when other possible
   discards and their triggered events are considered too.

Greedy also lost twice by playing Duck and Cover for Ops at DEFCON 2.
The observed terminal results match the corrected engine behavior; no new
engine defect was isolated by this batch. The above bot issues remain
unfixed in the tested revision.

Before spending more compute on country-value training, prioritize explicit
terminal-loss checks for event choices and play modes, then risk evaluation
for hand-dependent discard events. The neural regional correction inherits
these tactical weaknesses from StrategicPlayer.

## Evidence and reproduction

[Tracked results](../models/game-check-2026-09-08.json) include per-game
outcomes and the last 12 competitive decisions, including phasing-player
context. Full replay logs and the two ad hoc test drivers are retained in
the local, git-ignored `logs/game-check/` directory. Run the drivers from
the repository root with the project and test dependencies installed:

```bash
python logs/game-check/check_games.py
python logs/game-check/random_games.py
python -m pytest -q
```

The drivers are local diagnostic artifacts, not part of the committed test
suite. Existing replay APIs can load their `{seed, actions, ...}` JSON logs.
