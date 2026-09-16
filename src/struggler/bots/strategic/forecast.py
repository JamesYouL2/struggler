"""One region's expected-scoring calculation: the Factor 1 prototype.

The value-function rebuild prices a region's future scoring as an expected VP
payout: probability the scoring occurs, times the expected board payout if it
does. This module is the payout half for a single region, Africa first: it
takes a position, a seat and a scoring horizon and returns the signed expected
payout with the country-bonus and regional-tier parts kept separate. It is NOT
wired into any ranking; the old evaluator and its corpus are untouched while
the candidate is built.

The prototype was built on Africa and is region-general: every function
takes the region (or card) as an argument, and immediate scoring agrees with
the engine in all six regions plus Southeast Asia's own payout. Two
region-specific rules ride along: Southeast Asia pays per controlled country
and never touches Asia's tiers, and Europe's Control tier is an automatic
victory -- `europe_control` names it, but expected VP must never override a
certain win or defeat, so its precedence over every payout here is
integration work (the rebuild's common-units step), not a number in this
module.

The rebuild README asks the first implementation five questions. Answers:

1. Partial influence -> control probability: the first forecast maps the
   board's current control (the same margin-vs-stability threshold `Position`
   uses) to degenerate 0/1 probabilities. Partial progress earns nothing yet.
   The September 13 control-odds fits are the evidence for the curve that
   replaces this, conditioned on the scoring occurring -- that conditioning
   must survive the replacement.
2. Access, Ops-to-control cost, overprotection: not inputs yet, by design.
   Access gates future acquisition (unreachable ground is ~0 to convert); the
   pointwise cost is the influence needed to tip the margin past stability
   against whoever holds; overprotection (margin above stability) currently
   scores the same as bare control although the retention fits say it
   matters. All three are named inputs of the next forecast, not this one.
3. Horizon: accepted and carried on the forecast, but the first approximation
   is horizon-invariant -- current control at every horizon. The scoring
   schedule (this turn / pre-reshuffle / later cycles / final) plus a
   per-cycle retention shapes it later; retention is per scoring cycle, never
   compounded per turn.
4. Tiers without multi-count: the tier payout is computed ONCE per region from
   the joint implied controls, through `evaluator.region_vp`'s own counting --
   never per country. A country's value is derived afterwards as a potential
   difference (`marginal`), and differences are never summed back into a total.
5. Correlation: a deterministic forecast is perfectly correlated through the
   shared board, and the payout is exact. A stochastic forecast needs the
   JOINT distribution -- per-country probabilities do not determine domination
   odds -- so `expected_tier_payout` raises instead of guessing: neither the
   independence approximation nor modal substitution is applied silently (the
   first misprices domination, the second violates Jensen).
"""
from __future__ import annotations

from typing import NamedTuple

from struggler.engine import Region, Side
from struggler.bots.strategic import evaluator as ev


class ControlForecast(NamedTuple):
    """Per-country control probabilities for one region at one horizon.

    `members` are the region's country indices in `Terrain` order and `probs`
    aligns with it: `(p_us, p_ussr, p_open)` per member, each in [0, 1],
    summing to one. `horizon` is the scoring opportunity's index (0 is a
    scoring now); the first forecast is horizon-invariant by design (see the
    module docstring, question 3) but the horizon rides along so callers and
    tests already thread it.
    """

    region: Region
    members: tuple[int, ...]
    probs: tuple[tuple[float, float, float], ...]
    horizon: int

    def is_degenerate(self) -> bool:
        """Whether every member puts all its mass on one outcome."""
        return all(max(triple) == 1.0 for triple in self.probs)


class Breakdown(NamedTuple):
    """A region's expected payout, US-signed, with its two parts kept apart.

    `total` is `bonus + tier` by construction; the tests pin `total` against
    `evaluator.region_vp` (same counting) and the engine (same rules).
    """

    total: float
    bonus: float
    tier: float


