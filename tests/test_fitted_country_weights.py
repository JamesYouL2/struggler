"""The fitted per-country weights (`StrategicWeights.country_vp_scale`) and
the Europe Control price (`europe_control_vp`).

See docs/notes/claude/2026-09-18-fitted-country-weights.md. On by default
since 2026-09-18 (the parity corpus still pins the tiers: its records carry
country_vp_scale 0.0 from capture); these tests pin what the fit means.
"""
import dataclasses
import math
import json

import pytest

from conftest import bare_engine
from struggler.engine import Engine, Region
from struggler.bots.strategic import StrategicWeights
from struggler.bots.strategic import evaluator as ev


def fitted_weights():
    return StrategicWeights(country_vp_scale=json.loads(ev.FITTED_WEIGHTS_PATH.read_text())['matched_scale'])


def test_the_fitted_file_covers_every_country_for_both_sides_and_says_where_it_came_from():
    data = json.loads(ev.FITTED_WEIGHTS_PATH.read_text())
    t = ev.terrain()
    assert set(data['weights']) == set(t.ids)
    assert all(set(per) == {'US', 'USSR'} for per in data['weights'].values())
    for field in ('source_revision', 'generator_sha256', 'seeds', 'positions', 'matched_scale'):
        assert data[field], field
    assert data['europe_control_vp'] == ev.EUROPE_CONTROL_VP
    assert data['matched_scale'] > 0


def test_fitted_importance_is_the_weight_times_the_region_mass_plus_southeast_asias_exact_payout():
    t = ev.terrain()
    table = ev._fitted_table(t.ids)
    urgency = tuple(1.0 + 0.01 * i for i in range(len(t.ids)))
    thailand, burma, france = (t.index[c] for c in ('Thailand', 'Burma', 'France'))
    asia = urgency[t.region_anchor[Region.ASIA]]
    assert ev.fitted_importance(t, urgency, france, ev.US) == pytest.approx(
        table[ev.US][france] * urgency[t.region_anchor[Region.EUROPE]])
    assert ev.fitted_importance(t, urgency, thailand, ev.USSR) == pytest.approx(
        table[ev.USSR][thailand] * asia + 2.0 * (urgency[thailand] - asia))
    assert ev.fitted_importance(t, urgency, burma, ev.US) == pytest.approx(
        table[ev.US][burma] * asia + 1.0 * (urgency[burma] - asia))


@pytest.mark.parametrize('seed', [4000, 4001])
def test_fitted_country_values_are_zero_sum_across_the_seats(seed):
    # Our control is priced at our weight and theirs at theirs, so the two
    # seats must still read every country as the same amount with opposite
    # signs -- the split is between sides, not between viewpoints.
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    board = engine.board
    for c, (us, ussr) in {'France': (3, 0), 'Iran': (0, 3), 'Panama': (1, 0), 'Thailand': (0, 1),
                          'Egypt': (2, 2), 'Mexico': (0, 4)}.items():
        board.influence[c]['US'], board.influence[c]['USSR'] = us, ussr
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    w = fitted_weights()
    urgency = ev.ones(t)
    for i in range(len(t.ids)):
        us = ev.country_value(t, pos, i, ev.US, w, urgency)
        ussr = ev.country_value(t, pos, i, ev.USSR, w, urgency)
        assert us == pytest.approx(-ussr, abs=1e-9), t.ids[i]


def test_switching_the_fit_on_changes_country_values_and_off_leaves_the_tiers():
    engine = bare_engine()
    engine.board.influence['France']['US'] = 3
    t = ev.terrain()
    pos = ev.Position(t).sync(engine.board)
    france, urgency = t.index['France'], ev.ones(t)
    off = StrategicWeights(country_vp_scale=0.0)
    assert ev.importance(t, off, urgency, france, ev.US) == off.battleground
    assert ev.country_value(t, pos, france, ev.US, fitted_weights(), urgency) != \
        ev.country_value(t, pos, france, ev.US, off, urgency)


@pytest.mark.parametrize('price', [20.0, 40.0, 60.0])
def test_europe_control_is_priced_at_the_weight(price):
    engine = bare_engine()
    t = ev.terrain()
    for c in (t.ids[i] for i in t.members[Region.EUROPE] if t.battleground[i]):
        engine.board.influence[c]['US'] = 5
    engine.board.influence['Finland']['US'] = 5
    pos = ev.Position(t).sync(engine.board)
    assert ev.region_vp(t, pos, Region.EUROPE, europe_control_vp=price) == price
    assert ev.region_vp(t, pos, Region.EUROPE) == 40.0
    assert StrategicWeights().europe_control_vp == 40.0
    fields = {f.name for f in dataclasses.fields(StrategicWeights)}
    assert {'country_vp_scale', 'europe_control_vp'} <= fields


