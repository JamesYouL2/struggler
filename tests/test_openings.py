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


# -- the benchmark's seed-keyed selection ------------------------------------


def test_seed_keyed_openings_walk_every_combination():
    """Nine starting boards, not three: the two seats advance on different
    cycles so a seed range reaches all of them."""
    from struggler.bots.benchmark import openings_for_seed
    seen = {tuple(sorted(openings_for_seed(s).items())) for s in range(4000, 4009)}
    assert len(seen) == len(OPENINGS['US']) * len(OPENINGS['USSR'])


def test_the_opening_is_a_property_of_the_seed_not_the_arm():
    """What keeps the gate paired. The seed is its unit of observation
    (`benchmark.seed_scores`), so both arms of a seed must get the same
    board -- exactly as they get the same deal. If the arms could differ,
    the opening would stop cancelling out of the measured difference and
    start being part of it."""
    from struggler.bots.benchmark import openings_for_seed
    for seed in range(4000, 4020):
        assert openings_for_seed(seed) == openings_for_seed(seed)
        assert set(openings_for_seed(seed)) == {'US', 'USSR'}
        for side, name in openings_for_seed(seed).items():
            assert name in OPENINGS[side]


def test_a_baseline_without_opening_books_is_refused_not_silently_paired():
    """A pre-v0.2.0 baseline cannot be given an opening, and the two arms
    would then start from *different* boards -- which is the one thing
    this whole mechanism exists to prevent. It has to say so."""
    import pytest as _pytest

    from struggler.bots.benchmark import build

    class Old:
        def __init__(self, weights=None):
            pass

    import struggler.bots.benchmark as bm
    original = bm.StrategicPlayer
    bm.StrategicPlayer = Old
    try:
        assert isinstance(build('strategic', 4000, 24), Old)   # fine without books
        with _pytest.raises(ValueError, match='predates the opening books'):
            build('strategic', 4000, 24, None, {'US': 'france', 'USSR': 'poland'})
    finally:
        bm.StrategicPlayer = original


def test_openings_can_be_pinned_explicitly():
    from struggler.bots.benchmark import parse_openings
    assert parse_openings('US=france,USSR=austria') == {'US': 'france', 'USSR': 'austria'}
    assert parse_openings(' US=italy , USSR=poland ') == {'US': 'italy', 'USSR': 'poland'}


def test_pinning_must_name_both_seats():
    """Defaulting the unnamed seat would let two runs differ in a book
    nobody wrote down -- the confound the option exists to remove."""
    import pytest as _pytest

    from struggler.bots.benchmark import parse_openings
    with _pytest.raises(ValueError, match='both seats'):
        parse_openings('US=france')
    with _pytest.raises(ValueError, match='bad opening'):
        parse_openings('US=nope,USSR=austria')
