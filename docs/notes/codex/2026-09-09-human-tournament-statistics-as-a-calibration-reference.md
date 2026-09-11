# 2026-09-09 — Human tournament statistics as a calibration reference

Internet research found useful tournament outcome data, but no verified,
ready-to-use tournament dataset of per-card event-versus-operations
frequencies. Use the available data as an advisory diagnostic, not a target
distribution the bot must imitate or a replacement for the strength gate.

### Sources and observed outcomes

The official [WBC 2024 report](https://www.boardgamers.org/yearbook24/tws.html)
and [WBC 2025 report](https://www.boardgamers.org/yearbook25/tws.html) provide
the following counts. Percentages are calculated from all reported games,
including resignations and games with an unreported ending type.

| Ending | WBC 2024: 56 games | WBC 2025: 60 games |
|---|---:|---:|
| Automatic victory before final scoring | 24 (42.9%) | 27 (45.0%) |
| Final scoring | 19 (33.9%) | 6 (10.0%) |
| Wargames | 6 (10.7%) | 6 (10.0%) |
| DEFCON 1 | 3 (5.4%) | 7 (11.7%) |
| Resignation | 4 (7.1%) | 8 (13.3%) |
| Unreported | 0 (0%) | 6 (10.0%) |

Both events used a nonstandard half-point China Card tiebreaker. Preserve
the reports' broad "automatic victory" category rather than silently
equating it with VP-track victories alone. The large year-to-year variation
also argues against treating either small sample as a universal target.

The [BPA 2026 Round 4 results](https://twstourney.wordpress.com/2026-round-4/)
record individual games with side, bid, ending type and turn, including VP,
Wargames, DEFCON, Europe control and final scoring. These round tables are
a promising source for a cleaned multi-round ending-turn dataset. They
were inspected, not yet imported or validated as a complete dataset.

For card usage, ACTS journals are a possible extraction source: card plays
and accompanying action descriptions can support reconstruction, but the
descriptions require interpretation. See the
[Vassal discussion explaining ACTS journals](https://forum.vassalengine.org/t/twilight-struggle/10848).
No consistently covered downloadable tournament action corpus was verified.

### Initial comparison with an existing bot benchmark

Inspected `logs/game-check/gate-9d9890f/full-vs-base.json`, containing 64
games of that revision against its baseline:

- VP-track endings: 45/64 (70.3%).
- Final scoring: 17/64 (26.6%).
- Wargames: 2/64 (3.1%).
- DEFCON: 0/64.
- Ending turns: T4: 4, T5: 6, T6: 8, T7: 2, T8: 3, T9: 6, T10: 35.

Thus 35/64 games ended on turn 10, which is not the same as reaching final
scoring. This is an older bot-versus-predecessor sample, not a measurement
of the current working tree. Opponents, rules and human resignations make
the tournament comparison non-equivalent. The lower Wargames frequency is
a reason to inspect missed opportunities and timing, not evidence that its
weight should simply be increased. Zero bot nuclear losses should not be
"calibrated" upward to match humans.

### Proposed use without MCTS

1. Add behavioral reporting to games already run by the gate: ending
   turn/reason, side, scoring-card timing and each card's chosen use. This
   requires instrumentation, but no additional games or search.
2. Separate headline events, voluntarily chosen action-round events,
   opponent events triggered alongside operations, space attempts,
   discards and held cards. A single "percentage evented" confounds
   preference with forced execution. Compare individual cards by side and
   turn, with explicit denominators and eligibility/availability where
   observable; do not infer unseen hands from aggregate result records.
3. Use human/bot differences to choose investigations and regression
   positions: missed Wargames opportunities, unusual scoring timing, or
   cards consistently valued differently. A mismatch poses a question;
   it does not establish a strategic error.
4. With a sufficiently clean dataset, use ending-turn records as a rough
   prior for reaching future scoring opportunities. Position-level records
   would allow conditioning on current turn, VP and board state. Do not
   apply an unconditional game-length distribution as though every current
   position has the same remaining horizon.
5. Keep cohorts comparable by rules, optional cards, starting bid/bonus,
   player strength and tournament format. Treat resignations, timeouts and
   missing outcomes separately; removing them can itself introduce bias.
   Reserve independent games/tournaments for validation if these data are
   used to select parameters.

Recommendation: build an advisory human-reference diagnostic alongside the
gate, then use it to prioritize targeted evaluator fixes. Matching human
aggregate frequencies is not proof of strength, and human error rates are
not desired bot behavior. No bot code, weights or gate thresholds were
changed as part of this research or its documentation.
