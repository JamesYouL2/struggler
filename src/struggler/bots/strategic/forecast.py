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

1. Partial influence -> control probability: READ. Horizon 1+ maps the
   board through the measured "D full +over" logistic (`p_control_at_scoring`):
   exact Ops-to-control under the doubling rule, reach, stability and
   controller categories, overprotection. Conditioned on the scoring
   occurring, exactly as the September 13 rows were. Horizon 0 stays
   degenerate on purpose -- immediate scoring must reproduce the engine
   exactly -- so Q2's access/Ops/overprotection are now priced THROUGH the
   fit rather than absent from it.
2. Access, Ops-to-control cost, overprotection: inputs THROUGH the fit
   (see 1). What the fit does not carry is access-gated ACQUISITION for
   countries we cannot place in beyond the logistic's `reach`
   categories -- the reach feature is one binary, and its weight is what
   the rows measured, so this is the shape the data says, not a gap
   silently ignored.
3. Horizon: two measured tables (next scoring, the one after). Beyond 2
   the read continues the h1->h2 movement geometrically (`_horizon_triple`):
   monotone in the ordering, one simplex point at every horizon, and the
   continued asymptote is documented, not silent.
4. Tiers without multi-count: the tier payout is computed ONCE per region from
   the joint implied controls, through `evaluator.region_vp`'s own counting --
   never per country. A country's value is derived afterwards as a potential
   difference (`marginal`), and differences are never summed back into a total.
5. Correlation: a deterministic forecast is perfectly correlated through the
   shared board, and the payout is exact. A stochastic forecast prices the
   tiers through the independence DP (`_tier_distribution`) -- the exact
   expectation of the count-keyed tiers under per-country independence,
   the NAMED approximation the README contemplates, not a silent guess:
   pinning it degenerate-exact against `region_vp` at every override
   combination is what keeps the mirrored counting honest (and it caught
   the Formosan promotion missing from the bonus on the way in). How far
   independence is from correlated truth is a measurement, not this
   module's business.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import NamedTuple

from struggler.engine import Region, Side
from struggler.bots.rules_math import ops_to_control
from struggler.bots.strategic import evaluator as ev


# P(a side controls a country at its region's scoring), the "D full +over"
# logistic fit from docs/notes/claude/2026-09-13-control-odds-fits.md
# (192 games, seeds 7000-7191, at 27176ed; even seeds fit, odd score; the
# best held-out log-loss at BOTH horizons, and the calibration printout
# carries its residual bias). beta[0] is the intercept, then:
# c_me, c_opp, reach_me, reach_opp, stability==2/3/4, controller==me/them,
# over_me, over_opp -- in the order `fit_control_odds.FORMS['D full +over']`
# reads its features.
#
# Conditioned on the scoring occurring: rows resolved only when the region
# actually scored (censored rows dropped, never hidden). Measured under the
# OLD policy's games; per the rebuild README, conditioning must survive and
# these are evidence, not universal constants. Fitted on BATTLEGROUNDS only
# -- every non-battleground reading here is a documented extrapolation.
# Checked 2026-09-16 by re-running `fit_control_odds.py` over the recorded
# rows: the betas reproduce to the printed digits, and the horizon-1 table's
# cells fall where the measured ones do.
CONTROL_ODDS_BETA: dict[int, tuple[float, ...]] = {
    1: (0.012, -0.628, 0.357, 0.497, -0.439, 0.189, 0.091, -0.471, -0.860, 1.633, -0.367, 0.887),
    2: (0.135, -0.473, 0.317, 0.433, -0.462, 0.120, 0.125, -0.286, -1.057, 1.310, -0.280, 0.564),
}


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


def _control_features(t: ev.Terrain, pos: ev.Position, i: int, me: int, foe: int) -> tuple[float, ...]:
    """The measured row's features, from the snapshot: exact Ops to control
    point by point under the doubling rule (`rules_math.ops_to_control`,
    0 when already held -- control now makes taking it free), whether each
    side may place there at all (`reach`), the stability and current
    controller as categories, and influence held beyond the stability
    margin (the controller's overprotection, 0 when not in control).
    Row-relative: `me` is the side the fit is read for."""
    mine, theirs = pos.inf[me][i], pos.inf[foe][i]
    stability = t.stability[i]
    return (
        float(ops_to_control(mine, theirs, stability)),
        float(ops_to_control(theirs, mine, stability)),
        1.0 if pos.reach[me][i] else 0.0,
        1.0 if pos.reach[foe][i] else 0.0,
        float(stability == 2), float(stability == 3), float(stability == 4),
        1.0 if pos.control[i] == me else 0.0,
        1.0 if pos.control[i] == foe else 0.0,
        float(max(0, mine - theirs - stability)),
        float(max(0, theirs - mine - stability)),
    )


