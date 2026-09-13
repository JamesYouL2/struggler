"""The strategic bot: the policy, its value function, and its planner.

Four modules, each a job the others do not do:

- `evaluator`  pure board terms over an indexed snapshot, no state of their
               own. The part a native kernel would receive as-is.
- `public_cards`  the deck's public schedule: which cards are live, when a
               region scores next, the odds the game reaches final scoring.
- `defcon`     the whole-hand survival search, which ranks every card, mode
               and discard by turn-loss risk before value is consulted.
- `policy`     everything stateful: the valuation context, Ops/VP pricing,
               the event sandbox, card valuation, risk integration, and the
               decision dispatch.

Re-exported flat, so `from struggler.bots.strategic import StrategicPlayer`
keeps working for the engine, the benchmark, the trainer and the tests.
`policy` is still the biggest file here by a wide margin and holds six
distinct jobs; splitting *it* is the next step, and the gate's snapshot
loader was taught about packages first so a baseline binds its own code
(`benchmark._SnapshotFinder`).
"""
from struggler.bots.strategic.policy import *   # noqa: F403
from struggler.bots.strategic.policy import (   # noqa: F401
    ASK, CARDS, HAND_ATTACK_EVENTS, HIDDEN_INFO_EVENTS, LOSS,
    OPS_MODIFIER_EVENTS, PUBLIC_EVENTS, TUNABLE_WEIGHTS, UNTUNED_WEIGHTS,
    SandboxUnsupported, StrategicPlayer, StrategicWeights,
    coup_bans, scoring_flags,
)
# Shared rules arithmetic. It lives in `bots/rules_math.py`; this re-export
# stays because the tests, `rollout.py` and the corpus generator reach it
# through this name. (It used to live in `greedy.py`, which made one
# baseline bot the home of code four other things import.)
from struggler.bots.strategic.policy import (  # noqa: F401
    bonus_ops, coup_risks_defcon, in_bonus_region, sync_board,
)
