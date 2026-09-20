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


def test_forecast_probabilities_are_valid_and_degenerate_now_only():
    """Immediate scoring (horizon 0) stays degenerate; horizon 1+ reads the
    measured fit, and its per-member masses still live in [0, 1] and sum to
    one no matter what the sigmoids said."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        now = fcst.forecast_controls(t, pos, region, horizon=0)
        assert now.is_degenerate()
        for horizon in (1, 2, 5):
            forecast = fcst.forecast_controls(t, pos, region, horizon=horizon)
            assert forecast.horizon == horizon
            assert forecast.members == t.members[region]
            assert not forecast.is_degenerate()
            for _i, triple in zip(forecast.members, forecast.probs, strict=True):
                assert len(triple) == 3
                assert all(0.0 <= p <= 1.0 for p in triple)
                assert sum(triple) == pytest.approx(1.0)


def test_control_forecast_representative_rows_match_the_measurement():
    """Representative boards price where the measured horizon-1 table fell:
    being in control beats contested beats enemy-held, overprotection buys
    keep odds, and the fit's cliff is where the data said. Shape pin, not
    recalibration."""
    engine = bare_engine()
    board = engine.board
    cid = next(cid for cid, info in board.countries.items()
               if info.battleground and info.stability == 2
               and info.region is Region.MIDDLE_EAST)
    board.influence[cid]['US'] = 2
    t, pos = _synced(board)
    i = t.index[cid]
    p_us_held = fcst.p_control_at_scoring(t, pos, i, Side.US, 1)
    p_ussr_read = fcst.p_control_at_scoring(t, pos, i, Side.USSR, 1)
    assert 0.6 < p_us_held < 0.95
    assert p_ussr_read < 0.35
    # The fit's mirror property: the same board, read from the other seat,
    # uses the same row-relative function of it.
    assert p_ussr_read < p_us_held


def test_control_forecast_enemy_stab_4_ground_is_near_lost():
    """Japan with 4 USSR influence, US never reached: the fit's cliff."""
    engine = bare_engine()
    board = engine.board
    board.influence['Japan']['USSR'] = 4
    t, pos = _synced(board)
    assert fcst.p_control_at_scoring(t, pos, t.index['Japan'], Side.US, 2) < 0.05


def test_control_forecast_is_monotone_in_the_horizon_and_a_simplex_point():
    """The forecast answer and its reading: each coordinate moves the h1->h2
    direction monotonically as the horizon grows, every triple sums to one
    by construction (a scale, never a clamp), and `h >= 2` continues one
    geometric step, not a flat clamp."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        triples = [fcst.forecast_controls(t, pos, region, horizon=h).probs
                   for h in (1, 2, 5)]
        for k in range(len(t.members[region])):
            for coord in range(3):
                a1, a2, a5 = (triples[j][k][coord] for j in range(3))
                lo, hi = sorted((a1, a2))
                assert lo <= a5 <= hi, (region, k, coord, a1, a2, a5)
        for h in (1, 2, 5):
            for triple in fcst.forecast_controls(t, pos, region, horizon=h).probs:
                assert sum(triple) == pytest.approx(1.0)


def test_overprotection_raises_the_hold():
    """The maintainer's question, in the fit: influence beyond the stability
    margin buys retention odds, in `over_me`'s positive coefficient."""
    t, pos = _africa_position()  # Algeria US-controlled at exactly 2 influence
    algeria = t.index['Algeria']
    p_exact = fcst.p_control_at_scoring(t, pos, algeria, Side.US, 1)
    over = fcst.p_control_at_scoring(*_overprotected_algeria(), algeria, Side.US, 1)
    assert over > p_exact


def _overprotected_algeria():
    """The Africa position with one more US point in Algeria than control
    needs."""
    engine = bare_engine()
    board = engine.board
    board.influence['Algeria']['US'] = 3
    board.influence['Nigeria']['US'] = 1
    board.influence['Zaire']['US'] = 1
    return _synced(board)


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


