# MCTS with a 1- or 2-action-round horizon, timed

The maintainer asked (2026-09-27) how slow MCTS was for one or two action
rounds, and whether full turns had been tried. None of it had been timed
on current code: the prototype (`bots/mcts.py`) last ran on 2026-09-10/11,
and its rollouts ran to the end of the turn. Its 32-seed run read 0.547
+/- 0.062, at 650 s a game, with a median of 4 visits to the chosen move --
"a very expensive random tie-break"
(archive/2026-09-10-mcts-does-not-replicate-and-military-ops-needed-a-discount.md).

## What changed

`MCTSPlayer(horizon=n)` stops a simulation at the first card play `n`
action rounds past the root, counting both sides. 1 is our play and the
opponent's reply; 2 is two of each. The position there is scored by
`leaf_return`: the strategic value function plus banked VP, the same leaf
the prototype already used for turn ends. `horizon=None` is the original
rest-of-turn behaviour, and the existing MCTS tests pass unchanged.
`STRUGGLER_MCTS_HORIZON` sets it for benchmark runs.
`tests/test_mcts_horizon.py` pins that a horizon search stops mid-turn and
reports it.

## The timing (local, idle 6-core box, one search at a time)

Eight AR1 card-play decisions from the parity corpus: turns 1, 3, 5 and 7,
each side. `search_all` was on, so every one searched. Wall time per
decision, with `logs/mcts-horizon/time_horizon.py`:

| horizon | simulations | median | max | visits to chosen (median) |
| --- | ---: | ---: | ---: | ---: |
| rest of turn (the prototype) | 24 | 22.9 s | 43.0 s | 7.5 |
| 2 action rounds | 24 | 8.6 s | 18.1 s | 6.5 |
| 1 action round | 24 | 3.3 s | 7.4 s | 6.0 |
| 2 action rounds | 96 | 32.1 s | 55.2 s | 27.5 |
| 1 action round | 96 | 13.1 s | 21.8 s | 23.0 |

The root had a median of 5 candidate moves (the September run had 8-12).

## What it means

- **The horizon buys simulations.** 1 round is about 7x cheaper per search
  than the rest of the turn, and 2 rounds about 2.7x. At 96 simulations,
  1 round gets **23 visits** to the move it picks, three times what the
  old 24-simulation search ever had, for about half its time.
- **These are AR1 decisions, the worst case for rest-of-turn.** The later
  in a turn, the shorter a rest-of-turn rollout, so its median over a
  whole game would be lower than 22.9 s. The horizon searches cost about
  the same at any action round.
- **A whole game** has about 65 of our own card plays. Searching every
  one, as rough products of the medians: 1 round at 96 simulations is
  about 14 minutes a game, and 2 rounds at 24 about 9, against about 50 s
  for the strategic bot. Searching only chosen decisions (the prototype
  searched only turns with a scoring card in hand) divides that down.
  Either way it is a CI experiment, not a local one, and a 1024-seed arm
  is many runner-hours.

## The experiment this makes cheap

The obvious first one: **1 action round, 96 simulations, searching only
AR1** (the maintainer's headline-then-AR1 question lives there: the USSR's
headline plus AR1 are two moves in a row). It would run against the
strategic bot at a few hundred seeds first, to see whether the search
separates from the policy at all, before any 1024-seed arm. Nothing is
dispatched yet.

## The first experiment: the rule, before the number (2026-09-27)

The maintainer: "start the horizon 1 MCTS and see what it buys." To run
it on CI, an arm can now carry `search` (`{"simulations": 96, "horizon": 1,
"rounds": [1]}`): the shard's challenger is HEAD's `MCTSPlayer`, searching
only the named action rounds and falling back to the strategic policy
everywhere else (`MCTSPlayer(rounds=...)`, `STRUGGLER_MCTS_ROUNDS`).
`search` joins the shard's cache key only when set, so no strategic arm's
cached shard moves. The benchmark now counts `search_overrides` (searches
that played a card the strategic policy would not have), and the pool
summary reports `search_override_rate`.

A local smoke (seed 151000, both seats, two workers) ran clean: 16
searches at 17.5 s each, 6 of them overrides (37.5%), scoring 0.5.

