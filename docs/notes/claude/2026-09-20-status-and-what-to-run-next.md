# Status on 2026-09-20 evening, and the four things to run

Written to answer three questions at once: where the bot stands, what to
dispatch next, and what is true that nobody has written down. Every reading
below is quoted from a run that finished; where a number is my arithmetic
over two runs rather than a paired arm, it says so.

## 1. The drift is closed, and the run that says so reads red

Run 35524331002 (drift, on `d9baa95` -- main with `vp_swing` 3.0), verdict
job green:

| anchor | score | one-sided 95% | on 2026-09-18 |
| --- | ---: | --- | ---: |
| v0.1.0 | 0.576 | [0.559, 0.593] | -- |
| v0.2.1 | 0.505 | [0.489, 0.521] | **0.470 DRIFT** |
| `bc5ef93` | 0.502 | [0.485, 0.519] | 0.483 |
| `07d553a` | 0.534 | [0.518, 0.550] | 0.520 |
| v0.3.4 | 0.508 | [0.493, 0.523] | -- |

**No anchor's upper bound is below 0.500, so the canary passes.** The
v0.2.1 row was the drift this project has been chasing since 2026-09-18,
and the bisect's two findings -- delete the region margin, restore the VP
curve at 3.0 -- closed it. That is the headline, and it is not in any note
yet.

**The run shows `failure` in the Actions list.** Two of the eight
`bc5ef93` shards failed, so the run-level conclusion is red while the
verdict step exited 0 on 1022 of 1024 seeds. Anyone scanning run
conclusions reads this as "drift still failing". It is the opposite.

**What the panel did not cover, now covered.** The 2026-09-18 reading had
*two* DRIFT rows, v0.2.0 (0.474) and v0.2.1 (0.470), and the five-anchor
panel carries only v0.2.1. Run 35539623005 dispatched `v0.2.0` alone on the
canary's own block, so the row is comparable with the rest:

    ok    v0.2.0: score 0.501 [0.485, 0.517] over 1024 seeds

Eight shards, all green, no stall, and the verdict exits 0. **Both former
DRIFT rows are closed**, and the whole 2026-09-18 finding is answered: the
region-margin deletion and `vp_swing` 3.0 recovered everything that was
lost between v0.2.1 and `07d553a`.

Note what "closed" means here and what it does not. v0.2.0 at 0.501 and
`bc5ef93` at 0.502 are *level*, not beaten -- the bot has caught up with
its own best past self rather than passed it. The only anchors HEAD leads
measurably are v0.1.0 (0.576) and `07d553a` (0.534). A canary that passes
says nothing was lost; it does not say anything was gained.

## 2. Levels are not comparable across blocks, and the notes compare them

"Main against `07d553a`" has five readings this week, all at 1024 or 512
seeds, all with the books pinned:

| block | arm | score |
| --- | --- | ---: |
| 44000-45023 | `margin-base` | 0.499 |
| 46000-47023 | `restore-base` | 0.522 |
| 6000-7023 | drift, today | 0.534 |
| 56000-56511 | `potential-round-base` | 0.541 |
| 54000-55023 | `sandbox-base` | 0.559 |

Main really did get stronger between the first and the last. But the spread
is 0.060 and the two readings taken on *the same code* -- 0.534 (drift) and
0.559 (sandbox), both post-`vp_swing`-3.0, three hours apart -- differ by
0.025, which is larger than every single gain measured this week except the
VP curve itself. At 1024 seeds the one-sided interval is about +/-0.016, so
two blocks can disagree by more than an accepted change is worth.

The paired differences are unaffected: that is the whole point of pairing,
and `+0.039 [+0.019, +0.059]` for `vp_swing` 3.0 stands. What does not hold
is the *level series*. The sandbox note's closing line reads main at 0.559
"where the same anchor read 0.499 before the region-margin deletion and
0.522 before `vp_swing` 3.0", and treats the 0.060 as the two changes
showing up together. Three blocks, three sentences, one number. The two
changes are worth +0.031 and +0.039 *by their paired arms*, which is the
evidence; the level series is consistent with it but cannot confirm it, and
0.025 of the 0.060 is attributable to block alone.

