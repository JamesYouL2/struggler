# 2026-09-10 — MCTS does not replicate, and Military Ops needed a discount

### The 32-seed MCTS run: 0.75 does not replicate, and the search is too thin to be one

Codex and I both wanted this before any native-port discussion, because the
port's whole case rested on one 8-game reading of 0.75. Run at `5a2f3bb`,
24 simulations, seeds 4000-4031, both seats, against the plain policy:

| | |
| --- | ---: |
| score | 0.547 +/- 0.062 (32 seed pairs) |
| 95% CI | [0.425, 0.668] |
| mean total | **-0.58** |
| nuclear losses | 0 |
| seconds a game | 650, of which 93% is search |

**The interval contains 0.5 and the mean total is slightly negative.** The
0.75 was 8 games; it is gone. And the diagnostics say why, which is the
part worth keeping:

| | |
| --- | ---: |
| simulations completed | 24 (always) |
| tree nodes | median 15 |
| root moves that got any visit | median 8, max 12 |
| **visits to the move it chose** | **median 4, min 3** |
| searches choosing on fewer than 5 visits | 526 of 900, **58%** |
| truncated rollouts | 0 |

Twenty-four simulations spread over eight to twelve root macros is three or
four visits each. A UCT root that picks the highest mean over three samples
is not searching, it is sampling noise, and 58% of decisions are decided
that way. The honest description of the current prototype is a very
expensive random tie-break among survival-safe cards.

So the two ways forward are arithmetic, not engineering taste. Either the
root gets far fewer macros (three or four, not twelve), which is free, or
the simulation count goes up by an order of magnitude, which at 650 s a
game is impossible in Python and is the case a native port would have to
make. **Nothing here supports starting the port.** Narrow the root first
and re-measure; that experiment costs nothing and would tell us whether
the leaf and the rollout are any good at all, which this run cannot.

Evidence: `logs/game-check/mcts-32seed-5a2f3bb/`, per-game INFO logs with
every search dict, summarised by `mcts_report.py` in the session
scratchpad.

### Military Operations: rule-exact value, and why a flat one VP an Op is wrong

The only model was a credit inside `coup()` of `weights.military * min(ops,
deficit)`, a flat 2.0 raw against a VP worth ~16 raw on the opening board:
the requirement was priced at about an eighth of its value. Rule 6.3.5
leaves nothing to estimate -- a side below the DEFCON level at the end of
the turn hands the difference over as VP -- so an Op that closes the
deficit is worth exactly one VP and an Op past it is worth nothing.

Pricing it at a full VP an Op made the fixture **worse**, 23 misses to 26:

| Card | Expert | Flat credit | Discounted |
| --- | ---: | ---: | ---: |
| Korean War | -1.00 | -2.07 | -1.10 |
| Indo-Pakistani War | +0.50 | +1.59 | +0.67 |
| Arab-Israeli War | -1.78 | -2.33 | -1.42 |

The reason is that early in a turn the credit is not real: some *later*
card would very likely have covered the requirement anyway, and only the
Ops that end up uncovered are worth a VP. Spreading the credit over the
action rounds still to play fixes it, uses the shape the Containment and
Red Scare riders already use, and introduces no free parameter -- full
value in the last round, a sixth of it in the first.

Discounted, the three war rows move to 24 misses, and the sum of their
absolute error is 0.63 against the baseline's 0.64. **So the fixture calls
this neutral, not an improvement.** The extra "miss" is an ordering check,
not a value: Arab-Israeli War moving toward its target overtook Suez
Crisis, which is itself underpriced by 1.27 and already flagged. Keep the
change because it is rule-exact and the old number was arbitrary, not
because the table endorses it; the gate decides.

Both call sites -- `coup()` and the event sandbox -- now go through one
`military_credit`, so they cannot drift. The sandbox half is new: a war
grants Military Ops to whoever the *event* belongs to, which is not always
the side playing the card (the US playing Korean War for Ops credits the
USSR), and the sandbox valued events by board influence and VP alone, so
that was worth nothing at all before.

