"""`.github/experiments.json` is a registry a runner reads, so nothing in the
suite ever looked at it. Three things went wrong there in one week, and every
one of them only shows up on a dispatched runner, an hour after the mistake:

1. A merge left conflict markers in the file. `tests.yml` was green on that
   head because no test parses it; the first thing to notice would have been
   the workflow's `plan` step, on dispatch.
2. `margin-off-vs-07d553a` names `margin_presence`, `margin_battleground` and
   `margin_country`, which the region-margin deletion removed.
   `StrategicWeights.load` drops retired fields with an INFO log (that is
   deliberate: an old model file should still load), so the arm does not fail
   -- it runs as a copy of its base and reports as an ablation. A null
   ablation that looks like a measurement is worse than a crash.
3. Two arms claimed overlapping-but-different seed blocks (56000-56511 and
   56000-57023). Arms on the same block and opponent are paired on purpose;
   arms on a *partially* shared block look independent and are not.

The workflow's `plan` step already checks slugs, `bot_ref`/`weights` and
`compare_to` -- but only for the arms one dispatch selected, on a runner.
These are the checks that belong to the file itself.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from struggler.bots.strategic.policy import StrategicWeights

REGISTRY = Path(__file__).resolve().parents[1] / '.github' / 'experiments.json'


def _arms() -> list[dict]:
    return json.loads(REGISTRY.read_text())['experiments']


def _span(text: str) -> range:
    lo, hi = (int(x) for x in text.split('-'))
    return range(lo, hi + 1)


def test_the_registry_is_valid_json() -> None:
    # Defect 1: a conflict marker parses as nothing at all.
    text = REGISTRY.read_text()
    for marker in ('<<<<<<<', '>>>>>>>'):
        assert marker not in text, f'{REGISTRY.name} still holds a {marker} conflict marker'
    data = json.loads(text)
    assert data['experiments'], 'the registry has no arms'


def test_every_arm_weight_is_a_live_field() -> None:
    # Defect 2: `load` drops what it does not know, so a retired name turns an
    # ablation into a duplicate of its base. The registry has to name fields
    # that still exist.
    known = {f.name for f in fields(StrategicWeights)}
    retired: dict[str, list[str]] = {}
    for arm in _arms():
        gone = sorted(set(arm.get('weights') or {}) - known)
        if gone:
            retired[arm['slug']] = gone
    assert not retired, (
        'arms naming weights StrategicWeights no longer has; each would run as a '
        f'copy of its base and report as an ablation: {retired}')


def test_seed_blocks_are_identical_or_disjoint() -> None:
    # Defect 3: a partial overlap is the trap. Sharing a block is how arms are
    # paired; sharing *part* of one is two questions reading the same games
    # while presenting as independent.
    blocks: dict[str, set[int]] = {}
    for arm in _arms():
        for text in [arm['seeds']] + ([arm['held']] if arm.get('held') else []):
            blocks.setdefault(text, set(_span(text)))
    overlaps = []
    for a, b in ((a, b) for a in blocks for b in blocks if a < b):
        if blocks[a] & blocks[b]:
            overlaps.append((a, b))
    assert not overlaps, (
        'seed blocks that share seeds without being the same block; arms on them '
        f'read the same games while looking independent: {overlaps}')


@pytest.mark.parametrize('arm', _arms(), ids=lambda a: a['slug'])
def test_a_paired_arm_shares_its_base_block_and_opponent(arm: dict) -> None:
    # A paired difference cancels the deal, which only works when the two arms
    # were dealt the same games against the same bot.
    target = arm.get('compare_to')
    if not target:
        return
    by_slug = {a['slug']: a for a in _arms()}
    assert target in by_slug, f"{arm['slug']}: compare_to {target!r} is not an arm"
    base = by_slug[target]
    assert arm['seeds'] == base['seeds'], (
        f"{arm['slug']} is paired with {target} on a different seed block")
    assert arm.get('anchor', '') == base.get('anchor', ''), (
        f"{arm['slug']} is paired with {target} against a different opponent")
