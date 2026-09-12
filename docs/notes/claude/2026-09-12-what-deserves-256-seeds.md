# What deserves the 256-seed ceiling: `battleground`

> **SUPERSEDED, same day.** The diagnostic this note put first was run, and
> it retired the experiment this note proposed. At the shipped weights a
> Battleground reads 4.05 VP at T5 and 4.00 at T7 -- the maintainer's figure
> -- against the 2.05 that made `battleground` known-wrong, and the decay
> from T3 is 1.08x rather than 2.66x. The flat VP curve closed it. See
> `2026-09-12-the-flat-curve-fixed-the-battleground-level.md`.
>
> The reasoning below stands and is why the answer was cheap: a ceiling on
> sample size is only half the discipline, and the other half is asking
> whether the question needs games at all. This one did not. The 256 is
> unspent and free for the next thing.

Sample sizes are now 128 by default and 256 as a hard ceiling, enforced in
`scripts/lib/queue_common.sh` rather than asked for. 128 is where early
stopping starts working at all (`ACCEPTANCE['min_games']` is 150 pooled
games, so an 80-seed run has ten games of slack and saves 4%, measured).
256 is where the clock stops buying resolution: +/-0.056 at 128, +/-0.040
at 256, and +/-0.028 for four and a half hours at 512.

So the ceiling is a budget, and it should be spent on the term that is
both **wrong** and **load-bearing**. That is `battleground`.

## It is the only weight recorded known-wrong

`models/provenance.json` rates all 31 strategic weights on source and
determination. Twelve are `guess / underdetermined`. Exactly one is
`known-wrong`:

    battleground   5.0   guess / known-wrong

"Known-wrong" in that file means measured and found not to match. The
recorded symptom: a turn-4 Battleground prices at **2.05 VP against the
maintainer's ~4**, and the mismatch grows across the game -- a Battleground
falls from about 3.5 VP to about 1.3 VP while the maintainer's reading says
it should hold up.

`2026-09-11-vp-base-cannot-fix-the-battleground-level.md` establishes that
the obvious knob cannot fix it: `vp_base` is a constant factor, so it moves
every turn equally, and the setting that puts turn 4 at 4 VP puts turn 1 at
6.8. The shape is the problem, not the level, and that note names
`battleground` as the likely culprit.

## But today changed the arithmetic, and the diagnostic must come first

The recorded mismatch is that `vp_value` grows about **3.4x** across a game
while a Battleground's `delta` grows about **1.28x**, so Battleground VP
decays by roughly 3.4 / 1.28 = **2.66x**.

`vp_value` is `per_vp(turn) * ops_value(1)`, and `per_vp` is
`vp_base * vp_swing ** ((turn - 1) / 9)`. At the old `vp_swing = 2.0` that
first factor grew exactly 2.0x on its own, so the measured 3.4x implies
`ops_value(1)` grew 3.4 / 2.0 = **1.70x**.

Shipping `vp_swing = 1.0` today makes `per_vp` constant. So the same board
now gives:

| | old (`vp_swing` 2.0) | new (`vp_swing` 1.0) |
| --- | ---: | ---: |
| `vp_value` growth across the game | 3.4x | **1.70x** |
| Battleground `delta` growth | 1.28x | 1.28x |
| implied Battleground VP decay | 2.66x | **1.33x** |

**The decay halves.** A Battleground that fell ~3.5 -> ~1.3 VP should now
fall ~3.5 -> ~2.6. That is most of the recorded defect, closed as a side
effect of a change made for a different reason -- which is what you expect
when two parameters were modelling the same effect and one of them was
deleted.

**This is arithmetic from published figures, not a measurement.** It
assumes `ops_value(1)`'s 1.70x is unchanged by the weight change, which is
true by construction (`vp_swing` does not enter `ops_value`) but the 3.4x
and 1.28x are themselves approximations from one earlier run.

## So the order is: diagnostic first, and only then the 256

1. **Re-run `scripts/board_vp_by_turn.py` at the shipped weights.** It reads
   corpus positions and costs **no games at all**. It measures both halves
   -- what a Battleground is worth by turn, in Ops and in VP -- and it
   settles whether the level problem survived `vp_swing = 1.0`. This should
   happen before anything is queued.
2. **If the level is still wrong, `battleground` gets the 256.** It earns
   the ceiling on three counts that nothing else in the file combines:
   it is the only known-wrong weight; it is the term every other board
   value is priced relative to, so an error in it biases everything
   downstream rather than one decision; and a level change is exactly the
   kind of large effect worth *resolving* at +/-0.040 rather than merely
   gating at +/-0.056.
3. **If the diagnostic says it is fixed**, the 256 is free for the next
   thing and this note should record that the fix came from `vp_swing`.

The general shape here is worth keeping separately from the answer: the
expensive measurement was nearly queued against a target that a cheap
corpus diagnostic may have already resolved. A ceiling on sample size is
only half the discipline; the other half is asking whether the question
needs games at all.