def p_control_at_scoring(t: ev.Terrain, pos: ev.Position, i: int, side: Side, horizon: int) -> float:
    """P(`side` controls country `i` at its region's given scoring, if that
    scoring happens -- the fits' conditioning, carried through here.

    Horizon 1 means the region's NEXT scoring (this cycle, from the deck
    walk); horizon 2 the one after. Beyond the measured two the horizon-2
    fit stands (no further table exists); the clamp is documented, not
    silent -- every later scoring borrows the second fit as its only
    available shape.
    """
    me = ev.SIDE_INDEX[side]
    foe = 1 - me
    row = _control_features(t, pos, i, me, foe)
    beta = CONTROL_ODDS_BETA[min(2, max(1, horizon))]
    z = beta[0] + sum(b * x for b, x in zip(beta[1:], row, strict=True))
    z = max(-35.0, min(35.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _triple(p_us: float, p_ussr: float) -> tuple[float, float, float]:
    """The two fitted sigmoids as one simplex point.

    The fits are read per side and nothing couples them, so `p_us +
    p_ussr` can exceed one. The read is scaled to what the outcome space
    allows: relative support between the two sides is preserved, `p_open`
    takes the remainder, and the triple sums to one by construction --
    never by a clamp that silently favors whoever read lower.
    """
    total = p_us + p_ussr
    if total > 1.0:
        return p_us / total, p_ussr / total, 0.0
    return p_us, p_ussr, 1.0 - total


def _horizon_triple(t: ev.Terrain, pos: ev.Position, i: int, horizon: int) -> tuple[float, float, float]:
    """The forecast at any horizon from the two measured ones.

    Horizons 1 and 2 are the measured tables. Beyond 2, the read continues
    the h1->h2 movement, geometrically halving the last step (Cohen's
    continuation over a simplex axis: linear in the probabilities, stays a
    simplex point -- the sums keep adding to one, each coordinate stays
    between the two fitted tables' values, and the direction is monotone
    by construction). The asymptote `2*f2 - f1` is one more step of the
    same movement, not a measured equilibrium; the halving says the data
    supports at most one further step of the same drift, and every later
    cycle decays toward it.
    """
    if horizon >= 2:
        f2 = _triple(p_control_at_scoring(t, pos, i, Side.US, 2),
                     p_control_at_scoring(t, pos, i, Side.USSR, 2))
        if horizon == 2:
            return f2
        f1 = _triple(p_control_at_scoring(t, pos, i, Side.US, 1),
                     p_control_at_scoring(t, pos, i, Side.USSR, 1))
        out = []
        for a, b in zip(f1, f2, strict=True):
            half = 0.5 * (b - a)
            out.append(min(max(a, b), max(min(a, b), b + half)))
        return tuple(out)
    return _triple(p_control_at_scoring(t, pos, i, Side.US, 1),
                   p_control_at_scoring(t, pos, i, Side.USSR, 1))


def forecast_controls(t: ev.Terrain, pos: ev.Position, region: Region, horizon: int = 0) -> ControlForecast:
    """The control forecast at one scoring opportunity's horizon.

    Horizon 0 (a scoring NOW) stays degenerate -- the acceptance criterion
    is that immediate scoring reproduces the engine's exact payout, which a
    probability cannot. Horizon 1+ reads the measured "D full +over"
    logistic (`p_control_at_scoring`, its provenance extrapolations above)
    through `_triple`/`_horizon_triple`: the two sides read the SAME
    row-relative function, the triple sums to one by construction (a scale,
    not a clamp -- relative support between the sides survives), and every
    horizon past 2 continues the h1->h2 movement, halving each further
    step: monotone in the horizon, and still a simplex point by linearity.
    A shrinkage scan over the recorded rows (logistic blended toward the
    Laplace table, held-out log-loss) moved LL by at most 0.0008 -- noise
    by the fits' own note -- so no shape change is justified yet.
    """
    if horizon < 0:
        raise ValueError(f"horizon counts scoring opportunities from 0, got {horizon}")
    members = t.members[region]
    control = pos.control
    if horizon == 0:
        probs = tuple(
            (1.0, 0.0, 0.0) if control[i] == ev.US
            else (0.0, 1.0, 0.0) if control[i] == ev.USSR
            else (0.0, 0.0, 1.0)
            for i in members
        )
    else:
        probs = tuple(_horizon_triple(t, pos, i, horizon) for i in members)
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

    The independence DP (`_tier_distribution`) covers stochastic forecasts;
    a stochastic forecast arriving here is a caller bug.
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
            raise ValueError("implied_controls is the degenerate path; "
                             "a stochastic forecast belongs to the DP")
    return tuple(controls)


def _tier_distribution(t: ev.Terrain, forecast: ControlForecast,
                       overrides: tuple[frozenset[int], frozenset[int]] | None) -> dict:
    """The joint distribution of the four counts the tier payout reads.

    Members are independent draws over (US / USSR / uncontrolled) -- THE
    independence approximation, named in the rebuild README as a possible
    first implementation and an assumption, not a rules consequence: a
    real player pursues a region across several countries with one Ops
    budget, so the draws are correlated in truth. What it buys: the exact
    expectation of every count-keyed payout under per-country
    probabilities, with no per-country tier share to double-count and no
    modal substitution (Jensen). Tiers key on (countries controlled,
    battlegrounds controlled) per side; the four-count DP is their exact
    convolution when independence holds, and `expected_tier_payout`'s
    tests pin it degenerate-exact against `region_vp` at every override
    combination, so the mirroring cannot drift from the rules.

    Overrides ride the snapshot, not the outcome: Formosan promotes
    Taiwan into every draw's battleground status, and Shuttle ignores one
    USSR-held member in every draw (its total-battleground share stays
    counted, as `region_vp` counts it) -- both are conditions the snapshot
    names, not outcomes the forecast prices.
    """
    total_bg, scoring_vp, rows = _tier_rows(t, forecast, overrides)
    tier_of = _tier_fn(total_bg, scoring_vp)
    state = _convolve_rows(rows)
    dist: dict[float, float] = defaultdict(float)
    for (us, ussr, us_bg, ussr_bg), p in state.items():
        dist[tier_of(us, us_bg, ussr, ussr_bg)] += p
    return dist


def _tier_rows(t: ev.Terrain, forecast: ControlForecast,
               overrides: tuple[frozenset[int], frozenset[int]] | None,
               skip: int | None = None) -> tuple[int, tuple[int, int, int, int], list]:
    """One region's DP inputs: (total_bg, scoring_vp, member rows), with
    member `skip` EXCLUDED when named (the per-member-removed DP's
    building block). total_bg and every battleground flag are terrain and
    override state -- STATIC within a snapshot: the removed member's
    own is_bg stays counted in total_bg even though its draw is skipped,
    exactly as the full walk counts it."""
    promoted, ignored = ev.NO_OVERRIDES if overrides is None else overrides
    total_bg = 0
    rows = []
    for where, (i, probs) in enumerate(zip(forecast.members, forecast.probs, strict=True)):
        is_bg = t.battleground[i] or i in promoted
        total_bg += is_bg
        if where == skip:
            continue  # the excluded member's draw is the caller's to add
        p_us, p_ussr, p_open = probs
        if i in ignored:
            # The snapshot says the Shuttle already dropped it from this
            # region's scoring; every draw reads it uncontrolled.
            p_us, p_ussr, p_open = 0.0, 0.0, 1.0
        rows.append((is_bg, p_us, p_ussr, p_open))
    return total_bg, t.scoring_vp[forecast.region], rows


def _tier_fn(total_bg: int, scoring_vp: tuple[int, int, int | None]):
    """The tier-value closure over the count state — one copy of the rule,
    shared by the full DP and the per-member reconvolve."""
    presence_vp, domination_vp, control_vp = scoring_vp

    def tier_of(us: int, us_bg: int, ussr: int, ussr_bg: int) -> float:
        def val(count: int, bg: int, opp: int, opp_bg: int):
            if total_bg > 0 and bg == total_bg and count > opp:
                # Europe's Control tier is an auto-victory, not a number
                # (control_vp None); every other region's is control_vp.
                return None if control_vp is None else control_vp
            if count > opp and bg > opp_bg and count > bg:
                return domination_vp  # 10.1.1: also >=1 non-battleground
            return presence_vp if count > 0 else 0.0
        ours = val(us, us_bg, ussr, ussr_bg)
        if ours is None:
            return ev.EUROPE_CONTROL_VP
        theirs = val(ussr, ussr_bg, us, us_bg)
        if theirs is None:
            return -ev.EUROPE_CONTROL_VP
        return ours - theirs
    return tier_of


def _convolve_rows(rows) -> dict:
    """The joint count distribution of the rows' independent draws."""
    state = {(0, 0, 0, 0): 1.0}
    for is_bg, p_us, p_ussr, p_open in rows:
        nxt = defaultdict(float)
        bg = 1 if is_bg else 0
        for (us, ussr, us_bg, ussr_bg), p in state.items():
            if p_us:
                nxt[(us + 1, ussr, us_bg + bg, ussr_bg)] += p * p_us
            if p_ussr:
                nxt[(us, ussr + 1, us_bg, ussr_bg + bg)] += p * p_ussr
            if p_open:
                nxt[(us, ussr, us_bg, ussr_bg)] += p * p_open
        state = nxt
    return state


def tier_e_minus(t: ev.Terrain, forecast: ControlForecast,
                 overrides: tuple[frozenset[int], frozenset[int]] | None,
                 where: int) -> dict | None:
    """The count-distribution of everything but member `where`, for the
    incremental reconvolve: the buy-back's base. Its key insight: the
    members' OTHER features do not change between the delta's before and
    after (a one-country trial only moves one member's own row i and its
    neighbours' reach), so this distribution is per-decision constant
    around a member and cached by the caller. `None` when the forecast is
    degenerate (the exact snapshot path covers that; no DP is needed)."""
    if forecast.is_degenerate():
        return None
    total_bg, scoring_vp, rows = _tier_rows(t, forecast, overrides, skip=where)
    tier_of = _tier_fn(total_bg, scoring_vp)
    state = _convolve_rows(rows)
    return tier_of, state


def tier_e_from_minus(tier_of, state_minus, member: tuple) -> float:
    """E[signed tier payout] with member's own (`is_bg, p triple`) row added
    back by a single reconvolve over `state_minus`. The buy-back's charge:
    one pass over the cached dict instead of the full n-member walk.

    Two layouts meet here and the mismatch is the defect this function
    shipped with at first: `state_minus`'s keys are (us, ussr, us_bg,
    ussr_bg) in the convolve's order, while `tier_of` reads (us, us_bg,
    ussr, ussr_bg) -- the caught-by-the-hand-math swap."""
    is_bg, p_us, p_ussr, p_open = member
    bg = 1 if is_bg else 0
    total = 0.0
    for (us, ussr, us_bg, ussr_bg), p in state_minus.items():
        if p_us:
            total += p * p_us * tier_of(us + 1, us_bg + bg, ussr, ussr_bg)
        if p_ussr:
            total += p * p_ussr * tier_of(us, us_bg, ussr + 1, ussr_bg + bg)
        if p_open:
            total += p * p_open * tier_of(us, us_bg, ussr, ussr_bg)
    return total


def expected_country_bonus(t: ev.Terrain, forecast: ControlForecast,
                           overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """Expected 10.1.2 country bonuses, US-signed: +1 VP per controlled
    battleground, +1 per controlled country adjacent to the enemy superpower.

    Linear in the probabilities, so this is exact under ANY forecast,
    stochastic included -- each country's bonus depends only on its own
    holder. Africa has no superpower-adjacent members, but the term is
    general. The overrides ride along exactly as `region_vp` counts them:
    a Formosan-promoted Taiwan is a battleground in the bonus too, and a
    Shuttle-ignored member is uncontrolled in it. Without the promotion
    the DP-vs-region_vp pin disagrees by exactly that +1 -- the mismatch
    that forced this parameter to exist.
    """
    total = 0.0
    promoted = frozenset() if overrides is None else overrides[0]
    ignored = frozenset() if overrides is None else overrides[1]
    battleground, home = t.battleground, t.home
    for i, (p_us, p_ussr, _p_open) in zip(forecast.members, forecast.probs, strict=True):
        if i in ignored:
            continue  # dropped from this region's scoring entirely
        bg = 1.0 if (battleground[i] or i in promoted) else 0.0
        total += p_us * (bg + (i in home[ev.USSR])) - p_ussr * (bg + (i in home[ev.US]))
    return total


def expected_tier_payout(t: ev.Terrain, forecast: ControlForecast,
                         overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """Expected presence/domination/control tier payout, US-signed, computed
    ONCE for the region -- never per country.

    Degenerate forecast: exact -- the implied joint controls are loaded into
    a scratch snapshot and `evaluator.region_vp` scores them with its own
    counting, minus the country-bonus part (which `expected_payout` adds
    back separately, so the two are never double-counted). Stochastic
    forecast: the independence DP (`_tier_distribution`) -- the exact
    expectation of the count-keyed tiers under per-country independence,
    a NAMED approximation, not a silent one (the rebuild README's
    "hardest modeling choice"); its calibration against correlated truth
    is a measurement, not this function's business.
    """
    if forecast.is_degenerate():
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
        return ev.region_vp(t, shadow, forecast.region, *ov) - expected_country_bonus(t, forecast, overrides)
    dist = _tier_distribution(t, forecast, overrides)
    return sum(payout * p for payout, p in dist.items())


def expected_payout(t: ev.Terrain, forecast: ControlForecast,
                    overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> Breakdown:
    """The region's expected scoring payout, US-signed, with bonus and tier apart."""
    bonus = expected_country_bonus(t, forecast, overrides)
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
