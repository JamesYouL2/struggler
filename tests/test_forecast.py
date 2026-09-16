"""The Factor 1 one-region prototype: forecast accounting, not rankings.

`bots/strategic/forecast.py` prices a region's scoring as an expected VP
payout with the country-bonus and tier parts kept separate. These tests pin
the accounting contract from the rebuild README: immediate scoring agrees
with the engine, deterministic forecasts reproduce the exact board payout,
probabilities are valid, tiers are counted once per region, raw deltas
telescope, and the stochastic joint model raises instead of guessing.
"""
import itertools

import pytest
from conftest import bare_engine

from struggler.engine import Engine, Region, Side
from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic import forecast as fcst


def _played_board(seed: int = 4000, steps: int = 160):
    """A board with influence actually spread around it (mirrors test_evaluator)."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    for _ in range(steps):
        if engine.is_terminal:
            break
        engine.step(engine.pending_decision.options[0])
    return engine.board


def _synced(board):
    t = ev.terrain()
    return t, ev.Position(t).sync(board)


def test_immediate_potential_matches_region_vp_every_region():
    """The prototype shares `region_vp`'s counting, so its total agrees everywhere --
    including Europe's Control stand-in, which is a ranking number, not an engine one."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        assert fcst.region_potential(t, pos, Side.US, region).total == ev.region_vp(t, pos, region)


def test_immediate_potential_matches_engine_scoring_with_overrides():
    """Immediate scoring bypasses the forecast and reproduces `Board.score_region`,
    with the Formosan/Shuttle overrides in force as well as without."""
    board = _played_board()
    board.influence["Taiwan"]["US"] = board.countries["Taiwan"].stability
    t, pos = _synced(board)
    for formosan, shuttle in itertools.product((False, True), repeat=2):
        for region in Region:
            names = board.scoring_overrides(region, formosan_resolution=formosan,
                                            shuttle_diplomacy=shuttle)
            indices = ev.scoring_overrides(t, pos, region, formosan_resolution=formosan,
                                           shuttle_diplomacy=shuttle)
            try:
                expected = board.score_region(region, *names)
            except RuntimeError:
                continue  # Europe control: no VP either implementation can name
            got = fcst.region_potential(t, pos, Side.US, region, overrides=indices)
            assert got.total == expected


def test_forecast_probabilities_are_valid_and_degenerate():
    """US/USSR/uncontrolled mass per member lives in [0, 1] and sums to one."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        forecast = fcst.forecast_controls(t, pos, region, horizon=2)
        assert forecast.horizon == 2
        assert forecast.members == t.members[region]
        for i, triple in zip(forecast.members, forecast.probs, strict=True):
            assert len(triple) == 3
            assert all(0.0 <= p <= 1.0 for p in triple)
            assert sum(triple) == pytest.approx(1.0)
            holder = pos.control[i]
            assert triple == ((1.0, 0.0, 0.0) if holder == ev.US
                              else (0.0, 1.0, 0.0) if holder == ev.USSR
                              else (0.0, 0.0, 1.0))
        assert forecast.is_degenerate()


def test_horizon_and_holder_misuse_raise():
    t = ev.terrain()
    pos = ev.Position(t)
    with pytest.raises(ValueError):
        fcst.forecast_controls(t, pos, Region.AFRICA, horizon=-1)
    forecast = fcst.forecast_controls(t, pos, Region.AFRICA)
    with pytest.raises(ValueError):
        fcst.force(forecast, t, t.index["Nigeria"], 7)


def test_seat_signing_and_breakdown_add_up():
    """The USSR seat sees the negation, and total is bonus + tier by construction."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        us = fcst.region_potential(t, pos, Side.US, region)
        ussr = fcst.region_potential(t, pos, Side.USSR, region)
        assert (ussr.total, ussr.bonus, ussr.tier) == (-us.total, -us.bonus, -us.tier)
        assert us.total == us.bonus + us.tier


def _africa_position(us_extra=None):
    """A bare board where the US holds Algeria/Nigeria/Zaire; `us_extra` adds one more."""
    engine = bare_engine()
    board = engine.board
    board.influence["Algeria"]["US"] = 2
    board.influence["Nigeria"]["US"] = 1
    board.influence["Zaire"]["US"] = 1
    if us_extra is not None:
        board.influence[us_extra]["US"] = board.countries[us_extra].stability
    return _synced(board)


def test_nonbattleground_moves_tier_not_bonus():
    """Cameroon (non-BG, non-adjacent) completes domination: the bonus does not
    move, the tier jumps presence -> domination, and the marginal prices it whole."""
    t, pos = _africa_position()
    cameroon = t.index["Cameroon"]
    without = fcst.region_potential(t, pos, Side.US, Region.AFRICA)
    assert (without.total, without.bonus, without.tier) == (4.0, 3.0, 1.0)
    forecast = fcst.forecast_controls(t, pos, Region.AFRICA)
    assert fcst.marginal(t, Side.US, forecast, cameroon, ev.US) == 3.0
    t2, pos2 = _africa_position(us_extra="Cameroon")
    assert t2 is t
    with_ctrl = fcst.region_potential(t2, pos2, Side.US, Region.AFRICA)
    assert (with_ctrl.total, with_ctrl.bonus, with_ctrl.tier) == (7.0, 3.0, 4.0)


