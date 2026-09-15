# 2026-09-15 — Italy default opening (swap from iran), plus handoff

Branch `experiment/opening-italy-default` off `origin/main` (`35182ef`).
Per the maintainer's call: the default US opening moves from `iran`
(4 West Germany / 3 Italy / Iran to 3) to `italy` (4 West Germany /
4 Italy / Iran to 2 — Sankt's 4/4/2). USSR stays `austria`. `france`
and `iran` remain available as books.

## Commits (all pushed)

- `e7cfff5` — the swap: `DEFAULT_OPENINGS` in `policy.py`, the default
  test in `tests/test_openings.py`, and the opening bullet in
  `docs/STRATEGIC_AI.md` (binding contract, same commit).
- `74f27e2` — corpus recapture on the new default, seeds 4000-4003
  (474 records, up from 431 — the italy games run longer).
- `501c1f3` — second pin on the old board found by the suite, not by
  grep: `test_opening_book_plays_the_standard_setup_and_the_handicap`
  in `tests/test_strategic.py` asserted `us[7:] == ['Iran', 'Iran']`
  and Iran at 3. Now `['Iran', 'Italy']`, Italy at 4, Iran at 2.

## Verification

- Targeted: `tests/test_openings.py` 27 passed.
- Full suite green: 861 passed, 3 skipped, 1 xfailed in 9:34
  (`logs/suite-italy-2.log`, `exit=0`). The 861 vs 862 elsewhere is
  expected: this branch is off `main` without the deck-tracking test.
- Ruff: 55 errors before and after the swap, all pre-existing — nothing new.

## Gate (running at time of writing)

`34997791463` on `experiment/opening-italy-default` vs `35182ef`,
`decide=0 vary=0`. Verdict to be appended.

Caveat for the reader of that verdict: the remote gate pins
`iran/austria` for both arms (`GATE_BOOKS` default in `scripts/gate.sh`,
no workflow input to override), so it is a no-regression safety gate —
it cannot measure the swap itself. Measuring the swap wants a local
`GATE_OPENINGS=` empty run (each revision its own default) or
`scripts/opening_tournament.py`. The `merge to main` request is held
until the gate ACCEPTs.

## Other runs (status at ~09:55 PDT)

- Joint gate `34987717417` (`experiment/scoring-five-bucket`):
  completed `success`. Merge still wants its ACCEPTED line from the log
  confirmed and the verdict appended to
  `2026-09-14-scoring-buckets-and-removals.md`.
- Drift `34983574990` (same branch): completed `failure` — drift was
  called on some anchor. Pull the log before merging that branch.
- Deck-tracking gate `34990361093`: still `in_progress` at time of writing.

## Next

1. Read gate `34997791463`. On ACCEPT: merge `--no-ff` to `main`,
   append verdict here. On REJECT: the corpus and tests already pin
   the new default, so a reject is about the books, not the plumbing.
2. Decide the measuring run: local each-own-default gate, or the
   opening tournament (italy vs iran as *positions*, independent of default).
3. Deck-tracking and five-bucket merges each still need their own verdict
   confirmed first — three branches, three verdicts, no bundling.
