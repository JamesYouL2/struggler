# 2026-09-09 (night) — Audit: the gate, the bot's speed, its strength, and what is off those three lists

Asked for: how to speed up the gate, how to speed up the strategic bot, how
to make it stronger, and anything important that is none of those. Written
against `df29bf8`, with `c15a603` (Codex's audit of the same revision) read
afterwards; the two are compared at the end.

What is *not* behind this section: no fresh profile of my own. A gate held
the machine for the whole audit (load 17 on 8 cores), and this file's own
rule is that a timing taken next to a gate is worthless. The step budget
below is from the gate's own records, which are wall-clock-honest about
themselves whatever else was running; the cProfile numbers quoted are
Codex's.

### The gate is not slow where either of us guessed

`gate-df29bf8`, 8 workers, 151 finished games, from the directory's mtimes
and the reports' own per-game seconds:

| Step | Wall | Share |
| --- | ---: | ---: |
| 1 + 1b, turn-1 table and the expert diff | 2 s | 0.1 % |
| 2, turn-3 checkpoint (64 games) | 67 s | 4 % |
| 3, full games (151 games, 12,282 CPU-seconds) | 1,595 s | 96 % |

The pool is not starved: 12,282 CPU-seconds over 8 workers is 1,535 s ideal
against 1,595 s actual, 96 % efficiency, and that is *with* one 551-second
game in the tail. So three of the speedups that suggest themselves from
reading `gate.sh` are worth nothing measurable. Running steps 1 and 1b
concurrently with step 3 saves two seconds. Folding the turn-3 checkpoint
into the full-game workers -- which I proposed before measuring, and which
`c15a603` calls "the next cheap speedup" -- saves 4 %. Worth doing as
tidiness, not as a speed programme.

The gate is 151 games of this bot and essentially nothing else. **Bot speed
is gate speed**; they are one item on the list, not two.

### Per-game seconds have drifted 2-3x in two days, and nobody attributed it

`mean_game_seconds` from each gate's `full-vs-base`, in commit order:
~13-15 s across the Sept 8 morning gates (`f123625` 13.2, `50e8bff` 13.4,
`873d9d9` 14.0, `c5446e0` 14.8, `1a03954` 15.5), then 25-36 s for every gate
of Sept 9 (`7cb9fbe` 31.9, `ec48dfa` 36.4, `b375ae5` 33.1), and 82.5 s for
`df29bf8` under contention.

Two candidate steps, neither attributed: `6ec71d4` (VP priced in Ops, which
puts an `ops_value` call underneath every VP price) with `4e67bf0` (sandbox
dice averaging, which forks the engine per die face) at the first jump, and
`7cb9fbe` (the two stale memos removed -- correctly; that commit bought
correctness and paid for it in time) at the second. Codex's cProfile at
`df29bf8` independently puts `ops_value` at ~31 s cumulative of 107.8 s,
which fits the first candidate. `ops_value` *is* cached per decision
(`_ops_values`), so this is cache misses across decisions and sandboxes, not
naive recomputation -- do not "fix" it by adding a cache that is already
there.

Attribute it with `scripts/profile_baseline.py` on a quiet machine before
optimising anything. A 2x recovery here is a 2x gate, which is worth more
than every structural change to `gate.sh` combined.

### What the gate can see -- and the arithmetic I got wrong first

I first computed the gate's standard error over individual games and got
0.041 at 150 games. That is wrong, in the direction that flatters the
gate: both seats of one seed play the same deal, so a seed is one
observation and not two, which is exactly what `benchmark.seed_scores`
already does and what the docstring there already says. Over the 2,315 seed
pairs in the recorded reports the seed-score SD is 0.24.

| Seed pairs | Games | SE | Regression blocked at 80 % power |
| ---: | ---: | ---: | ---: |
| 32 | 64 | 0.042 | 0.105 |
| 96 | 192 | 0.024 | 0.061 |
| 150 | 300 | 0.020 | 0.049 |
| 500 | 1,000 | 0.011 | 0.027 |

So the full 96-seed gate blocks a 6-point regression four times in five, and
is blind to 3 points in either direction. `df29bf8`'s own gate reported
+/- 0.009 because that change left most seeds identical: the error bar adapts
to how much the candidate actually moves play, which means it is tightest
exactly when the answer matters least.

The consequence for how this project spends its day: 49 commits landed on
Sept 9, most separately gated at ~28 minutes each. That bought *attribution*,
not evidence -- at 32-64 seeds nearly every one of them was unmeasurable by
construction. Batching related changes into one 300-game gate and bisecting
only on a failure costs less wall time and sees more. Keep per-commit gating
for changes expected to be large, and for anything touching the DEFCON
planner.

`gate-df29bf8` verdict, for the record: **ACCEPTED**, pooled 0.500 +/- 0.009
over 76 seeds, stopped early at 76 of 96. One candidate nuclear loss (seed
4003 USSR T6) to replay, and one *opponent* nuclear loss at seed 4003 US T6,
correctly not counted.

### Strength: the expert table's misses are mostly one missing quantity

23 misses at `df29bf8`. The large ones are not independent: France ranks
below Egypt, Pakistan and Iraq in the US placement order; Vietnam Revolts
-1.17 against -4.00; De-Stalinization -4.94 against -7.00; De Gaulle -0.80
against -2.00; Suez -1.23 against -2.50. Adjacency into *empty* countries,
the liability of a lone point, and what a coup takes back are one quantity,
and the term for it (`wipe`, `wipe_backed`) is coded and ships at 0. Plan
step 2 is still the highest-value strength work in the file, and it is the
one the expert table is already instrumented to score.

After it, in order:

1. **The 32-seed MCTS run.** Scoring-turn MCTS scored 0.75 against the plain
   policy on 8 games after the three semantic fixes. That is the only large
   unconfirmed number in this file, it is ~25 minutes, and it decides
   whether a native port is worth considering at all. Do it before any
   further Rust discussion.
2. **Scoring-card timing** (plan step 5): an urgency multiplier is not a
   plan, and seed 3003's Asia Scoring at -6 with no Asia presence is the
   standing reference failure.
3. **Fit weights to the expert table, not to games.** The trainer has never
   found a strict improvement, and the reason is arithmetic: its fitness has
   an SE of 0.04-0.06 against effects of 0.02-0.05. It cannot see what it is
   selecting for. The expert table is a one-second fitness function that
   can, and the gate then checks the result rather than searching with it.

### Three things off those three lists

**Every strong opponent is this bot.** Greedy scores 1.00 against it,
`event_value` and MCTS are strategic underneath, and the gate asks only
"does it beat yesterday's self". Nothing in the loop would notice the whole
line drifting away from strong human play; the expert table is the sole
external reference and it is ~30 rows on one board. The cheapest fix is to
extend it to annotated positions drawn from the parity corpus -- a tactics
suite scored the way the opening table is -- which doubles as the fitness
function item 3 above needs.

**Rules churn is invisible to the gate by construction, and 16 cards are
untested.** About a dozen rules fixes landed on Sept 9. `gate.sh` snapshots
only `src/struggler/bots`, so a rules change puts identical players on both
sides and returns exactly 0.500; the tests are the only thing standing under
those commits. These 16 of 110 cards are named nowhere under `tests/`:
Romanian Abdication, Nuclear Subs, Kitchen Debates, Cultural Revolution,
Flower Power, Colonial Rear Guards, Latin American Death Squads, OAS
Founded, Shuttle Diplomacy, Liberation Theology, Alliance for Progress,
Iranian Hostage Crisis, The Iron Lady, Reagan Bombs Libya, Iran-Contra
Scandal, Iran-Iraq War. A per-card pass against `docs/RULES_SOURCES.md`
belongs before more value tuning is stacked on top of them.

**The parity corpus is red and stale, and it is the oracle for what comes
next.** Every caching or indexing change is verified by it. Regenerate it in
its own reviewed commit (the ranking changes behind the failure are measured
and intended) before touching the evaluator again, or the next memo bug --
there have been three -- lands without a detector.

A fourth, smaller: these notes are 337 KB across two files and the open list
now lives in four separate sections. Whoever picks this up next pays an hour
to find out what is open. One short state-and-open-list page, rewritten
rather than appended, would pay for itself immediately.

### Where this differs from Codex's `c15a603`

Agreement on the substance: the risk and sentinel fixes are good, the corpus
should be regenerated separately rather than treated as evidence against
them, `LOSS` wants an explicit terminal-outcome type rather than sentinel
plumbing, `StrategicWeights` should separate its active tuning set from
compatibility and disabled fields, and no native port before the repeated
work is measured against a frozen Python reference.

Three differences, all of them measurement rather than opinion:

- Codex calls folding the turn-3 checkpoint into the full-game workers "the
  next cheap speedup". Measured, it is 4 % of the gate, and steps 1 and 1b
  are 0.1 %. The gate's cost is per-game CPU times 151, and nothing else.
- Codex proposes caching the repeated `discard_risk` / coup-target / `delta`
  work with full state keys. Right in principle, and this file's history
  says the risk is real (three memos have shipped keyed on less state than
  they read). But the corpus that would catch a fourth is currently red, so
  the order is corpus first, cache second.
- This section of Codex's notes does not raise an external strength
  reference, the untested cards, or the gate's statistical power. (It has
  asked for varied opponents before, under "benchmark reuse", so the first
  is a difference of emphasis rather than of view.) I think the power
  arithmetic changes how the day should be spent -- batch the gates, buy
  seeds with the savings -- more than any single item on either list.

