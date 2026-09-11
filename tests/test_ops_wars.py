"""The economics of breaking control, as fixtures.

Placing into a country the opponent **controls** costs 2 Ops a point --
but only until control breaks, which the first point does. Every point
after that is single rate. So the 2x toll is paid **once**, and against a
defended stability-2 country:

    Ops spent   points   end state    repair Ops   ratio
            2        1   US 2 SU 1             1     2:1
            3        2   US 2 SU 2             2     3:2
            4        3   US 2 SU 3             3     4:3
            5        4   US 2 SU 4        (taken)    --

**Breaking with n Ops costs the defender n-1 to repair.** The penalty is
one Op whatever the size, so the *relative* loss shrinks the more you
commit -- which is exactly why the maintainer's rule is "you have to
spend all your Ops, because otherwise you make it too easy for the
opponent". A minimum break is a 2:1 loss; a full four-Op break is 4:3,
near enough fair, and is the effective way to break a stability-2
country that is not over-protected.

Over-protection is what makes that fail, and it is a Mid and Late War
thing: on turns 1-4 neither side can spare the Ops to hold a margin.

That structure is why forty points accumulate in stability-2 countries
-- the corpus has Thailand at US 21 / SU 19 -- and why the defender wins
break wars fought one point at a time.

These fixtures pin the *engine* side of that exactly -- costs, legality,
and resulting control -- because it is arithmetic and cannot drift. They
only **record** what the bot ranks, without requiring any particular
choice, so the module is a before/after instrument for the
half-action-round forward search rather than a test that has to be
rewritten when the search lands. The search is off by default; these
pass either way.
"""
from __future__ import annotations

import pytest

from struggler.engine import Action, DecisionKind as K, Engine, Side
from conftest import bare_engine


def _board(engine: Engine, **influence: tuple[int, int]) -> None:
    """Set the board directly: `Country=(us, ussr)`."""
    for cid, (us, ussr) in influence.items():
        engine.board.influence[cid]["US"] = us
        engine.board.influence[cid]["USSR"] = ussr


def spend(engine: Engine, side: Side, cid: str, ops: int) -> int:
    """Spend `ops` into `cid` through a real decision; return the points
    bought.

    Not `points * influence_cost`, which is the trap this module exists to
    document: the doubled rate stops the moment control breaks, so four
    Ops buy three points against a defended stability-2 country, not two.
    Going through the engine means the fixture cannot restate the rule
    wrongly.
    """
    before = engine.board.influence[cid][side.value]
    engine.begin_influence_operations(side, ops)
    while engine.pending_decision and engine.pending_decision.kind is K.PLACE_INFLUENCE:
        action = Action(K.PLACE_INFLUENCE, {"country": cid})
        if action not in engine.legal_actions():
            break
        engine.step(action)
    return engine.board.influence[cid][side.value] - before


def repair_cost(engine: Engine, side: Side, cid: str) -> int:
    """Ops for `side` to (re)take `cid` from here."""
    inf = engine.board.influence[cid]
    need = engine.board.countries[cid].stability + inf[side.opponent.value] - inf[side.value]
    return max(0, need) * engine.board.influence_cost(side, cid)


# -- the exchange itself ----------------------------------------------------

@pytest.mark.parametrize('budget, points, repair', [(2, 1, 1), (3, 2, 2), (4, 3, 3)])
def test_breaking_with_n_ops_costs_the_defender_n_minus_one(budget, points, repair):
    """The whole finding, parameterised. The 2x toll is paid once, on the
    point that breaks control, so committing more improves the rate."""
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    assert engine.board.control("Italy") is Side.US
    assert spend(engine, Side.USSR, "Italy", budget) == points
    assert engine.board.control("Italy") is None, 'broken, but not taken'
    assert repair_cost(engine, Side.US, "Italy") == repair
    assert repair == budget - 1, 'the penalty is one Op whatever the size'


def test_five_ops_takes_the_country_instead_of_merely_breaking_it():
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    assert spend(engine, Side.USSR, "Italy", 5) == 4
    assert engine.board.control("Italy") is Side.USSR


