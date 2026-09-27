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