Codex also covers ground I did not, and it is worth keeping rather than
merging away: the `LOSS` sentinel wants a real terminal-outcome type, the
26 weight fields want their active tuning set separated from the
compatibility and disabled ones, `coup_discount=1` is a clean isolated
ablation, and the MCTS leaf parameters should be split from the rollout and
proposal parameters before anything tunes them together. Those belong with
`docs/STRATEGIC_SIMPLIFICATION.md`, which is where the weight-by-weight
argument already lives.

Neither audit found a new correctness defect in the risk fixes.

### Codex reviewed the section above, and corrected two of its claims

`CODEX_NOTES.md` "Review of Claude's night plan", written against the
uncommitted section above. Broad agreement, and it accepts the 4 % finding
that demotes the checkpoint fold. Two of my claims do not survive, and both
corrections are confirmed here rather than taken on trust:

- **"96 % pool efficiency" is close to a tautology, and is withdrawn.**
  `benchmark.play` times a game with `time.time()` (`benchmark.py:203,227`),
  so the per-game seconds are elapsed worker occupancy, not CPU. Summing
  them and dividing by the worker count measures how busy the workers were,
  which under contention inflates with the contention and returns ~1 by
  construction. What survives is the step budget itself, which comes from
  directory mtimes and is real wall clock: 2 s, 67 s, 1,595 s. Step 3
  dominates and the checkpoint fold is worth 4 %; the pool efficiency claim
  and the "2-3x code slowdown" both need controlled, quiet-machine
  comparisons before anyone believes them.
