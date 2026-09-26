"""The whole-board scoring potential: one number per board, one rule.

OFF THE RANKING PATH. The potential was descoped from it on 2026-09-17 for
cost, bought back as linear weight tables behind `StrategicWeights.potential`,
measured at 1024 seeds (+0.021 [-0.000, +0.042], the rule said stop) and the
in-ranking wiring deleted on 2026-09-26. This module is what
`scripts/fit_country_weights.py` fits the shipped country weights against:
the exact target the ranking's fixed per-country weights approximate. See
docs/notes/codex/2026-09-17-potential-delta-design.md for the exactness
record and docs/notes/pi/2026-09-23-the-potential-verdict.md for the verdict.

The contract this module carries, preserved for that buy-back:

    potential = sum over scoring opportunities e of the public deck state:
                  P(e occurs)  x  shaped  x  E[signed region VP at e]

with every factor its job -- occurrence in `schedule`'s masses, control-at-
scoring in `forecast`'s fitted horizons -- and, on the ranking path,
`StrategicPlayer.delta` pricing a placement as `potential(after) -
potential(before)` with the context fixed (the rebuild README's
raw-action-delta delta contract).

Shape (see docs/notes/codex/2026-09-17-potential-delta-design.md):

- the region term disappears: `region VP now x region_urgency` is
  replaced by the mass-weighted forecast expectation, which is what
  "region VP weighted by when it is paid and by whose control" tries to
  approximate;
- the margin-credit term disappears with it: its half-fraction progress
  smoothing existed because control was 0/1, and the fit's Ops-cost
  feature is continuous. Nothing else in board_value changes in this
  slice: importance keeps its tier x urgency structure (per-country VP
  amounts at par are later work), banked VP is untouched, access and
  reply/tempo stay separate.

Both seats read the same potential signed for their seat; the holder
shaping (`scoring_hand`, `scoring_rival`) is the only deliberately
asymmetric part, the asymmetry the deck-tracking gate accepted.
"""
from __future__ import annotations

from struggler.engine import Observation, Region, Side
from struggler.engine.core import SCORING_CARD_REGION
from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic import forecast as fcst
from struggler.bots.strategic import schedule as sch
from struggler.bots.strategic import public_cards as pc


def shaped_mass(obs: Observation, card: str, opp: sch.Opportunity, w) -> float:
    """One opportunity's mass with the holder shaping the consumer applies.

    The same rule as the urgency consumer (`_scoring_weight_uncached`):
    this cycle's term is shaped by who picks the moment (held: flat
    `scoring_hand`, no rival factor -- we hold it, they cannot) and by the
    amplified holder odds otherwise; final scoring rides `scoring_final`.
    Bucket 3+ is unshaped: the shaping is holder timing, and by the
    recycle every live scoring is played.
    """
    mass = opp.occurrence
    if opp.bucket in (1, 2):
        if card in obs.hand:
            mass *= w.scoring_hand
        elif w.scoring_rival:
            mass *= 1. + w.scoring_rival * pc.p_opponent_holds(obs, card)
    elif opp.bucket == 5:
        mass *= w.scoring_final
    return mass


def region_expected(t: ev.Terrain, pos: ev.Position, obs: Observation, seat: Side,
                    region: Region, w,
                    overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """The mass-weighted expected payout for `region` across every future
    opportunity of its scoring card: U.S-signed for the US seat, negated
    for the USSR, holder-shaped on the this-cycle terms.

    Bucket 1/2 are the region's NEXT scoring (fit horizon 1); bucket 3
    and 5 are the one after (the fit's only measured tables; the clamp is
    documented, not silent). Southeast Asia is NOT handled here -- its
    card does not score the region's tiers, it rides in the SEA
    countries' own importance exactly as `region_urgency` says."""
    card = next(c for c, r in SCORING_CARD_REGION.items() if r is region)
    total = 0.0
    for opp in sch.opportunities(obs, card):
        horizon = 1 if opp.bucket in (1, 2) else 2
        forecast = fcst.forecast_controls(t, pos, region, horizon)
        payout = fcst.expected_payout(t, forecast, overrides)
        signed = payout.total if seat is Side.US else -payout.total
        total += shaped_mass(obs, card, opp, w) * signed
    return total


def region_term(t: ev.Terrain, pos: ev.Position, card: str, region: Region, w,
                masses: tuple[tuple[float, int], ...],
                overrides: tuple[frozenset[int], frozenset[int]] | None = None) -> float:
    """The region's potential term, US-signed: Sigma_e mass x E[payout at e].

    `masses` is the card's shaped (mass, horizon) pairs -- deck state, fixed
    within a decision, so the mass list is built once per context and only
    E[payout] is asked of the moving board. `overrides` is the pair this
    region scores under at THIS snapshot."""
    total = 0.0
    for mass, horizon in masses:
        forecast = fcst.forecast_controls(t, pos, region, horizon)
        total += mass * fcst.expected_payout(t, forecast, overrides).total
    return total


def shaped_masses(obs: Observation, card: str, w) -> tuple[tuple[float, int], ...]:
    """The shaped (mass, forecast horizon) pairs for one scoring card,
    bucket 1/2 collapsed onto horizon 1 and 3/5 onto horizon 2 -- the two
    forecast tables the fit measured."""
    out = []
    for opp in sch.opportunities(obs, card):
        mass = shaped_mass(obs, card, opp, w)
        horizon = 1 if opp.bucket in (1, 2) else 2
        out.append((mass, horizon))
    return tuple(out)


def whole_board(t: ev.Terrain, pos: ev.Position, obs: Observation, seat: Side, w,
                overrides) -> float:
    """The scoring potential: every region's mass-weighted expected payout,
    signed for `seat`. `overrides` maps a region to its scoring-overrides
    pair, exactly `board_value`'s contract. The one number the ranking
    path reads for the scoring half: deltas are this function's
    before/after, nothing else."""
    sign = 1 if seat is Side.US else -1
    total = 0.0
    for card, r in SCORING_CARD_REGION.items():
        total += sign * region_term(t, pos, card, r, w,
                                    shaped_masses(obs, card, w), overrides.get(r))
    return total

