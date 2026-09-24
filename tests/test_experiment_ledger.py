"""The experiment ledger: one record per reading, and no arm without one.

`models/experiment_ledger.json` exists because of a defect on 2026-09-24:
the ablation sweep dispatched five arms whose questions run 35306328917 had
already answered at the same sample, because those verdicts lived only in a
prose note while the registry's arm contexts read as unrun. The ledger is
the map the next dispatch consults FIRST -- knob -> runs -> readings ->
telling -- so a duplicated question is visible before the runners are
spent. These tests keep the map complete (every registered arm has an
entry) and honest (every entry points at a telling that exists).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'models/experiment_ledger.json'
REGISTRY = ROOT / '.github/experiments.json'

REQUIRED = {'id', 'kind', 'knobs', 'run', 'reading', 'verdict', 'status', 'notes'}
STATUS = {'answered', 'in_flight', 'unrecorded'}


def _readings() -> list[dict]:
    return json.loads(LEDGER.read_text())['readings']


def test_the_ledger_parses_and_keeps_the_ledger_format() -> None:
    # The provenance convention: 2-space indent, never plain `json.dumps`
    # (compact) -- a test parses this file, and so do agents by eye.
    text = LEDGER.read_text()
    for marker in ('<<<<<<<', '>>>>>>>'):
        assert marker not in text, f'{LEDGER.name} still holds a {marker} conflict marker'
    data = json.loads(text)
    assert data['readings'], 'the ledger has no readings'
    assert text == json.dumps(data, indent=2) + '\n', (
        f'{LEDGER.name} is not 2-space-indented json.dumps output; regenerate it, '
        'do not hand-edit the format')


def test_every_entry_points_at_a_telling_that_exists() -> None:
    for r in _readings():
        assert REQUIRED <= r.keys(), f"{r.get('id')}: missing {sorted(REQUIRED - r.keys())}"
        assert r['status'] in STATUS, f"{r['id']}: status {r['status']!r} not in {sorted(STATUS)}"
        assert r['notes'], f"{r['id']}: no note -- a reading with no telling is how run 35306328917 got duplicated"
        for note in r['notes']:
            assert (ROOT / note).is_file(), f"{r['id']}: {note} does not exist"


def test_ids_are_unique() -> None:
    ids = [r['id'] for r in _readings()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f'one measurement, one entry: duplicated ids {sorted(dupes)}'


def test_every_registered_arm_has_an_entry() -> None:
    # The anti-duplication gate. An arm in the registry without a ledger
    # entry is invisible to the grep the next sweep makes -- exactly the
    # gap that produced five replicated arms.
    reg = json.loads(REGISTRY.read_text())
    slugs = {a['slug'] for a in reg['experiments']} | {a['slug'] for a in reg['_retired']['arms']}
    have = {r['id'] for r in _readings()}
    missing = sorted(slugs - have)
    assert not missing, (
        f'registry arms with no ledger entry (add one at dispatch time): {missing}')


def test_an_in_flight_entry_has_a_run() -> None:
    for r in _readings():
        if r['status'] == 'in_flight':
            assert r['run'], f"{r['id']}: in flight with no run id -- the read will not find it"
