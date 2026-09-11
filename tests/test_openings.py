"""Every opening book is legal, complete, and puts the board where it says.

One book is one starting position, and until now every game the gate has
ever measured began from it -- the strategic bot carries no RNG, so the
deal and the dice were the whole of the variation. These are the
maintainer's three per side.

A mis-specified book fails quietly and expensively: name a country in the
wrong subregion and the placement is refused, list too few and the engine
asks the value function for the rest, so the bot plays a *different*
opening than the one it is credited with and nobody can see it in a score.
So each book is played through the real setup phase and checked against
what it claims to build.
"""
from __future__ import annotations

import pytest

from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.policy import DEFAULT_OPENINGS, OPENINGS, OPENING_BOOKS
from struggler.engine import DecisionKind as K, Engine, Side
from struggler.engine.rules import RULES

ALLOWANCE = {'US': RULES['setup_additional']['WESTERN_EUROPE']['amount'],
             'USSR': RULES['setup_additional']['EASTERN_EUROPE']['amount']}
BONUS = RULES['setup_bonus']['amount']

# What each book is meant to build, as the influence that seat ends setup
# with in the countries it touches. Written from the maintainer's own
# shorthand ("3 WG / 3 France / 2 Italy / Iran to 2") rather than from the
# book, so the two have to agree -- a test that read the book back to
# itself would pass on any typo.
EXPECTED = {
    ('US', 'france'): {'West_Germany': 3, 'France': 3, 'Italy': 2, 'Iran': 2},
    ('US', 'italy'): {'West_Germany': 4, 'Italy': 4, 'Iran': 2},
    ('US', 'germany'): {'West_Germany': 5, 'Italy': 3, 'Iran': 2},
    ('USSR', 'austria'): {'East_Germany': 4, 'Poland': 4, 'Austria': 1},
    ('USSR', 'poland'): {'East_Germany': 4, 'Poland': 5},
    ('USSR', 'yugoslavia'): {'East_Germany': 4, 'Poland': 4, 'Yugoslavia': 1},
}


def play_setup(openings: dict[str, str]) -> Engine:
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    bot = StrategicPlayer(openings=openings)
    while engine.phase == 'setup' and not engine.is_terminal:
        decision = engine.pending_decision
        engine.step(decision.options[0] if decision.actor is Side.CHANCE
                    else bot.choose_action(engine.observe(decision.actor), []))
    return engine


def test_the_expectations_cover_every_book():
    """This file is only as good as its table."""
    assert set(EXPECTED) == set(OPENING_BOOKS)
    for side, names in OPENINGS.items():
        assert set(names) == {n for s, n in OPENING_BOOKS if s == side}
        assert DEFAULT_OPENINGS[side] in names


@pytest.mark.parametrize('side,name', sorted(OPENING_BOOKS))
def test_a_book_spends_exactly_its_allowance(side, name):
    book = OPENING_BOOKS[(side, name)]
    region = 'WESTERN_EUROPE' if side == 'US' else 'EASTERN_EUROPE'
    assert len(book[region]) == ALLOWANCE[side], (
        f'{side}:{name} places {len(book[region])} in {region}, not {ALLOWANCE[side]}. '
        f'Too few and the value function silently picks the rest.')
    assert len(book.get(None, ())) == (BONUS if side == 'US' else 0)


@pytest.mark.parametrize('side,name', sorted(OPENING_BOOKS))
def test_a_book_only_names_countries_in_its_subregion(side, name):
    """A country outside the subregion is not a legal setup placement, so
    the book would be ignored for that point and the opening quietly
    becomes something else."""
    book = OPENING_BOOKS[(side, name)]
    region = 'WESTERN_EUROPE' if side == 'US' else 'EASTERN_EUROPE'
    countries = Engine.new_game(seed=4000).board.countries
    for cid in book[region]:
        subregions = {s.name for s in countries[cid].subregions}
        assert region in subregions, (
            f'{side}:{name} places in {cid}, whose subregions are '
            f'{sorted(subregions)} -- not placeable in {region}')


@pytest.mark.parametrize('side,name', sorted(OPENING_BOOKS))
def test_a_book_builds_the_board_it_claims(side, name):
    """Played through the engine, against the maintainer's own shorthand."""
    other = 'USSR' if side == 'US' else 'US'
    engine = play_setup({side: name, other: DEFAULT_OPENINGS[other]})
    for cid, expected in EXPECTED[(side, name)].items():
        got = engine.board.influence[cid][side]
        assert got == expected, (
            f'{side}:{name} left {cid} at {got}, not {expected}')


def test_the_books_actually_differ():
    """Three names for one position would be a silent no-op -- and the
    whole point is nine starting boards, not one."""
    boards = {}
    for side, names in OPENINGS.items():
        other = 'USSR' if side == 'US' else 'US'
        for name in names:
            engine = play_setup({side: name, other: DEFAULT_OPENINGS[other]})
            boards[(side, name)] = tuple(
                sorted((c, v[side]) for c, v in engine.board.influence.items() if v[side]))
        seen = {boards[(side, n)] for n in names}
        assert len(seen) == len(names), f'{side} books collide: only {len(seen)} distinct boards'


def test_an_unknown_opening_is_refused():
    with pytest.raises(ValueError, match='unknown opening'):
        StrategicPlayer(openings={'US': 'not_an_opening'})


def test_the_default_is_what_shipped_before_the_books_were_named():
    """Adding the books must not move the bot. Changing which one is the
    default is a behaviour change and wants its own gate; until that runs
    the default stays where it was."""
    assert DEFAULT_OPENINGS == {'US': 'germany', 'USSR': 'austria'}
    engine = play_setup(DEFAULT_OPENINGS)
    assert engine.board.influence['West_Germany']['US'] == 5
    assert engine.board.influence['Italy']['US'] == 3
    assert engine.board.influence['Iran']['US'] == 2
    assert engine.board.influence['East_Germany']['USSR'] == 4
    assert engine.board.influence['Poland']['USSR'] == 4
    assert engine.board.influence['Austria']['USSR'] == 1
