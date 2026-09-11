"""One parameter for what winning is worth, and nowhere else to redefine it.

The bot had four numbers for the same fact and no two agreed: `LOSS` at a
million, `GAME_SWING_VP` at 40, `region_vp`'s Europe Control stand-in at
100, and an unimplemented win-probability ceiling. Three of the four had no
recorded derivation. They are one quantity -- what turning this position
into a certain win is worth -- and separately tuned numbers for one
quantity drift apart, which is how they got to 40, 100 and a million.

`stakes.AUTO_VICTORY_VP` is now the only free parameter and the rest are
expressions in it. These tests pin that: the derivations, and that no other
module quietly grows its own copy.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from struggler.bots.strategic import stakes

STRATEGIC = pathlib.Path(__file__).parent.parent / 'src' / 'struggler' / 'bots' / 'strategic'
DERIVED = ('GAME_SWING_VP', 'EUROPE_CONTROL_VP')


def test_every_stake_is_derived_from_the_one_parameter():
    assert stakes.GAME_SWING_VP == 2 * stakes.AUTO_VICTORY_VP
    assert stakes.EUROPE_CONTROL_VP == stakes.AUTO_VICTORY_VP


def test_moving_the_parameter_moves_everything(monkeypatch):
    """Not a tautology worth skipping: it is the property that failed. If a
    derived name is ever re-frozen as a literal, the module still imports and
    still passes the equality above at the default -- and silently stops
    following. Recomputing from a changed parameter is what catches that."""
    src = (STRATEGIC / 'stakes.py').read_text().replace(
        'AUTO_VICTORY_VP = 20.0', 'AUTO_VICTORY_VP = 30.0')
    namespace: dict = {}
    exec(compile(src, 'stakes.py', 'exec'), namespace)
    assert namespace['AUTO_VICTORY_VP'] == 30.0
    assert namespace['GAME_SWING_VP'] == 60.0, 'GAME_SWING_VP stopped following'
    assert namespace['EUROPE_CONTROL_VP'] == 30.0, 'EUROPE_CONTROL_VP stopped following'


def test_no_other_module_defines_its_own_stake():
    """The drift guard. A second definition anywhere else is how there came
    to be four numbers for one fact."""
    offenders = []
    for path in sorted(STRATEGIC.glob('*.py')):
        if path.name == 'stakes.py':
            continue
        tree = ast.parse(path.read_text())
        for node in tree.body:                      # module level only
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign) else [])
            for target in targets:
                if isinstance(target, ast.Name) and target.id in DERIVED:
                    offenders.append(f'{path.name}:{node.lineno} {target.id}')
    assert not offenders, (
        'these redefine a stake that belongs to stakes.py, which is how four '
        f'disagreeing numbers for one fact came about: {offenders}')


def test_win_probability_is_calibrated_against_the_same_parameter():
    """The link the maintainer asked for, so a VP constant and a win
    probability cannot disagree about what a win is worth."""
    assert stakes.value_of_win_probability(1.0) == stakes.AUTO_VICTORY_VP
    assert stakes.value_of_win_probability(0.0) == -stakes.AUTO_VICTORY_VP
    assert stakes.value_of_win_probability(0.5) == 0.0


@pytest.mark.parametrize('raw, expected', [
    (0.99, 0.90), (1.0, 0.90), (0.5, 0.5), (0.01, 0.10), (-5.0, 0.10)])
def test_an_estimator_is_never_allowed_to_be_certain(raw, expected):
    """The ceiling is a constraint on the output, not something the data
    teaches. A model fitted to outcomes will report 0.99 from a dominant
    board, and that inverts the term it feeds: the point of knowing you are
    behind is to start taking DEFCON and Europe Control shots."""
    assert stakes.clipped_win_probability(raw) == pytest.approx(expected)