**Arm `mcts-h1-ar1`:** 96 simulations, horizon 1, AR1 only, against
HEAD's strategic bot, the same policy MCTS falls back to. It plays **256
seeds** (151000-151255, 32-seed shards, reserve 151300-151363) with waves
off. With paired seats, the mirror is 0.5 in expectation, so the score
minus 0.5 is what searching AR1 buys.

THE RULE, not moved after the number:

1. **Lower bound above 0.5:** search at AR1 buys strength. Next come 1024
   seeds, then wider search (more rounds, or horizon 2).
2. **Covers 0.5:** not measurable at 256 seeds (about +/-0.035). The
   override rate and per-search cost are the reading, and the next step is
   the maintainer's (more simulations, horizon 2, or more seeds).
3. **Upper bound below 0.5:** searching AR1 costs. The likeliest culprit is
   the mid-turn leaf (the value function scoring a position one round
   ahead), and it is looked at before anything wider is tried.
4. **Veto:** DEFCON-1 losses by the MCTS side more than 1.5x the strategic
   side's is a failure, whatever the score.

## The first experiment: the reading (run 36301443382, 2026-09-27)

The run is complete: 256 seeds (512 games) plus two spare shards, no stall.

| | |
| --- | ---: |
| score vs HEAD's strategic bot | **0.479 [0.448, 0.510]** (US 0.553, USSR 0.406) |
| DEFCON-1 losses, MCTS side / strategic side | **38 / 9** over all 640 games (31 / 8 in the counted 512) |
| searches | 5010, at 39.9 s each on a runner (17.5 s locally) |
| searched plays that overrode the strategic pick | **36.7%** |
| mean game | 342 s |

**By the rule: rule 4's veto fires** (MCTS nuclear losses are 3.9x the
strategic side's; the line was 1.5x), so this is a failure whatever the
score. The score itself covers 0.5 and leans worse, which is rule 2's
"not measurable", with the USSR seat worst.

**Where the losses are:** 27 of 38 came as the USSR, on turn 2 (10) and
turns 8-9 (16). The override rate is barely higher in the games MCTS lost
to DEFCON 1 (39.9%) than elsewhere (36.6%), so the search is not reckless
in general. It is losing specific games.

**The likeliest cause (a hypothesis, not yet traced).** The strategic
ranking prices whole-hand survival (`safety_key`: the survival planner's
risk that the cards left can all be played safely before the turn ends).
A 1-round search scores the position one round ahead with `leaf_return`
(value function + banked VP), which does not see a hand that has become
unplayable later in the turn. The rollouts below the root use
`RolloutPolicy`'s immediate-only survival guard. So the search can prefer
an AR1 card that scores better one round out and leaves the hand
cornered, which is exactly the turn-8/9 shape, and turn 2 is the first
turn with DEFCON low enough to bite.

**Next, before any wider search** (rule 3's instruction, since the leaf is
the suspect):

1. **Trace it:** replay three or four MCTS-side DEFCON-1 games with logs on,
   and check that the AR1 override left a cornered hand.
2. **Fix it in the leaf:** charge the leaf the survival planner's residual
   risk for the hand left, priced against the game as `safety_key`
   already does. Or, more simply, restrict the root to moves whose
   safety risk ties the policy's best (the prototype's original "tie
   the best strategic survival ranking" rule, which the horizon leaf now
   bypasses).
3. **Re-run the same arm.** The strategic side's games reproduce exactly,
   so the comparison is clean.

## Tracing the nuclear losses, and the second experiment (2026-09-27)

The maintainer: "try experimenting with search after DEFCON result in
MCTS." Traced first, on seed 151001 as the USSR, one of the ten turn-2
MCTS-side DEFCON-1 losses:

- **The two overrides were NOISE.** At T2 AR1 the search chose Indo-Pakistani
  War at 0.8829 over the policy's East European Unrest at 0.8825, 33 visits
  each. At T1, Socialist Governments -0.413 against Nuclear Test Ban
  -0.442. A 1-round search at 96 simulations cannot tell those apart, and
  the root took the higher mean anyway. The search was effectively
  randomising among the policy's top three.
- **The loss itself came later.** The strategic policy played AR2-6 and
  held CIA Created to AR6 at DEFCON 2. That was harmless in the plain
  game, where the same card was the last one left. Here, a US
  Decolonization on AR5 (firing the USSR event) had put a USSR point in
  Nigeria, giving the US a coupable battleground once CIA Created fired.
  The overrides changed the path; the hazard was in the policy's later
  play.