def forecast_controls(t: ev.Terrain, pos: ev.Position, region: Region, horizon: int = 0) -> ControlForecast:
    """The first control forecast: current control, degenerate, at any horizon.

    Each member controlled by the US (USSR) forecasts (1, 0, 0) ((0, 1, 0));
    uncontrolled forecasts (0, 0, 1). Partial influence, access, Ops costs and
    overprotection do not move it yet -- questions 1 and 2 above name what the
    next forecast takes as input. A negative horizon is a caller bug.
    """
    if horizon < 0:
        raise ValueError(f"horizon counts scoring opportunities from 0, got {horizon}")
    members = t.members[region]
    control = pos.control
    probs = tuple(
        (1.0, 0.0, 0.0) if control[i] == ev.US
        else (0.0, 1.0, 0.0) if control[i] == ev.USSR
        else (0.0, 0.0, 1.0)
        for i in members
    )
    return ControlForecast(region=region, members=members, probs=probs, horizon=horizon)


def force(forecast: ControlForecast, t: ev.Terrain, i: int, holder: int) -> ControlForecast:
    """The same forecast with member `i`'s triple replaced by `holder`'s degenerate one.

    `holder` is `ev.US`, `ev.USSR` or `ev.NOBODY`. The raw material for
    `marginal`: potential differences need the before and after forecasts to
    agree everywhere else, and rebuilding that by hand at each call site is
    how a second copy of the alignment gets written.
    """
    if holder == ev.US:
        triple = (1.0, 0.0, 0.0)
    elif holder == ev.USSR:
        triple = (0.0, 1.0, 0.0)
    elif holder == ev.NOBODY:
        triple = (0.0, 0.0, 1.0)
    else:
        raise ValueError(f"holder is US/USSR/NOBODY ({ev.US}/{ev.USSR}/{ev.NOBODY}), got {holder}")
    where = t.member_pos[i]
    if forecast.members[where] != i:
        raise ValueError(f"country index {i} is not member {where} of {forecast.region}")
    return forecast._replace(probs=tuple(triple if k == where else p for k, p in enumerate(forecast.probs)))


def implied_controls(forecast: ControlForecast) -> tuple[int, ...]:
    """The joint control outcome a degenerate forecast names, member by member.

    Raises `NotImplementedError` for a stochastic forecast: picking the modal
    outcome would substitute one board for an expectation over many (Jensen),
    and that is exactly the silent step question 5 forbids.
    """
    controls = []
    for triple in forecast.probs:
        if triple[0] == 1.0:
            controls.append(ev.US)
        elif triple[1] == 1.0:
            controls.append(ev.USSR)
        elif triple[2] == 1.0:
            controls.append(ev.NOBODY)
        else:
            raise NotImplementedError(
                "stochastic tier expectation needs the joint control distribution, "
                "which the first forecast does not model (see module docstring, "
                "question 5); per-country probabilities do not determine domination odds")
    return tuple(controls)


def expected_country_bonus(t: ev.Terrain, forecast: ControlForecast) -> float:
    """Expected 10.1.2 country bonuses, US-signed: +1 VP per controlled
    battleground, +1 per controlled country adjacent to the enemy superpower.

    Linear in the probabilities, so this is exact under ANY forecast,
    stochastic included -- each country's bonus depends only on its own
    holder. Africa has no superpower-adjacent members, but the term is general.
    """
    total = 0.0
    battleground, home = t.battleground, t.home
    for i, (p_us, p_ussr, _p_open) in zip(forecast.members, forecast.probs, strict=True):
        bg = 1.0 if battleground[i] else 0.0
        total += p_us * (bg + (i in home[ev.USSR])) - p_ussr * (bg + (i in home[ev.US]))
    return total