Two process notes. The first version read `side` inside `_resolve_sandbox`,
which is an evaluator index there and not a `Side`; every sandboxed event
fell back to its estimate. It was loud rather than silent only because
`b5466cc` made an unexpected sandbox failure a warning -- exactly the case
that commit was written for. And `coup()` now calls `vp_value`, so it needs
the per-decision Ops cache that `rank_actions` builds and `prepare` does
not; every production caller is already inside a ranking, but a test that
called `prepare` alone crashed, which is worth knowing before someone
evaluates a coup outside one.

### The free-Coup gate: accepted, and no gain to show for it

`bbebbd8` against `b9f5370`, 76 seeds over both samples (the gate ran as
`gate-6d33d91`, HEAD having moved on to the docs commits, which touch no
bot file):

| Sample | Seeds | Score |
| --- | ---: | ---: |
| tuning 4000-4031 | 32 | 0.484 |
| held out 5000-5063 | 44 | 0.500 |
| pooled | 76 | **0.493 +/- 0.026** |

**ACCEPTED** on the rule that only a measurable regression blocks: the
one-sided 95% upper bound is 0.536. But read it plainly -- the point
estimate is a hair *below* even, and the fix bought nothing the games can
see. Two honest reasons and one thing to check:

- The three cards are Mid War, so they only fire in a subset of games, and
  the gate's half-width here is 0.05. A change confined to three cards
  cannot clear that bar even if it is worth something.
- Taking a free Coup is not free: it degrades DEFCON on a Battleground.
  The bot now takes Coups it used to decline, so some of the value is
  spent on DEFCON.
- One candidate nuclear loss, seed 4015 US T8, and the evidence says look
  at it rather than shrug. **That seat has appeared in 34 recorded gates
  and never once ended at DEFCON 1**; it ends on VP, Wargames or final
  scoring. It is a seat the bot loses every single time (result 0.0 in all
  34), so this costs nothing in score, but the mechanism is new and the
  change is the obvious suspect.

  Against that suspicion: `coup()` already returns the sentinel for a
  Battleground Coup at DEFCON 2 and `none` scores 0, so the free-Coup
  branch should refuse exactly the suicidal ones. The likelier story is
  DEFCON 3 to 2 on a Battleground the *geography* rule would normally have
  forbidden -- a free Coup is exempt from 8.1.5 -- with something else
  taking the last step. **Not resolved: replay it at `bbebbd8` in a
  worktree and read the DEFCON transitions.** Deferred only because the
  working tree carries the uncommitted Military Ops change, and stashing
  it while the corpus generator is reading `src/` would corrupt the
  capture.

The fix stays regardless. Choosing by tuple order is not a strategy, and
"the games cannot measure it" is not "it was fine". This is what the
gate's asymmetric rule is for.

### Seed 4015 replayed: the whole-hand planner did not see a trap seven rounds away

The gate's flagged nuclear loss, run down properly. My guess in the section
above was **wrong** -- no free Coup is involved anywhere in the fatal
sequence. What actually happened is worse, and it is the most valuable
thing found tonight.

Reproduced by replaying `bbebbd8` against the gate's own base snapshot
(mirror self-play at the same commit does *not* reproduce it: the loss
needs the pre-fix opponent, so it is a trajectory difference, not a new
suicidal move).

Turn 8, DEFCON 2 from action round 1 onward. The US hand at AR1:

    Lone_Gunman, Sadat_Expels_Soviets, Willy_Brandt, Iran_Contra_Scandal,
    Portuguese_Empire_Crumbles, Reagan_Bombs_Libya, The_Reformer, Star_Wars

Lone Gunman is a USSR event: playing it for Ops still hands the USSR the
Operations, and at DEFCON 2 the USSR spends them on a Battleground Coup,
which is DEFCON 1 and a loss for the phasing player. So **that one card was
a certain loss from AR1, with seven rounds of warning.** The bot played
every other card first and arrived at AR7 holding it alone:

| Round | Played |
| --- | --- |
| AR1 | Star Wars, event |
| AR2 | Reagan Bombs Libya, event |
| AR3-5 | Willy Brandt, Iran-Contra, Portuguese Empire -- all *USSR* events, for Ops |
| AR6 | Sadat Expels Soviets, Ops |
| AR7 | **Lone Gunman, forced.** "EVERY option is a certain loss" |

