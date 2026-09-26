# The hand planner stays off

The whole-hand planner (`bots/strategic/hand_planner.py`, gated by
`StrategicWeights.hand_assignment`) assigns every card in hand to a turn
slot before the bot picks one. It has been measured six ways since
2026-09-21. None was measurably better than the shipped bot, and the
maintainer's decision on 2026-09-26 is to **leave it off**:
`hand_assignment` stays 0 on main, and PR #57, the near-tie band, was
closed unmerged.

## What was measured

All readings are paired, against the shipped bot on identical seeds.
Every one is in `models/experiment_ledger.json`.

| variant | run | paired diff | nuclear | verdict |
| --- | --- | ---: | --- | --- |
| planner on, as built (`hand-assignment-on`) | 35814771005 | **-0.240** [-0.262, -0.218] | | a tie-break defect: the plan ordered the hand alphabetically |
| strict-preference lead (`planner-strict-lead`) | 35844260343 | **-0.061** [-0.090, -0.032] | USSR 7 -> 26 | still a loss |
| hold the worst card (`planner-hold-worst`) | 35845098170 | **-0.088** [-0.117, -0.060] | | a loss |
| headline only (`planner-headline-only`) | 35858542880 | -0.005 [-0.023, +0.014] | USSR 25 -> 55 | level on score, worse on nuclear losses |
| near-tie band 0.1 / 0.5 / 1.0 Op (`planner-band-*`) | 36225640116 | -0.008 / -0.009 / +0.004, all covering 0 | 55 / 44 / 51 vs 54 | no nomination (rule branch 4) |
| exact ties only, 1e-9 Op (`planner-band-tie`) | 36240012615 | -0.002 [-0.006, +0.003] | 56 vs 54 | rule branch 1, overruled: off |

The band readings are 1152 seeds a side.

## What it taught

- **Overriding the scorer is what cost.** Every variant that let the
  plan's preference outrank the risk and score blend lost strength or
  raised nuclear losses. Confined to near-ties, it did neither. The
  -0.240 was mostly one defect: engine listing order standing in for a
  preference. That diagnosis is in
  [the alphabetical-order note](2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md).
- **As a tie-breaker, the plan is worth nothing measurable.** Ties decide
  17.5% of real card-play choices, yet breaking them by plan moves the
  score by at most about ±0.005.
- **The cost is small but not zero:** about +1%, +3% and +4–5% per
  card-play decision at bands of 0.1, 0.5 and 1.0 Op, and nothing at 0.
  These were timed locally on 221 identical positions.

## Why the tie arm does not ship though its rule said so

The pre-registered rule set a bar of "not measurably worse", because a
tie-break replaces an arbitrary pick. The tie arm cleared that bar with
a dead heat. The maintainer's call: a dead heat does not earn a new code
path and a per-decision cost. The rule reading and the decision are both
recorded, in the ledger (`planner-band-tie`) and in the alphabetical-order
note, so neither is rewritten.

## What stays on main

- `hand_planner.py` and the `hand_assignment` weight, at 0. At 0 the
  planner is never consulted, and the parity corpus confirms this.
- **A positive `hand_assignment` on main is the ORIGINAL override**, the
  one that read -0.240. The band and the strict-lead fix lived only on
  the closed branch `exp/planner-near-tie`. Anyone turning the planner
  back on should start from that branch, not from main.
- The five `planner-band-*` arms are in `_retired`, and their seed blocks
  stay reserved: 132000-133023, spares 133700-133827.

## What would reopen it

A hold needs its own price. Today play and hold are valued the same, so
the plan's only strict preferences are the headline, space and UN slots.
The maintainer's answer (EXPERT_ASKS, holding) gives two reasons to hold:

1. timing an event that cannot be used yet: One Small Step, UN
   Intervention, Wargames;
2. sitting out a negative card past the reshuffle.

For both, `vp_swing` measures the per-turn decline. Until that price
exists, the planner has nothing to allocate.

## A side finding: the stalls are the anchor's, not the shipped bot's

Seeds 132008 and 132709 never finished, in the base arm as well as the
tie arm. The same happened to 140565, 140591 and 141179 in the access
deletion's base arm (run 36253272931). **Traced 2026-09-26: the hang is in
the OPPONENT, the `bc5ef93` anchor.** Replaying 132008 locally, the stack
after four minutes sits entirely in the anchor snapshot. It cycles
`event_value -> _hand_attack_value -> hold_value -> event_value ->
_resolve_sandbox -> helper.choose_action -> _score_event_choice ->
hold_value`, with Blockade and Latin American Debt Crisis ending in
`RecursionError`. This is the sandbox helper chain that `48007da` fixed
on 2026-09-13 (`tests/test_sandbox_helper_chain.py`; the note is
2026-09-12-the-blockade-recursion-is-a-chain-of-fresh-helpers). The
anchor, `bc5ef93`, is from 2026-09-12 and predates the fix. The shipped
bot has it.

What it costs a reading: the anchor hangs on a game path, not on a seed,
so a hung game drops that seed from BOTH compared arms, and the spare
shards backfill it. That is paired attrition, recorded in `pooled.json`'s
`dropped`. It is not a defect in the bot under test. Any arm anchored on
`bc5ef93` will keep losing about one seed in 700 this way.
