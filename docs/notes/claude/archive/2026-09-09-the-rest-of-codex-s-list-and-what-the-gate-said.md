# 2026-09-09 — The rest of Codex's list, and what the gate said

Done in the order that makes later changes cheapest, not in the order of
severity. Every behaviour change below was gated on both seed ranges.

| Commit | Change | Pooled score, 96 seeds |
| --- | --- | ---: |
| `7750aff` | the gate's exit status is the verdict | infrastructure |
| `b5466cc` | say when an event value is a broken estimate | no value change |
| `8680865` | simulate the two dice-contest events | 0.495 +/- 0.014 |
| `e9cd991` | cap the scoring horizon, price the game's end | 0.503 +/- 0.028 |
| `56f793d` | nuclear losses judged against their rate | infrastructure |
| `40726d0` | one Ops estimate, not two | 0.542 +/- 0.034 |

The last is the best result of the session and the only one positive on both
samples independently (0.531 tuning, 0.547 held out). It is still not
significant: the lower bound is 0.486. Do not claim it as a strength gain.

### Two things the session got wrong first

**Timing while a gate runs.** These notes already warned about this, and I
did it anyway: the Ops change looked like a 3x slowdown (419 s against 125 s
on the suite) while a 192-game gate had the machine. On a quiet machine it is
12.5 s against 13.6 s, slightly *faster*. Never time anything while a gate
runs; the numbers are worthless, not merely noisy.

**`pytest` and stale bytecode.** Toggling `VALUE_RADIUS` between 2 and 3 with
`sed` changed one character, so the source kept its size, and with the mtime
inside the same second CPython reused the `.pyc` from the previous value. A
test then failed against source that was already correct. If a one-character
edit produces an impossible result, clear `__pycache__` before believing it.

### Still open, from Codex's list

Flag-only events (NATO, NORAD, Warsaw Pact Formed, Nuclear Subs, Quagmire,
Bear Trap) still value 0: the sandbox measures influence and immediate VP,
and a persistent effect is neither. Left alone deliberately, as it needs
expert judgement about what those effects are worth rather than a mechanical
fix. Formosan Resolution and Shuttle Diplomacy came off this list once
scoring took the overrides -- see below -- because what they change is a
number the bot already computes.

`FINAL_SCORING_ODDS` is measured from this bot's own games and is a generous
proxy for expert play. Codex has tournament statistics; replacing the table
is one line, and `scripts/game_endings.py` recomputes the bot's own
distribution to compare against them.
