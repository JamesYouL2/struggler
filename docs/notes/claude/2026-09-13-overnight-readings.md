# Overnight 2026-09-12: what came back, and what was checked before reading it

The queues (`scripts/overnight3.sh`, `overnight4.sh`, `overnight5.sh`) and
the CI runs they collected wrote six generated notes, each of which says
plainly that nobody has read its numbers. This is the reading. Every
anomaly below was checked against the raw reports before being written
down; the interpretations are marked as such.

## 1. Early stopping held, and CI's games replay here

`2026-09-12-gate-without-early-stopping.md`, `2026-09-12-ci-games-replayed-locally.md`.

- The route-decay gate, every game played: **0.498 +/-0.020 over 128 seeds,
  ACCEPTED**. The curtailed run said 0.500 +/-0.027 over 84.
- All 168 games the curtailed run played came out identical in the full
  run, and 16 of them replayed identically on this machine.

One data point for audit F3, and it agrees. It does not calibrate early
stopping.

## 2. The route decay did not measurably lengthen games

`2026-09-12-selfplay-lengths-and-sandbox-stacks.md`. Paired self-play,
191 seeds: end turn **+0.17 +/-0.23**, 7.36 -> 7.53. `defcon_1` endings
40 -> 47, not resolved. The handoff's section 2 reading ("postponing the
same result") is not contradicted; nor is anything shown.

## 3. The Blockade recursion

See `2026-09-12-the-blockade-recursion-is-a-chain-of-fresh-helpers.md`.
A chain of fresh sandbox helpers, each with its own empty re-entry guard,
through `un_card`. 24 of 192 games. Fix proposed, not applied.

## 4. Conversion with F1 fixed barely moved at horizon 1

`2026-09-12-conversion-and-retention-after-f1.md`, 192 seeds.

| stability | 1 | 2 | 3 | 4 | pooled |
| --- | ---: | ---: | ---: | ---: | ---: |
| p, biased collector (handoff, 96 seeds) | 0.406 | 0.303 | 0.304 | 0.154 | 0.287 |
| p, horizon 1, F1 fixed | 0.408 | 0.301 | 0.288 | 0.151 | 0.281 |
| p, horizon 2 | 0.461 | 0.383 | 0.410 | 0.272 | 0.383 |
| ratio p2 / p1 | 1.13 | 1.27 | 1.42 | 1.80 | 1.36 |

Reading: F1's bias was small at horizon 1 -- the shipped `CONVERSION_P`
shape survives the fix -- but not zero at stability 3. The ratio p2/p1 is
not one constant: it rises with stability, 1.13 to 1.80. That is what 4d
asked. If the turn discount were derived from it, it would be a function of
stability rather than one `scoring_discount`. Horizon 2 is censored hard
(4705 opportunities still open at game end against 3966 resolved), and
censoring is heaviest in short games, so the horizon-2 row leans toward
long games. Retention: 0.811 at horizon 1, 0.730 at horizon 2.

## 5. The gate ladder: two findings and one contradiction

`2026-09-12-gate-ladder-since-05b6690.md`. HEAD `b721744` against eight
bases, 128 + 128 seeds, every game played. Score is HEAD's; above 0.500 is
HEAD better.

| base | HEAD scores | verdict |
| --- | ---: | --- |
| `05b6690` | 0.520 +/-0.028 | ACCEPTED |
| `9b90ef0` | 0.453 +/-0.031 | ACCEPTED (upper 0.504) |
| `c0ccd95` | **0.447 +/-0.027** | **REJECTED** |
| `bc5ef93` | 0.496 +/-0.027 | ACCEPTED |
| `52bb329` | 0.518 +/-0.023 | ACCEPTED |
| `c7ed9f5` | 0.498 +/-0.021 | ACCEPTED |
| `9a2b3c7` | 0.498 +/-0.020 | ACCEPTED |
| `f492dc3` | 0.498 +/-0.020 | ACCEPTED |

**Checked first: the identical readings are real, not shape 3.** Three bases
read 0.498 with the same nuclear-loss seeds. Per game, `9a2b3c7` and
`f492dc3` are identical on 256 of 256 and differ in bot code only by
`1aa122e`, a `cards.json` summary the strategic bot never reads.
`c7ed9f5` is identical on 250 of 256; the Europe Control fix between them
moved six games. Every other pair of bases agrees on 10-62 games, which is
what different bots look like. The two drift anchors reading identically
(0.486, same endings) is the same: `3955b3e..05b6690` changes nothing under
`src/struggler/bots` or `data`.

