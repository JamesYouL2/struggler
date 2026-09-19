# The drift has one boundary, between #100 of v0.2.1..v0.2.2 and v0.2.3

> **Superseded by the overnight results at the end of this note.** At 1024
> seeds on a fresh block the gap is 0.033, not 0.10, v0.2.3 is level with
> the plateau bot, every ablated feature is a gain, and the remaining loss
> is the DEFCON trap. The 128-seed series below is kept as the record of
> why the overnight run was designed the way it was.

2026-09-18. Fourteen drift readings: HEAD (`dc59c7d`/`8507eb9`, the same bot
code as v0.3.1) against each anchor, with the bot's own code snapshotted per
anchor, both seats on italy/austria, seeds 6000-6127 (128 seeds, one-sided
+/-0.04-0.05). Runs 35293091011, 35297109201, 35301305203. The reports are
in those runs' artifacts; the decomposition below was computed from them,
not from new games.

## The series

`#n` is the commit's position in `v0.2.1..v0.2.2` (167 commits).

| anchor | commit | HEAD vs it | HEAD nuked | anchor nuked | HEAD as US | HEAD as USSR |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| v0.1.0 | (own default board) | 0.504 | 24 | 23 | 0.531 | 0.477 |
| v0.2.0 | c9541ed | **0.402** | 32 | 15 | 0.441 | 0.363 |
| v0.2.1 | c0342e3 (#0) | **0.426** | 31 | 21 | 0.473 | 0.379 |
| #33 | 5951efd | **0.410** | 31 | 21 | 0.465 | 0.355 |
| #67 | a7418ef | **0.426** | 39 | 31 | 0.527 | 0.324 |
| #100 | 07d553a | **0.400** | 44 | 32 | 0.500 | 0.301 |
| #130 | a83ab52 | 0.471 | 32 | 21 | 0.582 | 0.359 |
| #159 | 930dfdc | **0.391** | 40 | 25 | 0.480 | 0.301 |
| v0.2.2 | 4813570 (#167) | 0.475 | 36 | 27 | 0.551 | 0.398 |
| v0.2.3 | 6570337 | 0.504 | 30 | 32 | 0.570 | 0.438 |
| v0.2.4 | 4f8170c | 0.504 | 30 | 32 | 0.570 | 0.438 |
| v0.2.5 | 2f445b3 | 0.490 | 29 | 29 | 0.555 | 0.426 |
| v0.3.0 | cad05cf | 0.502 | 35 | 35 | 0.613 | 0.391 |
| v0.3.1 | ca201da | 0.500 +/-0.000 | 29 | 29 | 0.621 | 0.379 |

Bold is DRIFT (upper bound below 0.500). The six-tag run was dispatched
before v0.2.4 and v0.2.5 were renumbered, so its job labels are swapped
against today's tags; the rows above are by commit.

Two rows are identical on purpose, not by a harness fault: v0.2.3 and
v0.2.4 differ only in the *default* opening, and drift pins the books, so
the two anchors play the same games. v0.3.1's zero standard error is the
same thing, since no bot code has changed since it. Both are the
`bug-shapes.md` shape-3 tell, and both are explained.

## What it says

- **One boundary, not a slope.** Every anchor up to v0.2.2 beats HEAD
  (eight of eight below 0.48; their mean is 0.425), and every anchor from
  v0.2.3 on reads level (four of four within 0.01 of 0.500). The readings
  inside the interval (0.471, 0.391, 0.475) bounce by more than the one
  standard error each carries, so at 128 seeds the step inside
  #100..#183 cannot be located, only bracketed.
- **The loss is mostly on the US seat.** Against the self-play baseline
  (HEAD as US 0.621, as USSR 0.379 against itself), the old anchors cost
  HEAD about 0.12 as US and 0.04 as USSR. Against v0.2.0 and v0.2.1, the USSR
  seat is level and the whole gap is US. The old bot's USSR beats HEAD's US.
- **DEFCON is part of it, not all of it.** HEAD loses 10-17 more games to
  DEFCON 1 than the old anchor does in every pre-boundary row and about 0
  more in every post-boundary row. That is the boundary exactly, but it is
  at most half of the gap: games that did not end in DEFCON 1 still score
  0.39-0.43 against the plateau.
- **The USSR seat nukes itself in every version.** HEAD as USSR loses to
  DEFCON 1 in 19-28% of its games (self-play included); as US, about 5-6%.
  WBC players lose 2.7-5.8% per player-game. This is not the drift (every
  version does it) but it is the largest single strength leak the reports
  show, and it is most of why italy/austria self-play gives the US 62%.

## The bot changes inside the bracket (#100 07d553a .. #183 v0.2.3)

| # | change | still in HEAD? | ablation |
| --- | --- | --- | --- |
| 130 | delete `first_mover` | deleted | needs the term restored on a branch |
| 137 | F6 Our Man in Tehran | yes (a rules fix) | none sensible |
| 151 | cap the redundant-access aggregate | yes | `access 0` bounds it from above |
| 154 | reply look-ahead honours legality | yes | `reply_model 0` |
| 159 | M2b: regional VP weighted by region urgency | yes, everywhere | needs a flag |
| 167 | the reply may be a Coup | yes | `reply_coup 0` (added 1020bcf) |
| 173 | two-state retention | no (`retention_p` has no caller) | none needed |
| 183 | deck-tracking rival urgency | yes | `scoring_rival 0` |

## Hypotheses, most likely first

1. **The parent-only gate cannot see this.** Every change in the bracket
   passed a gate against its parent at +/-0.03-0.05. The four gated merges
   from v0.2.2 to HEAD with recorded readings (deck-tracking 0.520,
   five-bucket 0.506, factor-2 0.543, audit fixes 0.482) sum to +0.05
   against their parents; HEAD against v0.2.2 directly reads -0.025. Either the
   noise added up (four intervals of +/-0.03 allow it) or the game is
   intransitive across bot versions: a change can beat the parent whose
   weakness it exploits and lose to a bot outside the lineage. The overnight
   `v0.2.3-vs-07d553a` arm tests transitivity directly. If this is right,
   the fix is to the process: gate against a fixed panel (parent plus one
   or two older anchors), not the parent alone.
2. **One change in the bracket costs about 0.1 on its own**, most likely one
   that re-prices every placement (Coup replies, M2b) rather than a rules
   fix. The paired ablations against 07d553a test the reachable ones.
3. **The DEFCON handling changed at v0.2.3.** The excess-DEFCON column
   switches off at exactly the boundary. That looks like a real mechanism,
   but it cannot be the whole gap (see above).

Architecture is the explanation to reach for only if every ablation reads
level against the old bot *and* the transitivity check passes. That would
mean the loss is spread across many terms, and no single switch undoes it.

## Overnight (run 35306328917): 1024 seeds each, seeds 20000-21023

Paired against `base-vs-07d553a` (HEAD as it is against the plateau bot):
`coup-reply-off`, `reply-off`, `rival-off`, and three simplifications
(`margin-off`, `access-off`, `final-off`). Location: `base-vs-v0.2.2`,
`base-vs-v0.2.3`. Transitivity: `v0.2.3-vs-07d553a`. Diagnostic:
`selfplay-defcon-logs` (128 seeds of HEAD self-play with every game's log,
to see which play the USSR seat loses DEFCON on).

## Overnight results (run 35306328917, all 81 shards, 1024 seeds each)

| arm | score | one-sided 95% | paired diff vs base |
| --- | ---: | --- | ---: |
| HEAD vs 07d553a (base) | 0.467 | [0.450, 0.484] | -- |
| HEAD vs v0.2.2 | 0.475 | [0.459, 0.491] | |
| HEAD vs v0.2.3 | 0.495 | [0.479, 0.511] | |
| v0.2.3 vs 07d553a | 0.501 | [0.485, 0.517] | |
| Coup replies off | 0.408 | | **-0.059** [-0.082, -0.037] |
| reply look-ahead off | 0.412 | | **-0.056** [-0.079, -0.032] |
| access off | 0.429 | | **-0.038** [-0.061, -0.015] |
| rival urgency off | 0.443 | | **-0.025** [-0.046, -0.004] |
| final scoring off | 0.448 | | -0.020 [-0.041, +0.001] |
| region margin off | 0.468 | | +0.001 [-0.022, +0.024] |

**The 128-seed series overstated the gap about threefold.** Every one of
those readings used seeds 6000-6127, so they shared one block's luck and
were not fourteen independent looks: 07d553a read 0.400 there and 0.467 on
20000-21023. A series of anchors on one seed block is correlated; its
agreement is not evidence of size.

**Hypothesis 2 is refuted.** Every ablatable change in the bracket is a
*gain* against the plateau bot, measured paired: Coup replies +0.059, the
reply look-ahead +0.056, access +0.038, rival urgency +0.025. Keep them all.
And v0.2.3 is level with 07d553a (0.501), so the bracket lost nothing.

**Hypothesis 1 is not established.** Transitivity predicts HEAD vs 07d553a
of about 0.496 from the other two readings; it measured 0.467. That is
about 1.7 standard errors, so a lean, not a finding.

**Simplification: the region-margin terms read +0.001.** Setting
`margin_presence`, `margin_battleground` and `margin_country` to zero is
level against the old bot at 1024 seeds. It is the one deletion candidate.

## The remaining loss is one DEFCON trap

HEAD self-play with logs (128 seeds, `selfplay-defcon-logs`): 36 of 128
seeds end in DEFCON 1, and **33 of the 36 are one mechanism**. The phasing
side plays CIA Created (25, the USSR) or Lone Gunman (8, the US, its
mirror); the opponent spends the event's Ops on a battleground Coup at
DEFCON 2; the phasing player is responsible (ARCHITECTURE.md, "DEFCON
responsibility"). In 35 of the 36 the bot had already logged "EVERY option
is a certain loss": it was cornered before the play, not choosing badly
at it.

In all 25 CIA games the USSR was **holding CIA Created when DEFCON fell to
2**. The US dropped it (a battleground Coup at DEFCON 3) in 17; the USSR's
own battleground Coup dropped it in 8, which is walking into its own trap.
CIA Created is 1 Op, so it can never go to the Space Race: its only exits
are playing it at DEFCON 3+, UN Intervention, or keeping a spare safe card
to hold it past the turn. `defcon.py` already prices it as lethal at
DEFCON 2 (`_event_risk`, via `coup_threat`); what it does not do is get rid
of it while DEFCON is still 3.

And it got worse after v0.2.3. Against the same opponent (07d553a, 1024
seeds): v0.2.3 as USSR loses 147 games to DEFCON 1, HEAD 196; v0.2.3 as US
pushes the old USSR into it 199 times, HEAD 170. About 78 games change
hands, roughly 0.038 of score, against a measured gap of 0.033. That is the
whole drift, within the noise.

**The fix is in the survival planner, not the value function:** hold a
card that is lethal at DEFCON 2 only when a safe exit survives the
opponent's measured chance of dropping DEFCON, and never Coup a
battleground at DEFCON 3 while holding one. Measure it on self-play
nuclear rate (21% of USSR games now; WBC humans 3-6%) and on a 1024-seed arm
against 07d553a paired with `base-vs-07d553a`.

## Update, evening: the first 1024-seed canary (run 35371538598)

`drift.yml` now reads every tag at 1024 seeds (PR #5). The first run
measured PR #4's hand-safety code, before the fitted weights, on seeds
6000-7023:

| tag | score | one-sided 95% |
| --- | ---: | --- |
| v0.1.0 | 0.541 | [0.524, 0.558] |
| **v0.2.0** | **0.474** | **[0.458, 0.490]** DRIFT |
| **v0.2.1** | **0.470** | **[0.453, 0.487]** DRIFT |
| v0.2.2 | 0.520 | [0.504, 0.536] |
| v0.2.3 / v0.2.4 | 0.548 | [0.532, 0.564] (identical: v0.2.4 changed no bot code) |
| v0.2.5 | 0.552 | [0.536, 0.568] |
| v0.3.0 | 0.549 | [0.534, 0.564] |
| v0.3.1 | 0.544 | [0.533, 0.555] |

- **The hand safety beat every tag from v0.2.2 on**, and `07d553a` too
  (0.520 on seeds 30000-31023).
- **It is still behind v0.2.0 and v0.2.1**, by about 0.03. `07d553a`
  sits between v0.2.1 and v0.2.2, so this remaining loss entered between
  v0.2.1 and `07d553a`. That is earlier than this note first placed it:
  the CIA Created trap masked it.
- Re-reading on main with the fitted weights (+0.018 against the tiers)
  against v0.2.0, v0.2.1 and 07d553a: run 35416380534. If the gap holds,
  bisect v0.2.1..07d553a with 1024-seed anchored arms.