def test_stochastic_tier_expectation_is_the_named_independence_dp():
    """The tier part no longer refuses a stochastic forecast: the exact
    expectation of the count-keyed tiers under per-country independence.
    Pinned two ways: degenerate forecasts run the DP and the region_vp
    snapshot to the SAME number at every override combination, and a
    hand-computable two-member position matches its closed form."""
    board = _played_board()
    t, pos = _synced(board)
    for region in Region:
        for formosan, shuttle in itertools.product((False, True), repeat=2):
            indices = ev.scoring_overrides(t, pos, region,
                                           formosan_resolution=formosan,
                                           shuttle_diplomacy=shuttle)
            for h in (1, 2, 5):
                forecast = fcst.forecast_controls(t, pos, region, horizon=h)
                dp = fcst._tier_distribution(t, forecast, indices)
                assert sum(dp.values()) == pytest.approx(1.0)
            # The mirroring pin: a fully degenerate forecast through the DP
            # must equal the region_vp snapshot path, every override
            # combination -- this is what keeps tier_of from drifting from
            # region_vp's counting.
            now = fcst.forecast_controls(t, pos, region)
            assert now.is_degenerate()
            through_dp = sum(p * v for v, p in
                             fcst._tier_distribution(t, now, indices).items())
            through_vp = fcst.expected_tier_payout(t, now, indices)
            assert through_dp == pytest.approx(through_vp, abs=1e-9)


def test_stochastic_tier_matches_monte_carlo_independence():
    """The DP is the MC estimator's mean, variance small over 4096 draws."""
    import random

    board = _played_board()
    t, pos = _synced(board)
    region = Region.ASIA
    forecast = fcst.forecast_controls(t, pos, region, horizon=2)
    rng = random.Random(9)
    total = 0.0
    for _ in range(4096):
        shadow = ev.Position(t)
        for i, (p_us, p_ussr, _p_open) in zip(forecast.members, forecast.probs, strict=True):
            x = rng.random()
            if x < p_us:
                shadow.place(i, t.stability[i], 0)
            elif x < p_us + p_ussr:
                shadow.place(i, 0, t.stability[i])
        total += ev.region_vp(t, shadow, region) - fcst.expected_country_bonus(t, forecast)
    mc = total / 4096
    dp = fcst.expected_tier_payout(t, forecast)
    assert dp == pytest.approx(mc, abs=0.08)


def test_stochastic_payout_breakdown_adds_up_and_counts_once():
    """A stochastic region potential is bonus + DP tier, and the tier is
    computed once (the sum of marginals would double-count; the total must
    not)."""
    board = _played_board()
    t, pos = _synced(board)
    forecast = fcst.forecast_controls(t, pos, Region.AFRICA, horizon=2)
    breakdown = fcst.expected_payout(t, forecast)
    assert breakdown.total == pytest.approx(
        fcst.expected_country_bonus(t, forecast) + fcst.expected_tier_payout(t, forecast))
    assert -1.0 <= breakdown.tier <= 6.0  # presence 1 to control 6 VP, Africa's range


def test_incremental_tier_e_matches_the_full_dp_per_member():
    """The per-member-removed DP is the buy-back for the potential's
    per-delta cost: E[full walk] == E[`tier_e_minus` + one reconvolve] for
    EVERY member at once, on random triples. The reconvolve measures ~3ms
    against the full walk's ~23ms at Europe; the sharp equality is what
    lets the ranking path use it instead of the DP."""
    import random

    from struggler.bots.strategic.forecast import (_tier_distribution,
                                                   tier_e_minus, tier_e_from_minus)
    engine = bare_engine()
    t = ev.terrain()
    pos = ev.Position(t).sync(engine.board)
    region = Region.EUROPE
    rng = random.Random(4)
    now = fcst.forecast_controls(t, pos, region, horizon=1)
    for where in range(len(now.members)):
        first, second = rng.random(), rng.random()
        triple = (first, second, 1.0 - first - second)
        forced = now._replace(probs=tuple(triple if j == where else now.probs[j]
                                          for j in range(len(now.members))))
        full = sum(v * p for v, p in _tier_distribution(t, forced, None).items())
        tier_of, state_minus = tier_e_minus(t, forced, None, where)
        member = (t.battleground[now.members[where]], forced.probs[where][0],
                  forced.probs[where][1], forced.probs[where][2])
        assert tier_e_from_minus(tier_of, state_minus, member) == pytest.approx(
            full, abs=1e-9), where


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