- **The leaf compresses differences:** `tanh(value / 100)` saturates near
  +/-0.88 on these boards (values of 100 and up), which makes noise
  relatively larger.

Three options added, each off by default:

- `safe_root`: survival first. A root card must be no riskier than the
  policy's pick, and not cornered unless it is. This is the maintainer's
  "search after the DEFCON result".
- `leaf_risk`: a leaf is charged the survival planner's whole-hand
  turn-loss risk, `(1 - r) * value - r`.
- `confidence` z: the root plays the searched best only if it beats the
  policy's own card by z standard errors of the difference; otherwise the
  policy's card.

On seed 151001, `safe_root` and `leaf_risk` changed nothing: both overrides
still happened, because at AR1 no card was risky yet. `confidence` 2 made 0
overrides, and the game survived as the plain one does. One game; it shows
the mechanism, not the rate.

Arms against HEAD's strategic bot on the SAME seeds as `mcts-h1-ar1`
(151000-151255, reserve 151300-151363, 32-seed shards), each horizon 1, 96
simulations, AR1 only:

- `mcts-h1-conf2`: confidence 2;
- `mcts-h1-conf1`: confidence 1;
- `mcts-h1-guarded`: safe_root + leaf_risk + confidence 2.

THE RULE, not moved after the number, per arm:

1. **Veto first:** MCTS-side DEFCON-1 losses more than 1.5x the strategic
   side's is a failure.
2. **Lower bound above 0.5:** searching AR1 buys strength; 1024 seeds next.
3. **Covers 0.5, veto clear:** safe but not measured to help. The override
   rate says why: near 0 means the gate leaves search nothing to do at 96
   simulations, and the next lever is more simulations, not a looser gate.
4. **Upper bound below 0.5:** costs.

## The second experiment: the reading (run 36310237025, 2026-09-27)

All three arms are complete at 256 seeds. On the 256 core seeds, with
the first run alongside:

| arm | vs HEAD strategic | DEFCON-1 losses, MCTS / strategic | overrides | rule |
| --- | --- | ---: | ---: | --- |
| `mcts-h1-ar1` (no gate, run 36301443382) | 0.479 [0.448, 0.510] | 31 / 8 (3.9x) | 36.7% | veto |
| `mcts-h1-conf1` | **0.465 [0.437, 0.493]** | 32 / 9 (3.6x) | 20.5% | veto; costs |
| `mcts-h1-conf2` | 0.486 [0.461, 0.511] | 25 / 10 (2.5x) | 11.0% | veto |
| `mcts-h1-guarded` (safe_root + leaf_risk + conf 2) | **0.509 [0.484, 0.534]** | **17 / 12 (1.4x)** | 10.3% | **veto clear; covers 0.5** |

A search costs 35-38 s on a runner, and a game about 300 s.

**By the rule:** `mcts-h1-guarded` is the first MCTS variant to clear the
veto. It covers 0.5 (rule 3): safe, not measured to help. Its override
rate is 10.3%, not near 0, so the gate does leave the search room to act,
and at 256 seeds (+/-0.025) what it does is not distinguishable from the
policy. The other two fail the veto, and confidence 1 also costs.

**What the arms say together:**

- **Overrides trade survival for nothing.** More overrides meant more
  DEFCON-1 losses and a lower score, at every setting.
- **The confidence gate alone is not enough.** At z = 2, the 11% of
  overrides that clear it still lost 2.5x as often. Confident on value is
  not safe on survival.
- **The survival guards do the work the gate cannot.** At the same z = 2
  and nearly the same override rate, adding `safe_root` and `leaf_risk`
  cut MCTS-side losses from 25 to 17 and moved the score from 0.486 to
  0.509. The seed-151001 trace said neither guard would matter for that one
  game (no card was risky at AR1); across 256 games they do.

**Next, if MCTS is pursued:** the guarded settings are the base to build
on. Two ways to find out whether its 10% of overrides are worth anything:

1. **More seeds:** 1024 seeds at +/-0.012 would resolve a 2-point gain.
   At about 300 s a game that is roughly 170 runner-hours.
2. **Better overrides:** more simulations (192) per search. Rule 3's lever
   was for a near-zero override rate, which this is not, but deeper
   evidence per override is the other way to make the 10% count.