def test_country_bonus_is_linear_in_the_probabilities():
    """The bonus part is exact under any forecast: a 50/50 member splits the difference."""
    board = _played_board()
    t, pos = _synced(board)
    forecast = fcst.forecast_controls(t, pos, Region.AFRICA)
    i = forecast.members[0]
    mixed = forecast._replace(probs=((0.5, 0.5, 0.0), *forecast.probs[1:]))
    assert not mixed.is_degenerate()
    us_bonus = fcst.expected_country_bonus(t, fcst.force(forecast, t, i, ev.US))
    ussr_bonus = fcst.expected_country_bonus(t, fcst.force(forecast, t, i, ev.USSR))
    assert fcst.expected_country_bonus(t, mixed) == pytest.approx(0.5 * us_bonus + 0.5 * ussr_bonus)


def test_reordered_raw_changes_telescope():
    """Stepwise marginals sum to the endpoint difference in either order: the
    potential is a function of the final joint controls, not of the path."""
    engine = bare_engine()
    t, pos = _synced(engine.board)
    algeria, nigeria = t.index["Algeria"], t.index["Nigeria"]
    base = fcst.forecast_controls(t, pos, Region.AFRICA)
    p0 = fcst.expected_payout(t, base).total
    first = fcst.marginal(t, Side.US, base, algeria, ev.US)
    mid = fcst.force(base, t, algeria, ev.US)
    second = fcst.marginal(t, Side.US, mid, nigeria, ev.US)
    both = fcst.force(mid, t, nigeria, ev.US)
    assert first + second == fcst.expected_payout(t, both).total - p0
    other_first = fcst.marginal(t, Side.US, base, nigeria, ev.US)
    other_mid = fcst.force(base, t, nigeria, ev.US)
    other_second = fcst.marginal(t, Side.US, other_mid, algeria, ev.US)
    assert other_first + other_second == first + second


def test_stochastic_tier_expectation_raises_instead_of_guessing():
    """Per-country probabilities do not determine domination odds; the tier part
    refuses a stochastic forecast while the (linear, exact) bonus still computes."""
    board = _played_board()
    t, pos = _synced(board)
    forecast = fcst.forecast_controls(t, pos, Region.AFRICA)
    mixed = forecast._replace(probs=((0.5, 0.5, 0.0), *forecast.probs[1:]))
    assert fcst.expected_country_bonus(t, mixed) == pytest.approx(
        fcst.expected_country_bonus(t, forecast))
    with pytest.raises(NotImplementedError):
        fcst.expected_tier_payout(t, mixed)
    with pytest.raises(NotImplementedError):
        fcst.expected_payout(t, mixed)


def test_southeast_asia_payout_matches_the_engine():
    """The one-shot card pays per controlled SEA country (+2 Thailand), US-signed."""
    from conftest import bare_engine

    engine = bare_engine()
    board = engine.board
    board.influence["Thailand"]["US"] = 2
    board.influence["Vietnam"]["USSR"] = 1
    board.influence["Malaysia"]["US"] = 2  # stab 2, so 1 point would not control it
    assert engine._score_southeast_asia() == 2 - 1 + 1
    t, pos = _synced(board)
    forecast = fcst.forecast_controls(t, pos, Region.ASIA)
    assert fcst.expected_southeast_asia_payout(t, forecast) == 2.0


def test_southeast_asia_payout_is_linear_and_asia_only():
    """Per-country payout, exact under any forecast -- and it never prices Asia's tiers."""
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    t, pos = _synced(engine.board)
    forecast = fcst.forecast_controls(t, pos, Region.ASIA)
    thailand = t.index["Thailand"]
    mixed = forecast._replace(
        probs=tuple((0.5, 0.5, 0.0) if k == t.member_pos[thailand] else p
                    for k, p in enumerate(forecast.probs)))
    us_sea = fcst.expected_southeast_asia_payout(t, fcst.force(forecast, t, thailand, ev.US))
    ussr_sea = fcst.expected_southeast_asia_payout(t, fcst.force(forecast, t, thailand, ev.USSR))
    assert fcst.expected_southeast_asia_payout(t, mixed) == pytest.approx(0.5 * us_sea + 0.5 * ussr_sea)
    with pytest.raises(ValueError):
        fcst.expected_southeast_asia_payout(t, fcst.forecast_controls(t, pos, Region.AFRICA))


def test_europe_control_names_the_automatic_victory():
    """Holding every European battleground plus more countries is Control --
    the terminal outcome expected VP must never override."""
    from struggler.engine.types import ScoringTier

    from conftest import bare_engine

    engine = bare_engine()
    board = engine.board
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    assert fcst.europe_control(t, pos) is None
    europe_bg = [i for i in t.members[Region.EUROPE] if t.battleground[i]]
    non_bg = next(i for i in t.members[Region.EUROPE] if not t.battleground[i])
    assert len(europe_bg) > 0
    for i in europe_bg:
        board.influence[t.ids[i]]["US"] = t.stability[i]
    board.influence[t.ids[non_bg]]["US"] = t.stability[non_bg]
    pos = ev.Position(t).sync(board)
    assert board.region_tier(Side.US, Region.EUROPE) is ScoringTier.CONTROL
    assert fcst.europe_control(t, pos) is Side.US
    board.influence[t.ids[europe_bg[0]]]["USSR"] = 2 * t.stability[europe_bg[0]]
    pos = ev.Position(t).sync(board)
    assert fcst.europe_control(t, pos) is None