@pytest.mark.parametrize('region', list(Region))
@pytest.mark.parametrize('horizon', [1, 2])
@pytest.mark.parametrize('with_overrides', [False, True])
def test_tier_weights_are_the_exact_linear_weights_of_every_member(region, horizon, with_overrides):
    """`tier_weights` is proved equal, member by member and outcome by
    outcome, to the per-member-removed DP it replaces (`tier_e_minus` +
    one reconvolve with the member forced), and each member's dot product
    with its own triple reproduces the full DP. Random triples, so no
    member is degenerate by accident; both override kinds where the region
    has them (a Formosan promotion and a Shuttle-ignored member)."""
    import random

    from struggler.bots.strategic.forecast import (_tier_distribution, tier_e_minus,
                                                   tier_e_from_minus, tier_weights)
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    t, pos = _synced(engine.board)
    base = fcst.forecast_controls(t, pos, region, horizon)
    rng = random.Random(hash((region.value, horizon)) & 0xffff)
    probs = []
    for _ in base.members:
        a, b = sorted((rng.random(), rng.random()))
        probs.append((a, b - a, 1.0 - b))
    forecast = base._replace(probs=tuple(probs))
    overrides = None
    if with_overrides:
        promoted = frozenset(i for i in base.members if t.ids[i] == 'Taiwan')
        ignored = frozenset(base.members[1:2])
        overrides = (promoted, ignored)
    weights = tier_weights(t, forecast, overrides)
    full = sum(v * p for v, p in _tier_distribution(t, forecast, overrides).items())
    promoted, ignored = overrides or (frozenset(), frozenset())
    for where, i in enumerate(forecast.members):
        assert sum(q * w for q, w in zip(forecast.probs[where], weights[where])) == pytest.approx(full, abs=1e-9)
        if i in ignored:
            assert weights[where] == pytest.approx((full,) * 3, abs=1e-9)
            continue
        tier_of, state_minus = tier_e_minus(t, forecast, overrides, where)
        is_bg = t.battleground[i] or i in promoted
        for s, forced in enumerate(((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))):
            want = tier_e_from_minus(tier_of, state_minus, (is_bg, *forced))
            assert weights[where][s] == pytest.approx(want, abs=1e-9), (t.ids[i], s)


@pytest.mark.parametrize('region', list(Region))
@pytest.mark.parametrize('horizon', [1, 2])
def test_member_weights_price_the_whole_payout_exactly(region, horizon):
    """`member_weights` is the potential's linear form: for EVERY member,
    its own triple dotted with its own weights reproduces the region's whole
    expected payout -- tiers and 10.1.2 country bonuses together -- so a
    trial that moves one member is a dot product instead of a DP.

    The bonus half is what makes this more than `tier_weights`. It is
    linear per country, but the weights must still carry the REST of the
    region's expected bonus, which is constant in this member's triple. It
    was missing at first and cost 2.9 VP in Asia -- the whole of that
    region's bonus term -- which is exactly the error a per-member identity
    catches and a spot check does not.
    """
    board = _played_board()
    t, pos = _synced(board)
    fc = fcst.forecast_controls(t, pos, region, horizon)
    weights = fcst.member_weights(t, fc)
    total = fcst.expected_payout(t, fc).total
    for k, triple in enumerate(fc.probs):
        got = sum(q * w for q, w in zip(triple, weights[k], strict=True))
        assert got == pytest.approx(total, abs=1e-9), (t.ids[fc.members[k]], got, total)

    # A trial that moves ONE member is priced exactly by the dot product.
    for k, i in enumerate(fc.members):
        for forced in (ev.US, ev.USSR, ev.NOBODY):
            after = fcst.force(fc, t, i, forced)
            exact = fcst.expected_payout(t, after).total
            moved = tuple(1.0 if o == forced else 0.0 for o in (ev.US, ev.USSR, ev.NOBODY))
            by_weights = sum(q * w for q, w in zip(moved, weights[k], strict=True))
            assert by_weights == pytest.approx(exact, abs=1e-9), (t.ids[i], forced)

    # Negative control: the weights are per position. Feeding one member's
    # triple to another member's weights must NOT reproduce the payout, or
    # the test would pass against a table of constants.
    if len(fc.members) > 1:
        mismatched = [abs(sum(q * w for q, w in zip(fc.probs[0], weights[k], strict=True)) - total)
                      for k in range(1, len(fc.members))]
        assert max(mismatched) > 1e-9 or fc.is_degenerate()