def expected_tier_payout(t: ev.Terrain, forecast: ControlForecast,
                         overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """Expected presence/domination/control tier payout, US-signed, computed
    ONCE for the region -- never per country.

    Under a degenerate forecast this is exact: the implied joint controls are
    loaded into a scratch snapshot and `evaluator.region_vp` scores them with
    its own counting, minus the country-bonus part (which `expected_payout`
    adds back separately, so the two are never double-counted). Under a
    stochastic forecast it raises via `implied_controls` -- the joint model is
    deferred work, not a guess made here.
    """
    controls = implied_controls(forecast)
    shadow = ev.Position(t)
    for i, holder in zip(forecast.members, controls, strict=True):
        if holder != ev.NOBODY:
            stability = t.stability[i]
            if holder == ev.US:
                shadow.place(i, stability, 0)
            else:
                shadow.place(i, 0, stability)
    ov = ev.NO_OVERRIDES if overrides is None else overrides
    return ev.region_vp(t, shadow, forecast.region, *ov) - expected_country_bonus(t, forecast)


def expected_payout(t: ev.Terrain, forecast: ControlForecast,
                    overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> Breakdown:
    """The region's expected scoring payout, US-signed, with bonus and tier apart."""
    bonus = expected_country_bonus(t, forecast)
    tier = expected_tier_payout(t, forecast, overrides)
    return Breakdown(total=bonus + tier, bonus=bonus, tier=tier)


def expected_southeast_asia_payout(t: ev.Terrain, asia_forecast: ControlForecast) -> float:
    """Southeast Asia Scoring's expected payout, US-signed: +2 VP for Thailand,
    +1 per other controlled Southeast Asia country.

    Its own payout, never Asia's tiers: the one-shot card does not score
    presence, domination or control, and final scoring never fires it (it
    scores every *region*). Linear in the probabilities -- each country's
    payout depends only on its own holder -- so this is exact under ANY
    forecast, stochastic included, like the 10.1.2 country bonuses.
    """
    if asia_forecast.region is not Region.ASIA:
        raise ValueError(f"Southeast Asia lives in Asia, forecast was {asia_forecast.region}")
    total = 0.0
    for i in t.southeast_asia:
        p_us, p_ussr, _p_open = asia_forecast.probs[t.member_pos[i]]
        value = 2.0 if t.ids[i] == 'Thailand' else 1.0
        total += p_us * value - p_ussr * value
    return total


def europe_control(t: ev.Terrain, pos: ev.Position) -> Side | None:
    """Who holds Europe Control now, if anyone: every battleground plus more
    countries than the other side -- the engine's automatic-victory condition,
    which takes precedence over any expected VP here.

    A query, not a price: there is no VP number for ending the game, so the
    integration step checks this before comparing potentials, exactly as
    `_finish_game` scores Europe first and stops on it.
    """
    counts = ([0, 0], [0, 0])  # [countries, battlegrounds] per side
    total_bg = 0
    for i in t.members[Region.EUROPE]:
        if t.battleground[i]:
            total_bg += 1
        holder = pos.control[i]
        if holder != ev.NOBODY:
            counts[holder][0] += 1
            counts[holder][1] += t.battleground[i]
    for side, other in ((ev.US, ev.USSR), (ev.USSR, ev.US)):
        if total_bg > 0 and counts[side][1] == total_bg and counts[side][0] > counts[other][0]:
            return Side.US if side == ev.US else Side.USSR
    return None


def region_potential(t: ev.Terrain, pos: ev.Position, seat: Side, region: Region, horizon: int = 0,
                     overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> Breakdown:
    """The component's answer: this position, this seat, this horizon -- the
    signed expected payout with the country-bonus and tier parts kept separate.

    Positive favors `seat`. Banked VP is not touched here (never discounted,
    never re-counted); reply and tempo adjustments stay separate by the same
    rule that keeps them out of `evaluator.region_vp`.
    """
    payout = expected_payout(t, forecast_controls(t, pos, region, horizon), overrides)
    sign = 1 if seat is Side.US else -1
    return Breakdown(total=sign * payout.total, bonus=sign * payout.bonus, tier=sign * payout.tier)


def marginal(t: ev.Terrain, seat: Side, forecast: ControlForecast, i: int, holder: int,
             overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """What moving member `i` to `holder` is worth to `seat`: the whole
    potential after minus the whole before, context fixed.

    The tier part comes from the region's joint recount, not from a per-country
    tier share -- so a placement that completes domination credits the full
    tier swing here, and summing marginals over countries would count it once
    per country. Do not sum them; reordered raw changes telescope to the same
    final potential because every step re-derives from the final board state.
    """
    sign = 1 if seat is Side.US else -1
    before = expected_payout(t, forecast, overrides).total
    after = expected_payout(t, force(forecast, t, i, holder), overrides).total
    return sign * (after - before)