def test_bare_control_is_still_broken_by_one_point():
    """The trap inside the rule: taking the country at *exactly* stability
    leaves it breakable for two Ops, so five Ops buys control and not
    security."""
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    spend(engine, Side.USSR, "Italy", 5)                 # (2, 4), margin 2
    assert engine.board.control("Italy") is Side.USSR
    engine.board.influence["Italy"]["US"] += 1           # 2 Ops
    assert engine.board.control("Italy") is None


def test_a_point_of_margin_is_what_survives_the_cheap_answer():
    """Over-protection, and why it is a Mid and Late War move: it costs an
    extra Op that turns 1-4 cannot spare."""
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    spend(engine, Side.USSR, "Italy", 6)                 # (2, 5), margin 3
    assert engine.board.control("Italy") is Side.USSR
    engine.board.influence["Italy"]["US"] += 1
    assert engine.board.control("Italy") is Side.USSR, 'margin 3 survives one point'


def test_a_break_the_opponent_cannot_reach_is_not_repaired_at_all():
    """The repair has to be legal. With no Influence in the country and no
    controlled neighbour, the defender cannot place there at any price."""
    engine = bare_engine()
    _board(engine, Chile=(3, 0))
    engine.board.influence["Chile"]["USSR"] += 1
    engine.board.influence["Chile"]["US"] = 0
    assert not engine.board.is_reachable(Side.US, "Chile")


# -- the productive alternative --------------------------------------------

def test_the_same_ops_take_an_empty_battleground_outright():
    """What the Ops buy instead. Four Ops break a controlled Battleground
    and leave it contested; the same four take an empty one and hold it,
    because an empty country costs single."""
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    assert spend(engine, Side.USSR, "Italy", 4) == 3
    assert engine.board.control("Italy") is None, (
        'four Ops break it and leave it contested, repairable for three')

    other = bare_engine()
    _board(other, Chile=(0, 0), Argentina=(0, 1))
    assert spend(other, Side.USSR, "Chile", 4) == 4
    assert other.board.control("Chile") is Side.USSR, (
        'the same four Ops take an empty stability-3 Battleground outright')
    assert other.board.influence["Chile"]["USSR"] - 3 == 1, 'with a point of margin'


# -- through the engine, not just the board --------------------------------

def test_the_double_rate_applies_to_the_breaking_point_only():
    """Stated as a rate rather than a total, because the total is what the
    first version of this module got wrong."""
    engine = bare_engine()
    _board(engine, Italy=(2, 0), Greece=(0, 1))
    engine.begin_influence_operations(Side.USSR, 4)
    assert engine.board.influence_cost(Side.USSR, "Italy") == 2
    engine.step(Action(K.PLACE_INFLUENCE, {"country": "Italy"}))
    assert engine.pending_decision.context["ops_remaining"] == 2, 'the first point cost 2'
    assert engine.board.control("Italy") is None
    assert engine.board.influence_cost(Side.USSR, "Italy") == 1, 'and the rest cost 1'


# -- what the bot currently does, recorded rather than required ------------

def test_record_the_bots_preference_between_a_break_and_an_empty_country():
    """Deliberately not an assertion about which it picks.

    With the forward search off the bot prefers the break, because the
    break really is the cheapest way to change a control and nothing tells
    it the change will not survive. With the search on it should prefer the
    empty country. Pinning either would make this a test that has to be
    edited when the behaviour is fixed, which is shape 8 in
    `docs/CLAUDE_NOTES.md`. So it records the numbers and asserts only what
    must hold either way: both are legal, and they are priced differently.
    """
    from struggler.bots.strategic import StrategicPlayer
    engine = bare_engine()
    # Greece reaches Italy; Argentina reaches Chile.
    _board(engine, Italy=(2, 0), Greece=(0, 1), Chile=(0, 0), Argentina=(0, 1))
    engine.begin_influence_operations(Side.USSR, 4)
    obs = engine.observe(Side.USSR)
    bot = StrategicPlayer()
    ranked = bot.rank_actions(obs)
    by_country = {a.payload["country"]: key[-1] for key, a in ranked}
    assert "Italy" in by_country, 'the break must be on the table'
    assert "Chile" in by_country, 'and so must the empty Battleground'
    assert by_country["Italy"] != by_country["Chile"], (
        'if these ever score identically the ranking has stopped '
        'distinguishing a break from a free country')
