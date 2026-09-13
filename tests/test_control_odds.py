"""The control-odds measurement and its fitter.

`scripts/measure_control_odds.py` records, per side and country per turn, the
Ops each side needs to take control and the overprotection each holds, and
who controls it when its region actually scores. `scripts/fit_control_odds.py`
fits candidate shapes for the maintainer's battleground formula to those rows.
A cost that misreads the doubling rule, or a scoring that resolves when no
scoring happened, would fit a formula to the wrong numbers without a sign.
"""
from __future__ import annotations

import importlib.util
import math
import random
from collections import defaultdict

import pytest

from conftest import ROOT, bare_engine, headline_setup
from struggler.engine import Action, DecisionKind, Side


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('stability', [1, 2, 3, 4])
def test_ops_to_control_pays_the_doubling_rule_exactly_as_the_board_does(stability):
    measure = _script('measure_control_odds')
    board = bare_engine(seed=1).board
    cid = next(c for c, info in board.countries.items() if info.stability == stability)
    for mine in range(6):
        for theirs in range(9):
            board.influence[cid]['US'], board.influence[cid]['USSR'] = mine, theirs
            stepped = 0
            while board.control(cid) is not Side.US:
                stepped += board.influence_cost(Side.US, cid)
                board.influence[cid]['US'] += 1
            assert measure.ops_to_control(mine, theirs, stability) == stepped, (mine, theirs)


def test_overprotection_is_influence_beyond_the_control_margin():
    measure = _script('measure_control_odds')
    assert measure.overprotection(5, 1, 2) == 2
    assert measure.overprotection(3, 1, 2) == 0   # exactly controlled
    assert measure.overprotection(1, 3, 2) == 0   # not ours at all


def _asia(engine):
    engine.defcon = 5
    engine.board.influence['Japan']['US'] = 4
    return engine


def _resolved(rows):
    return [r for r in rows if r['outcome'] is not None]


def test_a_headline_defectors_cancels_resolves_nothing():
    engine = _asia(bare_engine(seed=1))
    headline_setup(engine, 'Asia_Scoring', 'Defectors')
    tracker = _script('measure_control_odds').Tracker(engine)
    tracker.open()
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Asia_Scoring'}))
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Defectors'}))
    assert engine.vp == 0
    rows = tracker.result()
    assert rows and not _resolved(rows), 'no scoring happened, so nothing is decided'


def test_a_headline_scoring_resolves_its_region_and_only_it():
    engine = _asia(bare_engine(seed=1))
    headline_setup(engine, 'Asia_Scoring', 'Duck_and_Cover')
    tracker = _script('measure_control_odds').Tracker(engine, (1, 2))
    tracker.open()
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Asia_Scoring'}))
    engine.step(Action(DecisionKind.HEADLINE_PLAY, {'card': 'Duck_and_Cover'}))
    resolved = _resolved(tracker.result())
    japan = next(r for r in resolved if r['country'] == 'Japan' and r['side'] == 'US')
    assert (japan['controller'], japan['outcome'], japan['horizon']) == ('me', 'me', 1)
    assert japan['c_me'] == 0 and japan['c_opp'] == 9, 'USSR pays 2 once to break Japan, then 1 x 7'
    assert all(r['region'] == 'ASIA' and r['horizon'] == 1 for r in resolved)
    assert any(r['country'] == 'Japan' and r['horizon'] == 2 for _, r in tracker.pending), \
        'horizon 2 waits for the next Asia scoring'


def test_final_scoring_resolves_every_horizon_one_row():
    engine = _asia(bare_engine(seed=1))
    tracker = _script('measure_control_odds').Tracker(engine)
    tracker.open()
    engine._finish_game()
    rows = tracker.result()
    assert rows and len(_resolved(rows)) == len(rows)


def test_southeast_asia_scoring_resolves_only_southeast_asia():
    engine = _asia(bare_engine(seed=1))
    tracker = _script('measure_control_odds').Tracker(engine)
    tracker.open()
    engine._score_southeast_asia()
    resolved = {r['country'] for r in _resolved(tracker.result())}
    assert 'Thailand' in resolved and 'South_Korea' not in resolved and 'Japan' not in resolved


def test_the_fitter_recovers_known_coefficients():
    """Synthetic rows drawn from a known logistic model in c_me and c_opp."""
    fitter = _script('fit_control_odds')
    rng = random.Random(0)
    truth = (0.4, -0.9, 0.6)
    groups = defaultdict(lambda: [0, 0])
    for _ in range(40000):
        c_me, c_opp = rng.randint(0, 6), rng.randint(0, 6)
        p = 1 / (1 + math.exp(-(truth[0] + truth[1] * c_me + truth[2] * c_opp)))
        key = ('none', 2, c_me, c_opp, 0, 0, True, True)
        groups[key][0] += 1
        groups[key][1] += rng.random() < p
    beta = fitter.fit(groups, lambda r, lam: [r['c_me'], r['c_opp']], ridge=0.)
    assert beta == pytest.approx(truth, abs=0.06)


def test_the_true_shape_wins_on_held_out_rows():
    """Rows generated from the reciprocal form: the reciprocal form must beat
    the linear one on rows it was not fitted on, or the comparison means nothing."""
    fitter = _script('fit_control_odds')
    rng = random.Random(1)
    split = {'train': defaultdict(lambda: [0, 0]), 'test': defaultdict(lambda: [0, 0])}
    for i in range(60000):
        c_me, c_opp = rng.randint(0, 8), rng.randint(0, 8)
        p = 1 / (1 + math.exp(-(-0.2 + 3.0 / (1 + c_me) - 3.0 / (1 + c_opp))))
        cell = split['test' if i % 2 else 'train'][('none', 2, c_me, c_opp, 0, 0, True, True)]
        cell[0] += 1
        cell[1] += rng.random() < p
    scores = {}
    for name in ('A reciprocal', 'D linear'):
        fn = fitter.FORMS[name]
        beta = fitter.fit(split['train'], fn)
        scores[name] = fitter.score(split['test'], fitter.predictor(beta, fn, None))[0]
    assert scores['A reciprocal'] < scores['D linear'], scores
