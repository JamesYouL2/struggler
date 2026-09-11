# Option C, step 1: the parity corpus

`scripts/capture_corpus.py` plays strategic-vs-strategic on seeds
4000-4003 and records, at headline, action-round, play-mode, Ops-type,
placement and coup decisions on turns 1/3/5/7/9 (rounds 1/3/6), the
serialized engine plus the current outputs: the full ranking with safety
keys, every country value, region scores and margins, the Ops scale, and
the planner's whole-hand, per-card and event risks. 455 positions,
`tests/corpus/positions.json.gz` (250 KB). `tests/test_parity_corpus.py`
rebuilds each position with a fresh bot and requires exact rankings,
values within 1e-9 (absolute and relative) and identical risks; it runs
in ~15 s. Regenerate only by an explicit commit.

Capturing it found a leak: `_event_basis` (the sandbox's per-country and
per-region values for the current board) was keyed on influence alone and
survived across decisions, so a headline's basis, computed with the
headline's scoring weights, priced the events of the following action
round when the board had not changed. Reset per `rank_actions` now; the
corpus was captured after the fix. Fresh baseline on the gate snapshot:
see the gate report for the commit (`mean_game_seconds`).
