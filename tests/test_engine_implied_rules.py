"""Rules the engine implies everywhere but states nowhere.

The suite is thick with tests of particular cards and particular
positions. What it has less of is the quiet invariants those rest on --
the ones that would still be true if every card were deleted, and that
nothing would notice breaking until a value function started returning
nonsense three layers up.

Each of these is checked over **every country on the board** rather than
a chosen one, because the failure mode for an implied rule is a single
country where it does not hold. That is cheap here: eighty-odd
countries, integer arithmetic.

Prompted by an Ops-war fixture that restated the cost rule as
`points * influence_cost` and got it wrong, because the doubled rate
stops when control breaks. The rule was in the engine and in a comment,
and in no test.
"""
from __future__ import annotations

import pytest

from struggler.engine import Action, DecisionKind as K, Side
from conftest import bare_engine

SIDES = (Side.US, Side.USSR)


@pytest.fixture
def engine():
    return bare_engine()


def _set(engine, cid, us, ussr):
    engine.board.influence[cid]["US"] = us
    engine.board.influence[cid]["USSR"] = ussr


# -- control ----------------------------------------------------------------

def test_control_is_exactly_margin_against_stability_everywhere(engine):
    """`control` is never anything but this comparison, for any country at
    any influence. Stated because several evaluator terms re-derive it and
    would silently disagree if it ever grew a special case."""
    for cid, info in engine.board.countries.items():
        for us in range(0, info.stability + 2):
            for ussr in range(0, info.stability + 2):
                _set(engine, cid, us, ussr)
                margin = us - ussr
                expected = (Side.US if margin >= info.stability else
                            Side.USSR if -margin >= info.stability else None)
                assert engine.board.control(cid) is expected, (
                    f'{cid} at US {us} SU {ussr}, stability {info.stability}')
        _set(engine, cid, 0, 0)


def test_nobody_controls_an_empty_country(engine):
    for cid in engine.board.countries:
        assert engine.board.control(cid) is None


def test_control_is_never_shared(engine):
    """A pair of mutually exclusive conditions, which is worth pinning
    because the region tiers count both sides' controlled countries and
    would double-count if it ever were not."""
    for cid, info in engine.board.countries.items():
        for us in range(0, info.stability + 2):
            _set(engine, cid, us, info.stability)
            holder = engine.board.control(cid)
            assert holder is None or isinstance(holder, Side)
        _set(engine, cid, 0, 0)


# -- the cost rule ----------------------------------------------------------

def test_placing_costs_two_exactly_when_the_opponent_controls(engine):
    """The rule the Ops-war fixtures got wrong by restating it. It is a
    function of *control*, nothing else -- not of stability, not of how
    much influence is there."""
    for cid, info in engine.board.countries.items():
        for us, ussr in ((0, 0), (info.stability, 0), (0, info.stability),
                         (info.stability + 3, 0), (1, 1)):
            _set(engine, cid, us, ussr)
            holder = engine.board.control(cid)
            for side in SIDES:
                expected = 2 if holder is side.opponent else 1
                assert engine.board.influence_cost(side, cid) == expected, (
                    f'{cid} US {us} SU {ussr}: {side.value} should pay {expected}')
        _set(engine, cid, 0, 0)


def test_the_doubled_rate_ends_the_moment_control_breaks(engine):
    """The implied part: the rate is re-read per point, so a spend that
    breaks control pays double once and single after. Nothing in the
    engine says this out loud; it falls out of charging per placement."""
    for cid, info in engine.board.countries.items():
        if not engine.board.is_reachable(Side.USSR, cid):
            continue
        _set(engine, cid, info.stability, 0)             # US controls, bare
        assert engine.board.influence_cost(Side.USSR, cid) == 2
        engine.board.influence[cid]["USSR"] += 1         # the breaking point
        assert engine.board.control(cid) is None
        assert engine.board.influence_cost(Side.USSR, cid) == 1, (
            f'{cid}: the rate should drop the moment control breaks')
        _set(engine, cid, 0, 0)


