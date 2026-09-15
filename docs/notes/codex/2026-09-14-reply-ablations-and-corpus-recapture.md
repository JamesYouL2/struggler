# 2026-09-14 — Reply-layer ablation gates and corpus recapture

## Where main stands

- `930dfdc` merged `fix/board-potential-m2b` (M1 + M2b, gate-backed).
- `2ae0907` docs: run logs go under `logs/`, not `/tmp` (AGENTS.md).
- `836f21b` test(corpus): recapture at `2ae0907`, seeds 4000-4003. Tree
  clean, in sync with `origin/main`.

## The four reply arms (all pushed, all gated)

`553cd14` shipped the Q1/Q2/F5 reply fixes as one unit, so the splits are
leave-one-out ablations. B (coups as replies) is the one addition, ported
without the rejected A stack.

| Arm | Branch / tip | Ablation | Targeted verification |
| --- | --- | --- | --- |
| B | `experiment/reply-coup-only` / `4e8d144` | opponent may answer a placement with a coup (`_coup_reply`) | 303 passed |
| no-q1 | `experiment/reply-no-q1` / `355151e` | no reach/Chernobyl check (`if need <= 0`) | 296 passed, 1 xfailed |
| no-q2 | `experiment/reply-no-q2` / `687d237` | flat retake `need * influence_cost` (1pt needs 4 not 3, 2pt 6 not 5) | 296 passed, 1 xfailed |
| no-f5 | `experiment/reply-no-f5` / `4d45f4e` | horizon `None -> 0`, always charges (all 9 turn-order cases) | 296 passed, 1 xfailed |

Zero new ruff findings on every arm (3 pre-existing, same as main).
Each arm re-pins `tests/test_reply_lookahead.py` to its measured ablation
behaviour; the gate verdict is the ship criterion, not the re-pinned tests.

Gates (all `decide=0 vary=0`, base `930dfdc`):

- B: run `34913877037`
- no-q1: run `34913881138`
- no-q2: run `34913885256`
- no-f5: run `34913888786`

The gates predate the corpus recapture, which is fine: they play games and
never read the corpus, and `930dfdc..836f21b` touches no `src/` file, so
the bot comparison is unchanged.

## Corpus post-mortem (why main was red)

The merge suite failed `test_parity_corpus.py` with 625 ranking mismatches
on clean `930dfdc`. Diagnosis: the M2b recapture (`3e49e36`) carries
`source_revision 618c0455` -- it was captured at an intermediate experiment
commit and went stale as the branch evolved. `git diff 3e49e36..930dfdc`
over `src/` is only the behaviour-preserving SIM103 refactor, so the corpus
was already stale at the branch tip, not broken by the merge.

Fix: regenerated on current main -- 429 positions (was 562; shorter games),
parity green (4 passed). Capture log:
`logs/corpus-recapture-20260914/capture.log`; verify log:
`logs/corpus-verify-20260914/pytest.log`.

## Pending

1. Four gate verdicts (~40-90 min each from 00:36 UTC).
2. Ship decisions per arm from the verdicts.
3. The experiment branches were cut at `930dfdc`; they need a rebase onto
   `836f21b` (corpus-only delta, no bot change) before merging anything.