**The practice this points at:** quote a level only with its block, and
never subtract two levels from different blocks. If a level series is
wanted, one arm on one fixed block -- the drift canary already is that arm.

## 3. The fitted country weights are off, and the intransitivity is the
   most interesting open question here

`country_vp_scale` ships at **0.0**. The 2026-09-18 evening handoff says
"Decided: default flipped to 2.795" and PR #6 merged it; the revert and its
reason live in a comment on the field and in the fitted-weights note's last
section, not in the handoff. Anyone reading the handoff alone will believe
the fit is live. It is not.

The reason it was reverted is worth more than the weights are:

- Against the guessed tiers, head to head, the fit **wins**: 0.518 [0.502,
  0.534] over 1024 seeds.
- Against `07d553a`, paired against the tier bot on the same 1024 seeds,
  the fit **loses**: -0.031 [-0.053, -0.009], all of it in the USSR seat.

A change that beats the bot it replaces and loses to a bot from a week
earlier is the clearest statement this repo has that *beating the current
bot is not the objective function*. `experiments.yml`'s own header says
intransitivity is the thing under suspicion; this is a measured instance of
it, at 1024 seeds, with the seat named.

Both readings were taken on the 2026-09-18 bot -- before the region-margin
deletion and before `vp_swing` 3.0, the two changes that moved main's
anchored score most. So the intransitivity has never been re-read on the
current bot, and the fit has never been judged against the anchor it would
now be merged into.

There is also a mechanical suspect nobody has tested. The weights were
fitted on self-play positions from `598e4d1` (the file records
`source_revision`), which is a bot two structural changes ago. Weights
fitted on the positions one bot reaches need not price the positions
another bot reaches. That makes a refit -- not a rescale -- the next move if
the anchored reading comes back level.

## 4. Three registry defects, and the test that now gates them

`.github/experiments.json` is read by a runner and by nothing else, so
until today no test had ever looked at it.

1. **PR #24's head (`ef0dfd9`) carries conflict markers in the file** --
   `<<<<<<< HEAD` at line 465, `>>>>>>> origin/main` at 500, from the merge
   that resolved `.github/experiments.json`, `docs/notes/claude/README.md`
   and `models/provenance.json`. The file is not valid JSON. `tests.yml` is
   green on that head and the gate passed, because neither parses it; the
   first thing that would have noticed is `experiments.yml`'s `plan` step,
   on dispatch, an hour into an overnight run. **This one is still open and
   lives on PR #24's branch, not here.**
2. **`margin-off-vs-07d553a` was a null ablation.** It set
   `margin_presence`, `margin_battleground` and `margin_country` to 0, and
   the region-margin deletion removed all three fields.
   `StrategicWeights.load` drops unknown keys with an INFO log -- correct
   for an old model file, wrong for an ablation -- so the arm would have run
   as a byte-identical copy of `base-vs-07d553a` and reported under a title
   claiming the margin was off. The arm is deleted here: its question was
   answered when the term was.
3. **A partial seed-block overlap is staged.** The `sep20-*` arms on
   `experiment/paired-calibration-20260920` claim 56000-57023; the
   `potential-round-*` arms on PR #24's branch already spent 56000-56511
   against the same anchor. Arms sharing a *whole* block and an opponent are
   paired on purpose; arms sharing *part* of one look independent and are
   not.

`tests/test_experiment_registry.py` gates all three shapes: the file
parses and holds no conflict marker, every arm's weight names are live
`StrategicWeights` fields, seed blocks are identical or disjoint, and a
`compare_to` names an arm on the same block and the same opponent. It
caught defect 2 on its first run.

## 5. Where PR #24 actually stands

Its own bar was "this stays open until run 35531902621 reports". It
reported:

| arm | score | one-sided 95% |
| --- | ---: | --- |
| `potential-round-base` | 0.541 | [0.518, 0.564] |
| `potential-round-on` | 0.562 | [0.538, 0.586] |
| **paired** | **+0.021** | **[-0.009, +0.052]** |

512 seeds, not the 1024 the sizing note calls the default for a question
worth asking. The interval contains zero, so the term is **not measured to
help**; it is also not measured not to. The PR's three exact speedups and
its two new oracle tests stand on their own -- they are exactness work, and
the corpus reproduces -- so the decision the reading supports is: land the
speedups, leave `potential` and `potential_refresh` at 0.0, and either
extend to 1024 on a fresh block or stop. Extending is one dispatch; at 1024
the interval halves to about +/-0.021, which would separate +0.021 from
zero if it is real.

## What to run, in order

**1. Drift with `v0.2.0`. DONE** -- run 35539623005, `ok  v0.2.0: 0.501
[0.485, 0.517]` over 1024 seeds. See section 1. What is left of this item
is a standing one: add `v0.2.0` to `drift.yml`'s default panel, so the
anchor that was a DRIFT row for two days is watched rather than remembered.
The two `bc5ef93` shards that failed in run 35524331002 were not re-run;
that anchor read 0.502 on 1022 of 1024 seeds, which is not a reading worth
another 8 shards on its own.

**2. The `vp_swing` peak on one block. DONE** -- run 35539441015: nothing
beats 3.0, 4.0 misses a measurable loss by a thousandth, and the entire
spread is in the USSR seat. See
[the peak note](2026-09-20-the-vp-peak-on-one-block.md). Original text: 3.0 ships; 4.0 has never been
compared with it, because the grid was stitched from two blocks with two
different bases (46000-47023 for 1.5/2.0/3.0, 52000-53023 for 4.0/6.0).
Section 2 says how far apart two blocks can read. Four arms, one fresh
block, all paired against the shipped setting. Registered here as
`peak-one-block-{base,vp2,vp4,vp5}` on 60000-61023.

**3. The fitted-weight intransitivity, re-asked on the current bot.** Two
arms against `07d553a`, paired, on a block neither earlier reading used:
`fit-intransitive-{base,on}` on 62000-63023. A loss confirms the revert
against current code and closes it. A level reading says the intransitivity
was an artifact of the bot the fit was measured on, and points at the refit
(section 3) rather than at the scale.

```
gh workflow run experiments.yml --ref <this branch> \
  -f only=peak-one-block-base,peak-one-block-vp2,peak-one-block-vp4,peak-one-block-vp5,fit-intransitive-base,fit-intransitive-on
```

Six arms, 48 shards, 12,288 games -- an overnight run, and it does not
collide with anything staged. (`experiments.yml` requires each candidate's
`compare_to` base to be selected in the same run, which the list above
satisfies.)

**4. Step 6, the joint space/hold allocation.** The only item on this list
that is strength work rather than a weight, and the one with a denominator
already measured: 2.7% of seat-games reach a hand with no exit, **seven of
seven of them lost to DEFCON 1**, and corners account for 44% of all
nuclear losses. `scripts/measure_last_exit.py` is the before-and-after
instrument and the two numbers to watch are the corner rate and the tail
mass at 0.25 -- the corner count alone is too small a sample to move
visibly at 128 seeds. PR #22 records the maintainer's five rulings on the
design, including that the space slot can be *two* and that the second
opens mid-turn, which a pure matching cannot express.

Behind those, unchanged in priority by anything measured today: the
Late War table (18 of 22 cards unpriced, in the period most games end in),
and the DEFCON-3 survival prior, measured 2-4x too low.

## What this note is not

No experiment was dispatched for it. Sections 1, 4 and 5 are readings from
runs that had already finished and were not written up; section 2 is
arithmetic over five recorded levels; section 3 is what the source says
against what the handoff says. The four recommendations are arguments from
those, not results.