**HEAD is measurably worse than `c0ccd95`** (the Space Race ability pricing,
2026-09-11 21:46) -- the only rejection. Read with the next line, the loss
sits somewhere in `c0ccd95..bc5ef93..52bb329`; `bc5ef93` (deducing the
opponent's hand) is the one behaviour commit between the rejected rung and
the recovered one. A reading, not an attribution: the rungs differ by several
commits each and every difference is two scores of +/-0.03.

**The contradiction.** The 2026-09-12 bisect on drift seeds 6000-6127 found
`9b90ef0` about 8 points WEAKER than `05b6690`
(`2026-09-12-the-reshuffle-fix-cost-eight-points.md`). This ladder, on gate
seeds, finds it about 7 points STRONGER (0.520 against `05b6690`, 0.453
against `9b90ef0`). Both differences exceed their error bars. The difference
that stands out is the protocol, not the seeds: `drift_check.sh` passes no
`--vary-openings` (its line 58 -- an anchor older than the books cannot take
one), so every drift game starts from one book, while the gate varies the
book by seed. If the reshuffle fix hurts from the default opening and helps
across the book rotation, both readings are right and "the reshuffle fix
cost eight points" is a statement about one opening. **Untested**; the check
is one CI gate against `05b6690` and `9b90ef0` with `GATE_VARY=0`, or one
drift pair with openings varied.

**Stalls, silently absorbed.** Seed 4006, USSR seat, never finished under
either `c0ccd95` or `bc5ef93`; the `f492dc3` self-play arm lost seed 9178 the
same way. Acceptance judged the ladder rungs on 255 of 256 games without
saying so -- audit F4, in a real run. One game cannot flip the `c0ccd95`
rejection (it moves the pooled score by at most ~0.004), but the hang itself
is a defect in those revisions that nobody has looked at.

## 6. Ablations: two terms are load-bearing, five are not resolved

`2026-09-12-ablations-on-ci.md`. The arm's score against the shipped
weights, seeds 9400-9527 + 9528-9655; below 0.500 means removing the term
hurt.

| arm | score | seeds played | verdict |
| --- | ---: | ---: | --- |
| `progress` 2.8 -> 0.01 | **0.354 +/-0.034** | 77 | **REJECTED** |
| `reply_model` 3 -> 0 (forward search off) | **0.431 +/-0.028** | 124 | **REJECTED** |
| `coup_discount` 0.9 -> 1.0 | 0.526 +/-0.038 | 77 | ACCEPTED |
| `first_mover` 0.6 -> 0 | 0.526 +/-0.034 | 76 | ACCEPTED |
| `region` 1.3 -> 1.0 | 0.506 +/-0.028 | 81 | ACCEPTED |
| `margin_battleground`, `margin_country` -> 0 | 0.494 +/-0.023 | 198 | ACCEPTED |
| `scoring_hand` 1.2 -> 1.0 | 0.493 +/-0.017 | 212 | ACCEPTED |

"Seeds played" is pooled over both samples, out of 256 planned. Fewer is
early stopping, not stalls: `--decide` curtails once the unplayed seeds
cannot change the verdict. That is the
F3 caveat for every curtailed row here -- one full-sample check (section 1)
agreed; that is all the calibration there is.

Readings:

- **`progress` is worth about 15 points.** It is the term that bridges an
  investment the search cannot finish, and without it the bot collapses.
  Recorded `guess / underdetermined`; this bounds it from below.
- **The forward search is worth about 7 points with its defects in.** Audit
  Q1, Q2 and F5 are real bugs in something load-bearing, so the reply patch
  is worth more than a cleanup, and must be gated against `reply_model` on,
  not off.
- **`coup_discount` 1.0 and `first_mover` 0 both read 0.526**, lower bounds
  0.488 and 0.492. Not measurable improvements, and they curtailed at 77 and
  76 seeds, where early stopping has the least evidence. If either is worth
  pursuing, re-run it uncurtailed (`decide` is now a gate input; the
  experiments workflow still always passes `--decide`).
- **`margin_battleground`, `margin_country` and `scoring_hand`** ran long
  (198-212 seeds) and read within a point of 0.500 with the tightest
  intervals of the night: the nearest thing here to evidence that a guessed
  weight is inert.

## What this changes for tomorrow

1. Before any further drift reading is quoted: settle the openings
   contradiction (section 5). It decides whether the reshuffle-fix
   regression exists.
2. F3/F4 (audit): the stall that acceptance absorbed happened twice
   tonight.
3. The reply-model patch (Q1/Q2/F5), now known to be patching a 7-point term.
4. The Blockade guard fix with its test.
5. F2's capped access formula, priced from section 4's F1-fixed `p`.