def test_the_europe_curve_is_continuous_monotone_and_reaches_the_auto_win_only_at_control():
    # 20*tanh(x/k): odd, increasing, strictly inside +/-20 for any score
    # short of Control, and exactly +/-20 at Control (value_for's None).
    k = 10.0
    xs = [x / 2 for x in range(-30, 31)]
    ys = [ev.europe_curve_vp(x, 0, k) for x in xs]
    assert all(b > a for a, b in zip(ys, ys[1:], strict=False))
    assert all(abs(y) < ev.AUTO_VICTORY_VP for y in ys)
    assert ev.europe_curve_vp(3, 3, k) == 0
    assert ev.europe_curve_vp(None, 5, k) == ev.AUTO_VICTORY_VP == 20.0
    assert ev.europe_curve_vp(4, None, k) == -20.0


def test_the_europe_curve_prices_only_europe_and_off_is_the_tiers():
    engine = bare_engine()
    t = ev.terrain()
    for c in ('France', 'Italy', 'West_Germany', 'Panama', 'Iran'):
        engine.board.influence[c]['US'] = 5
    pos = ev.Position(t).sync(engine.board)
    tiers = ev.region_vp(t, pos, Region.EUROPE)
    assert ev.region_vp(t, pos, Region.EUROPE, europe_curve=10.0) == pytest.approx(
        20 * math.tanh(tiers / 10.0))
    for region in (Region.CENTRAL_AMERICA, Region.MIDDLE_EAST):
        assert ev.region_vp(t, pos, region, europe_curve=10.0) == ev.region_vp(t, pos, region)
    assert StrategicWeights().europe_curve == 0.0


def test_the_fit_owns_the_whole_country_layer_and_the_guessed_tiers_are_not_read():
    """With `country_vp_scale` set, nothing under `country_value` may still
    read `battleground`/`control`.

    Shipped at 0.0, the fit rescales a country's importance from a guessed
    tier to fitted VP -- and `country_value` multiplies that importance into
    four terms: control, progress, the reserve, and `access`. `access` took
    the tier path regardless, because it called `importance` without a side
    and the fitted branch is guarded on `s is not None`. So Italy was worth
    7.136 to the three terms that read the fit and 5.000 to the one that did
    not: two scales inside one value, with `w.access` (1.5) multiplying the
    stale half -- and `access` is the tiebreaker
    (docs/notes/claude/2026-09-12-access-is-the-tiebreaker.md).

    The property, stated so it cannot rot: with the fit on, moving the tier
    weights must move nothing. That is also exactly what
    `docs/notes/claude/2026-09-20-finishing-the-vp-rebuild.md` step 4 needs
    before those two fields can be deleted.
    """
    engine = bare_engine()
    # A board with reach to price: influence next to uncontrolled battlegrounds.
    for cid, side, n in (('France', 'US', 3), ('Iran', 'USSR', 2),
                         ('Venezuela', 'US', 2), ('Cameroon', 'USSR', 1)):
        engine.board.influence[cid][side] = n
    t = ev.terrain()
    pos = ev.Position(t).sync(engine.board)
    urgency = ev.ones(t)

    fit = fitted_weights()
    # Same fit, absurd tiers. If any term still reads them, a value moves.
    moved = dataclasses.replace(fit, battleground=500.0, control=250.0)

    for i in range(len(t.ids)):
        for side in (ev.US, ev.USSR):
            assert ev.country_value(t, pos, i, side, fit, urgency) == \
                pytest.approx(ev.country_value(t, pos, i, side, moved, urgency), abs=1e-9), \
                f'{t.ids[i]} still reads the guessed tiers with the fit on'

    # And the negative control: with the fit OFF the tiers must still bite,
    # or the assertion above would pass for the wrong reason.
    off = StrategicWeights(country_vp_scale=0.0)
    off_moved = dataclasses.replace(off, battleground=500.0, control=250.0)
    france = t.index['France']
    assert ev.country_value(t, pos, france, ev.US, off, urgency) != \
        ev.country_value(t, pos, france, ev.US, off_moved, urgency)