Two separate defects, and the planner's own log settles which is which.

**1. The planner reported `risk=0.000` on every option at AR1.** Not a
truncated conservative estimate -- zero. It does see this card: the corpus
notes record Lone Gunman at DEFCON 2 as `risk` 1.0 *once it is forced*. It
simply never propagates that back to the round where it could still be
avoided. `docs/notes/claude/` opens by claiming the planner will "plan
the whole hand, not the current card"; on this evidence the claim is
overstated. It survives the current round and defers the problem, every
round, until deferring is the losing move. **A card whose forced play is a
certain loss should dominate the whole turn's plan from the moment the hand
is dealt.**

**2. The Space Race slot went unused while a lethal card sat in hand.**
The US did not space at all on turn 8, though it had spaced twice on turn
6, so the option was live. `space_card` picks "the opponent's card whose
Ops-plus-event is worst" *by value*. Lethality does not enter. Spacing Lone
Gunman at any point in seven rounds saves the game outright. This one is
small and self-contained: a card that is a certain loss when forced should
take the space slot ahead of any value comparison.

Worth being precise about blame. The free-Coup fix did not cause this and
the gate did not really "find" it either -- the seat loses in all 34
recorded gates and the change only altered *how*. What the gate did was
put a nuclear loss on a seed whose history made it worth opening, which is
exactly what the warn-and-name rule is for.

This is the strongest argument yet for the hand planner (tier 2), and it
also gives it a test case that does not need a strength gate to score:
seed 4015 US, turn 8, must not arrive at AR7 holding Lone Gunman.

### The Military Ops gate: the first measured improvement in this project's history

`da721fe` against `6d33d91`:

| Sample | Seeds | Score | Signed VP |
| --- | ---: | ---: | ---: |
| tuning 4000-4031 | 32 | 0.547 | +1.08 |
| held out 5000-5063 | 45 | **0.639** | +5.07 |
| pooled | 77 | **0.601 +/- 0.036** | +3.39 |

**ACCEPTED**, and for once that undersells it. Recomputed over the 75
complete seed pairs the score is 0.617 with a one-sided 95% *lower* bound
of 0.559. Every other gate on record sits below 0.500 on that bound:

| Gate | Seeds | Score | 95% lower |
| --- | ---: | ---: | ---: |
| **da721fe** | 75 | **0.617** | **0.559** |
| 40726d0 | 96 | 0.542 | 0.486 |
| fe6ddb0 | 75 | 0.540 | 0.489 |
| cddb7a0 | 96 | 0.510 | 0.489 |

So this is the first change the games can actually say is *better*, rather
than merely not worse. The held-out sample scores higher than the tuning
sample, which is the wrong direction for overfitting and is the strongest
part of the result.

**The fixture and the games disagree, and the games are right.** The
expert table called this neutral: 23 misses to 24, war-row error 0.64 to
0.63. The games call it a ten-point gain. That divergence is the most
useful thing here after the result itself. `models/expert_valuations.json`
is ~30 rows on the *opening board*, and the Military Ops requirement is
worth least on turn 1 -- the discount makes it a sixth of full value there
-- and most in the Mid and Late War, where the fixture has no rows at all.
A fixture that cannot see the change it is asked to judge will call any
such change neutral. This is the concrete argument for the Late War table
and the annotated position suite, and it is now evidence rather than
opinion.

What it cost: 2 candidate nuclear losses against 0-1 in recent gates, both
flagged (seed 4010 USSR T8, seed 5028 USSR T8), inside the rate cap. The
bot Coups more, so it spends more DEFCON. Set against that, it forced the
*opponent* into DEFCON 1 in five games where recent gates saw one or two,
which the acceptance rules correctly score as wins rather than penalties.

One thing not established: the flat, undiscounted version was never gated.
It was rejected on the fixture alone (23 misses to 26). So the evidence
says the discounted form works; it does not prove the discount is *why*.
If that matters later, gate the flat form as an ablation.

### Correction: most of the seed 4015 write-up above is wrong

The maintainer's correction, and it holds up against the log. Read the
section above with this one; I got the same game wrong twice.