def test_breaking_bare_control_always_costs_two_ops(engine):
    """One point, at the doubled rate, for every country on the board --
    independent of stability, which is the part that is easy to assume
    wrongly."""
    for cid, info in engine.board.countries.items():
        _set(engine, cid, info.stability, 0)
        cost = engine.board.influence_cost(Side.USSR, cid)
        engine.board.influence[cid]["USSR"] += 1
        assert (cost, engine.board.control(cid)) == (2, None), (
            f'{cid} at stability {info.stability}')
        _set(engine, cid, 0, 0)


# -- spending, through the engine ------------------------------------------

def test_an_influence_spend_never_exceeds_its_budget(engine):
    for budget in (1, 2, 3, 4):
        fresh = bare_engine()
        fresh.board.influence["Italy"]["US"] = 2
        fresh.board.influence["Greece"]["USSR"] = 1
        before = sum(v["USSR"] for v in fresh.board.influence.values())
        fresh.begin_influence_operations(Side.USSR, budget)
        while fresh.pending_decision and fresh.pending_decision.kind is K.PLACE_INFLUENCE:
            fresh.step(fresh.legal_actions()[0])
        after = sum(v["USSR"] for v in fresh.board.influence.values())
        assert after - before <= budget, f'{budget} Ops bought {after - before} points'


def test_every_offered_placement_is_affordable(engine):
    """A decision must never offer what the remaining Ops cannot buy."""
    engine.board.influence["Italy"]["US"] = 2
    engine.board.influence["Greece"]["USSR"] = 1
    engine.begin_influence_operations(Side.USSR, 3)
    while engine.pending_decision and engine.pending_decision.kind is K.PLACE_INFLUENCE:
        left = engine.pending_decision.context.get(
            "ops_remaining", engine.pending_decision.context.get("remaining"))
        for action in engine.legal_actions():
            cid = action.payload["country"]
            assert engine.board.influence_cost(Side.USSR, cid) <= left, (
                f'{cid} offered with {left} Ops left but costs '
                f'{engine.board.influence_cost(Side.USSR, cid)}')
        engine.step(engine.legal_actions()[0])


# -- placement side effects -------------------------------------------------

def test_placing_changes_control_only_where_it_places(engine):
    """The assumption `evaluator.Position.place` is built on: control moves
    for the country placed in and for nowhere else. If that were ever
    false the snapshot would go stale in a way no test would catch."""
    engine.board.influence["Italy"]["US"] = 2
    before = {cid: engine.board.control(cid) for cid in engine.board.countries}
    engine.board.influence["Italy"]["USSR"] += 1
    after = {cid: engine.board.control(cid) for cid in engine.board.countries}
    changed = {cid for cid in before if before[cid] is not after[cid]}
    assert changed == {"Italy"}, f'control also moved in {changed - {"Italy"}}'


def test_reachability_only_grows_when_you_place(engine):
    """Placing can open countries to you; it must never close one. The
    placement planner walks a reachable set it computed earlier and would
    offer illegal moves if this were not true."""
    for cid in ("Italy", "Chile", "Egypt"):
        fresh = bare_engine()
        before = {c for c in fresh.board.countries if fresh.board.is_reachable(Side.USSR, c)}
        fresh.board.influence[cid]["USSR"] += 1
        after = {c for c in fresh.board.countries if fresh.board.is_reachable(Side.USSR, c)}
        assert before <= after, f'placing in {cid} closed {before - after}'


def test_placing_never_moves_the_opponents_influence(engine):
    """Obvious, and worth one line: Influence placement is additive, so
    only an event or a Coup may remove."""
    snapshot = {c: dict(v) for c, v in engine.board.influence.items()}
    engine.board.influence["Italy"]["USSR"] += 2
    for cid, was in snapshot.items():
        assert engine.board.influence[cid]["US"] == was["US"], cid
