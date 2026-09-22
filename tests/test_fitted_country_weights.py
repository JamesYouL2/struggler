"""The fitted per-country weights (`StrategicWeights.country_vp_scale`) and
the Europe Control price (`europe_control_vp`).

See docs/notes/claude/2026-09-18-fitted-country-weights.md. Shipped ON
since 2026-09-21, when the guessed `battleground`/`control` tiers and
`country_value`'s un-fitted half were deleted on the strength of +0.054
[+0.031, +0.078] paired against bc5ef93 (run 35614516089,
docs/notes/claude/2026-09-21-the-fresh-block-answers-the-fit.md). These
tests pin what the fit means, and that the tiers cannot come back.
"""
import dataclasses
import json
import math
import pathlib
import re

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


def test_the_shipped_scale_is_the_truncation_every_arm_actually_played():
    """`country_vp_scale` ships at the rounding of the file's `matched_scale`.

    The two differ in the fourth decimal -- 2.793341679085859 against the
    shipped 2.793 as of the 2026-09-22 refit at cec39ca (2.7949857573867254
    against 2.795 at the 2026-09-21 fit) -- and every arm that measured a
    fit was dispatched with the short form. Rankings are decided by strict
    comparison, so "close enough" is not a thing here: shipping the long
    form would ship a bot no arm has played. When a refit moves
    `matched_scale`, the new scale is measured before it is shipped -- the
    refit-vs-shipped arm plays this exact default and merges only if its
    interval clears -- and this assertion is where that conversation
    happens.
    """
    matched = json.loads(ev.FITTED_WEIGHTS_PATH.read_text())['matched_scale']
    shipped = StrategicWeights().country_vp_scale
    # The rule, stated rather than approximated by a tolerance: the shipped
    # scale is `matched_scale` rounded to three decimals. A bare tolerance
    # was 1e-4, which only passed because 2.7949857... happens to sit almost
    # exactly on 2.795; a three-decimal rounding may move by up to 5e-4, so
    # the tolerance would have rejected the next refit for being ordinary.
    assert shipped == 2.793 == round(matched, 3)
    assert shipped != matched, 'the long form is not what any arm played'


def test_country_value_is_linear_in_the_scale_so_it_is_a_level_knob():
    """Doubling `country_vp_scale` doubles every country value.

    That is what makes `matched_scale` meaningful as a *level*: all four
    terms multiply importance, and `access` prices the battlegrounds it
    reaches through the same `importance` call, so the scale factors
    straight out of `country_value`. It is also what makes the scale sweep
    (half and double, both measurably worse) a test of the level alone.

    A term that read the scale non-linearly -- or one that priced part of
    the country layer on something else, which is exactly what the deleted
    tier fallback did inside `access` -- breaks this.
    """
    engine = bare_engine()
    for cid, side, n in (('France', 'US', 3), ('Iran', 'USSR', 2),
                         ('Venezuela', 'US', 2), ('Cameroon', 'USSR', 1)):
        engine.board.influence[cid][side] = n
    t = ev.terrain()
    pos = ev.Position(t).sync(engine.board)
    urgency = ev.ones(t)
    one = StrategicWeights(country_vp_scale=1.0)
    two = StrategicWeights(country_vp_scale=2.0)
    for i in range(len(t.ids)):
        for side in (ev.US, ev.USSR):
            assert ev.country_value(t, pos, i, side, two, urgency) == pytest.approx(
                2.0 * ev.country_value(t, pos, i, side, one, urgency), abs=1e-9), t.ids[i]


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


def test_the_guessed_tiers_are_gone_and_cannot_come_back():
    """`battleground` and `control` are deleted, and nothing may re-add them.

    They were a guessed 5.0/1.5 pair that gave every battleground on the
    map the same importance, and their last bug was subtler than their
    flatness: `access` called `importance` without a side, the fitted
    branch was guarded on `s is not None`, so the tiebreaker priced the
    battlegrounds it reached on the tiers while control, progress and the
    reserve were on fitted VP. Two scales inside one `country_value` (bug
    shape 6), with `w.access` multiplying the stale half.

    This test used to state that as a value property -- with the fit on,
    moving the tiers must move nothing -- and that property is now
    unstateable, because there is nothing to move. What replaces it is the
    deletion itself: the fields are gone, and no source file in the
    strategic package names them as weights. The failure this guards is
    someone re-introducing a guessed per-country or per-battleground tier
    *beside* the fit, which is how two scales got into one value the first
    time.

    docs/notes/claude/2026-09-21-the-fresh-block-answers-the-fit.md
    """
    fields = {f.name for f in dataclasses.fields(StrategicWeights)}
    assert not ({'battleground', 'control'} & fields), (
        'the guessed country tiers are back as weights. The fit owns the country '
        'layer; a second tier weight beside it is two scales in one value again.')

    strategic = pathlib.Path(ev.__file__).parent
    offenders = []
    for path in sorted(strategic.glob('*.py')):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'\bw(eights)?\.(battleground|control)\b', line):
                offenders.append(f'{path.name}:{n}: {line.strip()}')
    assert not offenders, 'weights-level tier reads are back:\n' + '\n'.join(offenders)

    # The board fact stays forever and is a different thing entirely:
    # `defcon.py` alone reads it five times to answer "can the opponent Coup
    # a Battleground and lower DEFCON". This asserts the two did not get
    # deleted together.
    t = ev.terrain()
    assert any(t.battleground) and not all(t.battleground)
