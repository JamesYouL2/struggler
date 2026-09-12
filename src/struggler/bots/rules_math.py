"""Rules arithmetic over public observation state, shared by every bot.

These nine functions lived in `greedy.py` and were imported from there by
`strategic/policy.py`, `rollout.py`, `llm/board_report.py` and three test
modules. That made one baseline bot's file the home of code four other
things depend on, with a live hazard: `benchmark.py` runs `GreedyPlayer`
as a comparison baseline, so a change made here *for the strategic bot*
would silently move the thing it is measured against. Found while pricing
the Space Race ability boxes, which needed exactly such a change.

What belongs here: pure functions of **public** state -- the board as
observed, `turn_effects`, the rules tables -- with no weights and no
hidden information (mandate #4). What does not: anything taking a
`GreedyWeights` or `StrategicWeights`, which is a policy's opinion rather
than a rule.

Several of these are deliberate *replicas* of engine internals rather than
calls into them, because a bot may only read what a seat can see.
`realignment_bonus` mirrors `Engine._realignment_bonus` and says so; the
duplication is the known cost and `docs/notes/claude/bug-shapes.md` shape
4 is the reason it is called out rather than hidden. `effective_ops_estimate`
is the counter-example worth copying: it used to be a second copy and is
now a call into `effective_ops`, which is how it stopped being wrong.
"""
from __future__ import annotations

from struggler.engine import Observation, Region, Side, Subregion
from struggler.engine.board import Board, CountryInfo
from struggler.engine.core import effective_ops
from struggler.engine.rules import RULES


def sync_board(board: Board, observation: Observation) -> None:
    influence = board.influence
    for cid, values in observation.influence.items():
        target = influence[cid]
        target["US"] = values.get("US", 0)
        target["USSR"] = values.get("USSR", 0)


def in_bonus_region(info: CountryInfo, bonus: str | None) -> bool:
    if bonus == "asia":
        return info.region is Region.ASIA
    if bonus == "se_asia":
        return Subregion.SOUTHEAST_ASIA in info.subregions
    return False


def bonus_ops(info: CountryInfo, bonuses) -> int:
    """How many extra Ops a point spent in this country earns: the play can
    carry two region bonuses at once (the USSR's China Card under Vietnam
    Revolts), and South East Asia is inside Asia, so a South East Asian
    country satisfies both."""
    return sum(1 for tag in bonuses or () if in_bonus_region(info, tag))


def coup_roll_modifier_estimate(observation: Observation, side: Side, info: CountryInfo) -> float:
    mod = 0.0
    te = observation.turn_effects
    lads = te.get("la_death_squads")
    if lads and info.region in (Region.CENTRAL_AMERICA, Region.SOUTH_AMERICA):
        mod += 1.0 if side.value == lads else -1.0
    if te.get("salt"):
        mod -= 1.0
    return mod


def coup_risks_defcon(observation: Observation, side: Side, info: CountryInfo) -> bool:
    """Whether a Coup here could degrade DEFCON at all: only Battleground
    countries do, and even those not while Nuclear Subs exempts this side."""
    if not info.battleground:
        return False
    return not (side is Side.US and bool(observation.turn_effects.get("nuclear_subs")))


def realignment_bonus(board: Board, side: Side, country: str) -> float:
    """Mirrors engine.core.Engine._realignment_bonus -- kept in sync by
    hand since this is an independent duplicate, not shared code. The
    region-bonus extra attempt (China Card in Asia / Vietnam Revolts in SE
    Asia) is deliberately NOT modeled here: it would add "count remaining
    Ops-type-choice attempts as still in-region" bookkeeping to a bot that
    already has no lookahead and only proxy (not exact) legality elsewhere
    -- disproportionate complexity for its value."""
    bonus = 1.0 if board.is_adjacent(side.value, country) else 0.0
    bonus += sum(1 for n in board.neighbors(country) if board.control(n) is side)
    if board.influence[country][side.value] > board.influence[country][side.opponent.value]:
        bonus += 1.0
    return bonus


def realignment_modifier(observation: Observation, side: Side) -> float:
    return -1.0 if (side is Side.US and observation.turn_effects.get("iran_contra")) else 0.0


def effective_ops_estimate(card, observation: Observation, side: Side) -> int:
    """The Ops `card` is worth to `side`, from the observation's public turn
    effects. The same function the engine applies, not a second copy of it:
    this one used to be a copy, and both were missing the Containment and
    Brezhnev ceiling."""
    return effective_ops(card.ops, observation.turn_effects, side)


def space_race_expected_vp(observation: Observation, side: Side) -> float:
    """The VP the *rules* award for the next attempt, and only that.

    Boxes 2, 4, 6 and 8 grant abilities; 2, 4 and 6 award no VP at all, so
    this returns 0.0 for them. That is correct here and must stay so -- what
    an ability is worth is a policy's opinion. `StrategicPlayer.
    _space_expected_vp` adds that premium; GreedyPlayer does not, which is
    part of what makes it a baseline.
    """
    pos = observation.space_race.get(side.value, 0)
    if pos >= RULES["space_race_max_box"]:
        return 0.0
    next_box = pos + 1
    box = RULES["space_race_boxes"][str(next_box)]
    probability = box["roll_max"] / 6.0
    first = observation.space_race.get(side.opponent.value, 0) < next_box
    vp = box["vp_first"] if first else box["vp_second"]
    return probability * vp
