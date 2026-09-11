"""Every tunable constant declares where its value came from.

The code documents each number's *reasoning* well and its *standing*
nowhere, so nothing distinguishes a rate measured over 973 samples from one
that has never been questioned. `models/provenance.json` records both, and
this keeps it honest: a constant added without an entry fails, and an entry
for a constant that no longer exists fails too, so the ledger cannot rot
into a description of a bot that used to exist.

It deliberately does **not** pin the values themselves -- other tests do
that, and duplicating them here would mean every tuning change touched two
files. What is pinned is that a value and its declared provenance agree,
which is the part that silently stops being true.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest

from struggler.bots.strategic import StrategicWeights
from struggler.bots.strategic.defcon import SurvivalPrior

LEDGER = pathlib.Path(__file__).parent.parent / 'models' / 'provenance.json'
STRATEGIC = pathlib.Path(__file__).parent.parent / 'src' / 'struggler' / 'bots' / 'strategic'
SOURCES = {'measured', 'gate', 'expert', 'derived', 'guess'}
DETERMINATIONS = {'overdetermined', 'determined', 'bounded', 'underdetermined',
                  'known-wrong', 'inert'}
# Module-level constants that are not valuations: indices, sentinels, table
# sizes. They shape behaviour but there is no "where did this number come
# from" to answer about NOBODY = -1.
NOT_A_VALUATION = {'LAST_TURN', 'NOBODY', 'US', 'USSR', '_ZOBRIST_MAX',
                   'WIN_PROBABILITY_FLOOR', 'GAME_SWING_VP_LEGACY'}


@pytest.fixture(scope='module')
def ledger():
    return json.loads(LEDGER.read_text())


def test_every_weight_and_prior_has_an_entry(ledger):
    for cls, section in ((StrategicWeights, 'StrategicWeights'),
                         (SurvivalPrior, 'SurvivalPrior')):
        declared = set(ledger[section])
        actual = {f.name for f in dataclasses.fields(cls)}
        assert actual - declared == set(), (
            f'{section} fields with no provenance entry: {sorted(actual - declared)}. '
            f'Add them to models/provenance.json saying where the number came from.')
        assert declared - actual == set(), (
            f'{section} entries for fields that no longer exist: '
            f'{sorted(declared - actual)}')


def test_every_module_constant_has_an_entry(ledger):
    """Module-level numeric constants too, which is where `CHINA_HOLD_RAW`
    hid a 30x units error behind a confident name."""
    declared = set(ledger['constants'])
    found = set()
    for path in sorted(STRATEGIC.glob('*.py')):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not (isinstance(target, ast.Name) and target.id.isupper()):
                continue
            if target.id in NOT_A_VALUATION:
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)) \
                    and not isinstance(node.value.value, bool):
                found.add(target.id)
    assert found - declared == set(), (
        f'numeric constants with no provenance entry: {sorted(found - declared)}. '
        f'Add them to models/provenance.json, or to NOT_A_VALUATION if the '
        f'number is an index or a budget rather than a valuation.')


def test_declared_values_match_the_code(ledger):
    """A ledger that has drifted from the values is worse than none, because
    it reads as evidence."""
    for cls, section in ((StrategicWeights, 'StrategicWeights'),
                         (SurvivalPrior, 'SurvivalPrior')):
        instance = cls()
        for name, entry in ledger[section].items():
            assert getattr(instance, name) == entry['value'], (
                f'{section}.{name} is {getattr(instance, name)} but the ledger '
                f'says {entry["value"]}')
    from struggler.bots.strategic import evaluator as ev, policy, stakes
    for name, entry in ledger['constants'].items():
        found = next((getattr(m, name) for m in (stakes, policy, ev)
                      if hasattr(m, name)), None)
        assert found is not None, f'{name} is in the ledger but not in the code'
        assert found == entry['value'], f'{name} is {found}, ledger says {entry["value"]}'


def test_the_vocabulary_is_closed(ledger):
    for section in ('StrategicWeights', 'SurvivalPrior', 'constants'):
        for name, entry in ledger[section].items():
            assert entry['source'] in SOURCES, f'{name}: unknown source {entry["source"]}'
            assert entry['determination'] in DETERMINATIONS, \
                f'{name}: unknown determination {entry["determination"]}'


def test_the_summary_counts_match_the_entries(ledger):
    """The headline -- half the constants are guesses -- is the reason this
    file exists, so it must not be a number someone typed once."""
    entries = [e for section in ('StrategicWeights', 'SurvivalPrior', 'constants')
               for e in ledger[section].values()]
    for field, key in (('counts_by_source', 'source'),
                       ('counts_by_determination', 'determination')):
        actual: dict[str, int] = {}
        for entry in entries:
            actual[entry[key]] = actual.get(entry[key], 0) + 1
        assert ledger['_summary'][field] == actual, (
            f'_summary.{field} says {ledger["_summary"][field]} but the entries '
            f'are {actual}')
