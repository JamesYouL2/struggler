"""The access calibration resolves at a region's ACTUAL scoring.

Codex's audit F1 (docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md):
`scripts/measure_access_conversion.py` resolved every opportunity in a region
when an action NAMED that region's scoring card. A headline Defectors cancels
never scores, yet it produced two failed conversions and a retained Japan;
Final Scoring, which no card names, resolved nothing. Those figures are the
ones `CONVERSION_P` and the route decay were fitted to. The collector now
hooks the engine's own scoring on the one real engine, and these tests pin
the four cases the audit names as its acceptance.
"""
from __future__ import annotations

import importlib.util

from conftest import ROOT, bare_engine, headline_setup
from struggler.engine import Action, DecisionKind


def _script():
    spec = importlib.util.spec_from_file_location(
        'measure_access_conversion', ROOT / 'scripts' / 'measure_access_conversion.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _asia(engine):
    """US controls Japan (a held battleground) and reaches South Korea from it."""
    engine.defcon = 5
    engine.board.influence['Japan']['US'] = 4
    return engine


def _flat(samples):
    return [v for values in samples.values() for v in values]


def test_a_headline_defectors_cancels_resolves_nothing():
    """The audit's reproduction. The old collector saw `Asia_Scoring` in the
    USSR's headline pick and resolved Asia; the scoring never happened."""
    engine = _asia(bare_engine(seed=1))
    headline_setup(engine, 'Asia_Scoring', 'Defectors')
    tracker = _script().Tracker(engine)
    tracker.open()
    assert tracker.live and tracker.holding, 'the position must open something to resolve'
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Asia_Scoring'}))
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Defectors'}))
    assert engine.vp == 0 and engine.phase == 'action_rounds'
    result = tracker.result()
    assert result['reach'] == {} and result['keep'] == {}


def test_a_headline_scoring_that_happens_resolves_the_region():
    """The same position with a headline that does not cancel, so the test
    above is not passing merely because headlines never resolve."""
    engine = _asia(bare_engine(seed=1))
    headline_setup(engine, 'Asia_Scoring', 'Duck_and_Cover')
    tracker = _script().Tracker(engine)
    tracker.open()
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Asia_Scoring'}))
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Duck_and_Cover'}))
    result = tracker.result()
    assert True in _flat(result['keep']), 'Japan, held at the scoring, is a retained sample'
    assert _flat(result['reach']), 'South Korea, reached from Japan, is resolved'
    assert not any(cid == 'South_Korea' for _, _, cid in tracker.live)


def test_final_scoring_resolves_every_region():
    engine = _asia(bare_engine(seed=1))
    engine.board.influence['France']['USSR'] = 1   # a reach in Europe as well
    tracker = _script().Tracker(engine)
    tracker.open()
    assert any(engine.board.countries[c].region.name == 'EUROPE' for _, _, c in tracker.live)
    engine._finish_game()
    result = tracker.result()
    assert result['censored_reach'] == {} and result['censored_keep'] == {}
    assert _flat(result['reach']) and _flat(result['keep'])


def test_southeast_asia_scoring_resolves_only_southeast_asia():
    engine = _asia(bare_engine(seed=1))
    engine.board.influence['Laos_Cambodia']['US'] = 1   # reaches Thailand
    tracker = _script().Tracker(engine)
    tracker.open()
    assert any(cid == 'Thailand' for _, _, cid in tracker.live)
    engine._score_southeast_asia()
    assert not any(cid == 'Thailand' for _, _, cid in tracker.live)
    assert any(cid == 'South_Korea' for _, _, cid in tracker.live), \
        'Southeast Asia scoring does not score South Korea, so it stays open'
    assert tracker.holding, 'Japan is not in Southeast Asia and stays held'