**You cannot Space Lone Gunman.** Every Space Race box requires at least
2 Ops (`rules.json`, boxes 1-4 need 2, 5-7 need 3, box 8 needs 4) and Lone
Gunman is a 1-Ops card, so `_can_space_race` refuses it in every position
the game can reach. `space_card` already filters on exactly that check, so
the "the space slot ignores lethality" defect **does not exist**. I
proposed a fix for a rule I had not read.

**Death on turn 8 holding Lone Gunman, to Terrorism or Aldrich Ames
Remix, is not a bug.** It is hand pressure, which the maintainer says is a
normal way to lose and which Codex's tournament notes already record as a
real cause of DEFCON defeats. The log shows exactly that shape: at AR6 the
US held Lone Gunman and The Reformer and correctly played neither of the
lethal lines -- its ranking marks Lone Gunman `lost=1`, so **the planner
does see the card** -- and then the USSR played Terrorism at AR7, which
discarded The Reformer and left Lone Gunman alone. The escape was taken
away, not thrown away.

So the claim that "the planner never saw a trap seven rounds away" is
wrong twice over: it sees the card, and on turn 8 there was no line that
avoids the loss once Terrorism lands. Turn 8 offered the bot nothing.

**What is left, and it is a question rather than a finding.** Lone Gunman
was in the US hand for the whole of turn 7 at DEFCON 5, then 4, then 3,
where playing it is harmless -- the USSR gets one Op. The bot played five
other cards and carried it into turn 8, where DEFCON 2 made it unplayable
all turn. Whether dumping a low-Ops opponent event early, while DEFCON is
still high, is real discipline or hindsight is a judgement call, and I
have now been wrong about this game twice, so it goes to the maintainer
rather than into a term. The repo already has a name for the shape
("self-trapping dumps", in the principles table).

The general lesson is the cheap one: check the rule before designing
around it. Whether a card *can* take the Space Race slot is a one-line
lookup, and it would have deleted half of the previous section.

### The DEFCON prior gate, and a speed claim that was measurement error

`7ba14f0` against `425ac9e`: pooled **0.506 +/- 0.028** over 77 seeds
(tuning 0.469, held out 0.533), **ACCEPTED** and honestly neutral. Two
candidate nuclear losses, flagged for replay (seed 4001 USSR T9, seed 4019
USSR T4), which is the expected direction: a planner that no longer
expects DEFCON to fall every round takes more DEFCON risk. Within the cap.

Keep it anyway. The old 0.75 was seven times a rate that had already been
measured and written down in this repo, and neutral games are not a reason
to keep a number that is known to be wrong. But the *reason* to keep it is
correctness, not strength, and not speed either:

**The speed claim in `7ba14f0`'s commit message is wrong.** It says an
ordinary mid-war decision goes 0.191s to 0.052s. Measured properly --
same process, same corpus positions, the two prior values interleaved so
drift cancels, five repetitions, best of each:

| Position | prior 0.75 | prior 0.15 | speedup |
| --- | ---: | ---: | ---: |
| opening T1 | 0.003s | 0.003s | 1.02x |
| mid-war T5-7 | 0.054s | 0.051s | 1.07x |
| late T8+ | 0.146s | 0.146s | 1.00x |

Nothing. The 3.7x came from comparing two `frozen_bench` runs taken at
*different revisions* and attributing the whole difference to the last
change; everything between them, the Military Ops work included, was in
that gap. The same error produced the claim that the hazardous position's
whole-hand risk fell from 0.469 to 0.081: `frozen_bench` selects the
highest-risk late position *from the corpus*, the corpus was regenerated
in between, so those two numbers describe **different positions**.

And the gate's own timings say the opposite again -- 8.95 s/turn before,
11.31 after -- because those two gates ran under different machine load.
Three measurements, three answers, and only the interleaved in-process one
is worth anything.

This is the same mistake the file already warns about ("never time
anything while a gate runs"), in a new dress. The warning needs widening:
**a timing is only evidence when the two things being compared run in one
process, interleaved, on the same inputs.** Two runs of the same script at
two revisions is not an A/B, it is two anecdotes. Neither is a per-game
average from two gates that shared the machine with different work.