- **"16 cards are untested" overstates it.** Codex names behaviour tests for
  Nuclear Subs, Flower Power and Shuttle Diplomacy that my grep missed
  because it searched for literal card IDs and the tests spell them
  differently or drive them through effect flags. Checked: those three are
  mentioned in 4, 2 and 4 test files respectively. Iran-Iraq War, OAS
  Founded and Kitchen Debates appear in one file each, which may be an
  incidental mention rather than a behaviour test. The real question is
  coverage of activation, resolution, interaction and expiration separately,
  and no grep answers it. Treat 16 as an upper bound on a number nobody has
  measured yet.

Codex's other three qualifications stand and are adopted: the wipe term is
a hypothesis rather than the proven cause of the clustered expert-table
misses (empty-country access, event vulnerability and coup vulnerability
overlap but are not the same mechanism); batching gates should keep
distinct strategic hypotheses independently measurable, since a failed
batch of interacting changes does not bisect cleanly; and the MCTS run
should record root visits and truncation and compare equal wall-time
budgets as well as equal simulation counts.

Its revised sequence -- green baseline, controlled profiling, the 32-seed
MCTS run, tactics suite and a real coverage audit, then optimisation with
wipe and coup-discount tested independently -- supersedes the order I gave
above. The one thing I would keep from mine is that the gate's power is a
reason to batch *validation*, not a reason to stop attributing changes.
