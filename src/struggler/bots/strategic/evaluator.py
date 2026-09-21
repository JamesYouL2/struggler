"""The board-value terms, as pure functions over an indexed snapshot.

Every function here is a function of its arguments alone. None of them reads
`self`, an `Observation`, the `RULES` table or a memo, so the same arguments
always produce the same float. That is the property the evaluator kept
losing: two memos in `StrategicPlayer` were keyed on less state than the
terms actually read, and the same position scored differently depending on
what had been evaluated before it.

The data is split by how often it changes.

`Terrain` is the map: adjacency, stability, battlegrounds, regions and the
rules constants derived from them. It is identical for every board in every
game, so it is built once per process and shared. Countries are identified
by their index in `Terrain.ids`, which is `data/countries.json` order.

`Position` is one board's influence, plus the three vectors the terms would
otherwise recompute on every call: control, per-side reachability, and the
per-side count of neighbours holding influence that reachability needs.
`Position.place` keeps all three correct after a single country changes, in
time proportional to that country's neighbours rather than to the board.

Float arithmetic here is grouped exactly as the methods it replaces grouped
it. Multiplication is not associative in floating point, and the rankings
these values feed are decided by strict comparison, so `weight * (base *
urgency) / stability` is not interchangeable with `(weight * base) *
urgency / stability`. `tests/test_parity_corpus.py` is what holds that line.

`urgency` is the per-country scoring weight, indexed like everything else:
how much the region around a country will still score. It is a function of
the observation, never of the board, so the caller computes it once per
decision and passes it in. `ONES` is the bare-evaluation case, where no
observation is available and every country counts for its printed value.
"""
from __future__ import annotations

import functools
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from struggler.engine import Region, Side, Subregion
from struggler.engine.board import Board
import math

from struggler.bots.strategic.stakes import AUTO_VICTORY_VP, EUROPE_CONTROL_VP
from struggler.engine.rules import RULES

US, USSR = 0, 1
NOBODY = -1
SIDE_INDEX = {Side.US: US, Side.USSR: USSR}
SIDE_OF = (Side.US, Side.USSR)


@dataclass(frozen=True, eq=False)
class Terrain:
    """The static map, indexed by country. Built once; never mutated."""

    ids: tuple[str, ...]
    index: dict[str, int]
    # Neighbours as indices, sorted by country id and with the two superpower
    # nodes dropped. Sorted because a set's iteration order follows
    # PYTHONHASHSEED, which once moved a sum by one ulp and reordered a tied
    # placement; dropped because every caller skipped them anyway.
    neighbors: tuple[tuple[int, ...], ...]
    neighbor_set: tuple[frozenset[int], ...]
    stability: tuple[int, ...]
    battleground: tuple[bool, ...]
    region_of: tuple[Region, ...]
    # Countries adjacent to each superpower: reachability's first clause and
    # region scoring's adjacency bonus.
    home: tuple[frozenset[int], frozenset[int]]
    members: dict[Region, tuple[int, ...]]
    # Where a country sits in its own region's member tuple, which is the key
    # the margin aggregates index their battleground fractions by.
    member_pos: tuple[int, ...]
    # A member of each region that only the region's own scoring cards
    # count -- the first outside Southeast Asia -- whose urgency is
    # therefore the region's. See `region_urgency`.
    region_anchor: dict[Region, int]
    # Southeast Asia's members, in `Terrain` order: the one-shot scoring card
    # pays per controlled country here (+2 for Thailand) and never touches
    # Asia's tiers, so the rebuild's payout half needs them as indices.
    southeast_asia: tuple[int, ...]
    scoring_vp: dict[Region, tuple[int, int, int | None]]
    coup_min_defcon: tuple[int, ...]
    # The three countries the Coup prohibitions name, as indices, so the
    # check is an integer compare rather than a dict lookup per country.
    japan: int
    france: int
    west_germany: int


@functools.lru_cache(maxsize=1)
def terrain() -> Terrain:
    """The one `Terrain`. `Board`'s country and adjacency tables are parsed
    once and shared by every board (`board._static_map`), so this is too."""
    board = Board()
    ids = tuple(board.countries)
    index = {cid: i for i, cid in enumerate(ids)}
    neighbors = tuple(tuple(index[n] for n in sorted(board.neighbors(cid)) if n in index)
                      for cid in ids)
    members = {r: tuple(index[c] for c in board.countries_in(r)) for r in Region}
    member_pos = [0] * len(ids)
    for group in members.values():
        for where, i in enumerate(group):
            member_pos[i] = where
    region_anchor = {r: next(i for i in group
                             if Subregion.SOUTHEAST_ASIA not in board.countries[ids[i]].subregions)
                     for r, group in members.items()}
    return Terrain(
        ids=ids,
        index=index,
        neighbors=neighbors,
        neighbor_set=tuple(frozenset(n) for n in neighbors),
        stability=tuple(board.countries[cid].stability for cid in ids),
        battleground=tuple(board.countries[cid].battleground for cid in ids),
        region_of=tuple(board.countries[cid].region for cid in ids),
        home=tuple(frozenset(index[c] for c in board._adjacency[side.value] if c in index)
                   for side in SIDE_OF),
        members=members,
        member_pos=tuple(member_pos),
        region_anchor=region_anchor,
        southeast_asia=tuple(i for i, cid in enumerate(ids)
                             if Subregion.SOUTHEAST_ASIA in board.countries[cid].subregions),
        scoring_vp={r: tuple(RULES['scoring'][r.name]) for r in Region},
        japan=index['Japan'],
        france=index['France'],
        west_germany=index['West_Germany'],
        coup_min_defcon=tuple(RULES['coup_min_defcon'].get(board.countries[cid].region.name, 2)
                              for cid in ids),
    )


# -- content hashing, so that a memo key can be correct by construction ----
#
# The commonest defect in this repo, six times over, is a cached value keyed
# on less state than it reads: `_access` was keyed on one country and reads
# influence two hops out, so a trial placement left it stale and 39 of 598
# corpus rankings moved when the memo was bypassed.
#
# The fix is not more careful key-writing, which is what failed six times.
# It is to give the position itself an identity: `Position.digest` is a
# 64-bit Zobrist hash of the influence vectors, maintained in O(1) by the
# one method that writes them. Two positions with equal influence have equal
# digests, and any change to any country changes it -- so a memo keyed on
# `(pos.digest, ...)` cannot go stale no matter how far the term reads.
#
# It is also equal again after an undo -- the trial-placement loops put the
# board back between candidates, and a monotonic counter would miss every
# one of those.
#
# **It is off by default, and that is a measurement, not caution.**
# Maintaining it costs 6.4% of bot time (20.2s to 21.5s over three
# five-turn games), and the memo it was built to enable is worth 2.3%: the
# base-board half of `delta` repeats only 1.7 times on average, not the four
# the placement loop's shape suggests. Paying 6.4% to save 2.3% is a loss,
# so the digest earns its place as a *correctness* instrument rather than a
# performance one -- it is what turns "the board has not moved" from a
# comment above a cache into something a test can check. Set
# STRUGGLER_CHECK_SNAPSHOT=1 to maintain it.
# ON by default since 2026-09-20. The reading above -- 6.4% to maintain
# against a 2.3% memo -- priced a memo over the base-board HALF of `delta`,
# which repeats 1.7 times. Measured over whole games, `delta` itself repeats
# 3.4 times: 70.3% of 265k calls in one game are the same (board, country,
# own, opp) asked again, mostly by the reply look-ahead re-pricing the same
# answers. `StrategicPlayer._delta_cache` keys on this digest, so the term
# it was built to enable is now worth several times what maintaining it
# costs. `STRUGGLER_CHECK_SNAPSHOT=0` turns it off again.
DIGEST = os.environ.get('STRUGGLER_CHECK_SNAPSHOT', '1') != '0'
_ZOBRIST_MAX = 64  # influence per side per country; above this, values fold


def _fold(count: int) -> int:
    """An influence count as a table index.

    Counts above `_ZOBRIST_MAX` wrap rather than raising: they do not occur
    in a legal game -- the largest seen in the corpus is well under ten --
    but a digest that raises on a strange board would turn a cosmetic
    problem into a crash. Wrapping can only cause a collision, and a
    collision is caught by `test_evaluator_digest.py`, which checks the
    digest against the influence vectors it claims to summarise."""
    return count % (_ZOBRIST_MAX + 1) if count > _ZOBRIST_MAX or count < 0 else count


@functools.lru_cache(maxsize=4)
def _zobrist_table(n: int) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Fixed random 64-bit keys per (side, country, count).

    Seeded, so a digest means the same thing in every process -- otherwise a
    value cached against one would be meaningless in the next, and a test
    could not pin it."""
    rng = random.Random(0x57C0FFEE)
    return tuple(tuple(tuple(rng.getrandbits(64) for _ in range(_ZOBRIST_MAX + 1))
                       for _ in range(n))
                 for _ in range(2))


class Position:
    """One board's influence and the vectors derived from it.

    `control` and `reach` are what `Board.control` and `Board.is_reachable`
    return, held as vectors because the terms ask for them tens of times per
    country and the answers only change where influence does. `near[s][i]`
    counts `i`'s neighbours holding side `s` influence, which is the only
    part of reachability that a change at a *neighbour* can move.
    """

    __slots__ = ('_zobrist', 'control', 'digest', 'inf', 'near', 'reach', 'terrain')

    def __init__(self, t: Terrain | None = None):
        t = t if t is not None else terrain()
        n = len(t.ids)
        self.terrain = t
        self.inf = ([0] * n, [0] * n)
        self._zobrist = _zobrist_table(n)
        # An empty board's digest: every country at zero on both sides.
        self.digest = 0
        if DIGEST:
            for s in (US, USSR):
                keys = self._zobrist[s]
                for i in range(n):
                    self.digest ^= keys[i][0]
        self.control = [NOBODY] * n
        self.reach = ([False] * n, [False] * n)
        self.near = ([0] * n, [0] * n)
        # An empty board is already a consistent snapshot: nobody controls
        # anything, and each side reaches exactly its own adjacent countries.
        # `refresh` relies on that, since it updates from wherever it starts.
        for s in (US, USSR):
            reach = self.reach[s]
            for i in t.home[s]:
                reach[i] = True

    def sync(self, board: Board) -> 'Position':
        """Reload every country from `board` and rebuild the derived vectors."""
        t = self.terrain
        us, ussr = self.inf
        influence = board.influence
        for i, cid in enumerate(t.ids):
            v = influence[cid]
            us[i] = v['US']
            ussr[i] = v['USSR']
        if DIGEST:
            keys = self._zobrist
            digest = 0
            for i in range(len(us)):
                digest ^= keys[US][i][_fold(us[i])] ^ keys[USSR][i][_fold(ussr[i])]
            self.digest = digest
        control, stability = self.control, t.stability
        for i in range(len(control)):
            margin = us[i] - ussr[i]
            control[i] = US if margin >= stability[i] else USSR if -margin >= stability[i] else NOBODY
        for s in (US, USSR):
            inf_s, home, reach, near = self.inf[s], t.home[s], self.reach[s], self.near[s]
            for i, adjacent in enumerate(t.neighbors):
                count = 0
                for k in adjacent:
                    if inf_s[k] > 0:
                        count += 1
                near[i] = count
                reach[i] = i in home or inf_s[i] > 0 or count > 0
        return self

    def refresh(self, board: Board) -> 'Position':
        """Bring the snapshot back in line with `board` by replacing only the
        countries whose influence actually moved.

        For the paths that hand a board back after writing to it directly. It
        costs one comparison per country plus `place` for each country that
        changed, where `sync` rebuilds both derived vectors outright."""
        t = self.terrain
        us, ussr = self.inf
        influence = board.influence
        for i, cid in enumerate(t.ids):
            v = influence[cid]
            new_us, new_ussr = v['US'], v['USSR']
            if us[i] != new_us or ussr[i] != new_ussr:
                self.place(i, new_us, new_ussr)
        return self

    def _rehash(self, i: int, was: tuple[int, int], us: int, ussr: int) -> None:
        """Move `digest` from `was` to the new counts at country `i`."""
        keys = self._zobrist
        if was[US] != us:
            k = keys[US][i]
            self.digest ^= k[_fold(was[US])] ^ k[_fold(us)]
        if was[USSR] != ussr:
            k = keys[USSR][i]
            self.digest ^= k[_fold(was[USSR])] ^ k[_fold(ussr)]

    def place(self, i: int, us: int, ussr: int) -> tuple[int, int]:
        """Set country `i`'s influence; return what it was.

        Control can only move for `i` itself. Reachability can only move for
        `i` and its neighbours, and only when this crosses the boundary
        between holding influence here and holding none.

        WRITTEN OUT RATHER THAN LOOPED, for the same reason `country_value`
        clamps with comparisons instead of `max`/`min`: `_delta` calls this
        twice per trial placement -- once to move the board and once to put
        it back -- so it runs about four times per `delta` and measured 2.3M
        calls in one self-play game, a tenth of the profile between it and
        `_rehash`. The two-element loop it replaces built a tuple of tuples
        on every one of those calls, and `_rehash` was a second Python call
        per placement. The arithmetic and the write order are unchanged, so
        the digest and every value are bit-identical; `test_parity_corpus`
        and `test_evaluator_digest` are what hold that.
        """
        t = self.terrain
        inf_us, inf_ussr = self.inf
        was_us, was_ussr = inf_us[i], inf_ussr[i]
        # Digest first, while the old values are still readable: XOR the
        # country's old contribution out and its new one in. O(1), and
        # exactly reversible, so undoing a trial placement restores the
        # digest bit for bit.
        # Almost every placement moves one side only, so each is tested
        # separately rather than XORing four table lookups unconditionally.
        # `_rehash` is inlined here (and kept, for callers that are not this
        # one); the XORs below are its body verbatim.
        if DIGEST:
            keys = self._zobrist
            if was_us != us:
                k = keys[US][i]
                self.digest ^= k[_fold(was_us)] ^ k[_fold(us)]
            if was_ussr != ussr:
                k = keys[USSR][i]
                self.digest ^= k[_fold(was_ussr)] ^ k[_fold(ussr)]

        inf_us[i] = us
        inf_ussr[i] = ussr
        margin = us - ussr
        stability = t.stability[i]
        self.control[i] = US if margin >= stability else USSR if -margin >= stability else NOBODY
        adjacent = t.neighbors[i]

        home, reach, near = t.home[US], self.reach[US], self.near[US]
        reach[i] = i in home or us > 0 or near[i] > 0
        if (was_us > 0) != (us > 0):
            step = 1 if us > 0 else -1
            for j in adjacent:
                count = near[j] + step
                near[j] = count
                reach[j] = j in home or inf_us[j] > 0 or count > 0

        home, reach, near = t.home[USSR], self.reach[USSR], self.near[USSR]
        reach[i] = i in home or ussr > 0 or near[i] > 0
        if (was_ussr > 0) != (ussr > 0):
            step = 1 if ussr > 0 else -1
            for j in adjacent:
                count = near[j] + step
                near[j] = count
                reach[j] = j in home or inf_ussr[j] > 0 or count > 0
        return (was_us, was_ussr)

    def matches(self, board: Board) -> bool:
        """Whether this snapshot still describes `board`, derived vectors
        included. For the tests that pin the write sites, not for the hot
        path: it rebuilds a whole second snapshot."""
        other = Position(self.terrain).sync(board)
        return (self.inf == other.inf and self.control == other.control
                and self.reach == other.reach and self.near == other.near)


def ones(t: Terrain) -> tuple[float, ...]:
    """The urgency vector for an evaluation with no observation behind it."""
    return (1.0,) * len(t.ids)


def importance(t: Terrain, w, urgency, i: int, s: int | None = None) -> float:
    """A country's tier times what its region will still score.

    With `w.country_vp_scale` set, the tier is the fitted per-country,
    per-side weight instead (`fitted_importance`); off, it is the guessed
    battleground/control pair, untouched."""
    if w.country_vp_scale and s is not None:
        return w.country_vp_scale * fitted_importance(t, urgency, i, s)
    return (w.battleground if t.battleground[i] else w.control) * urgency[i]


# Beside this module, inside the bots package: a gate's baseline is that
# package alone (`git archive <base> src/struggler/bots`), so data the bot
# reads anywhere else is missing from every snapshot of it.
FITTED_WEIGHTS_PATH = Path(__file__).resolve().parent / 'fitted_country_weights.json'


def europe_curve_vp(us_value, ussr_value, k: float) -> float:
    """Europe, US-signed, as `20 * tanh(x / k)`: `x` the net VP Europe would
    score now, Control the automatic victory at exactly +/-20
    (`AUTO_VICTORY_VP`, the maintainer's "+20, auto win"). `value_for`'s
    None is Control. `k` (VP) is fitted to the exact potential by
    scripts/fit_europe_curve.py: small k saturates early, so domination
    already reads most of the way to the win.

    The tiers jump from domination (7 + bonuses) to Control (40) with
    nothing between. That is the one region a fixed country weight could
    not describe (held-out R^2 0.63, docs/notes/claude/
    2026-09-18-fitted-country-weights.md)."""
    if us_value is None:
        return AUTO_VICTORY_VP
    if ussr_value is None:
        return -AUTO_VICTORY_VP
    return AUTO_VICTORY_VP * math.tanh((us_value - ussr_value) / k)


@functools.lru_cache(maxsize=None)
def _fitted_table(ids: tuple[str, ...]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """`a[s][i]`, from `fitted_country_weights.json` (beside this module): VP of future
    regional scoring, per unit of scoring mass, that side `s` gains by
    controlling country `i` instead of leaving it uncontrolled. Fitted to
    the exact potential by `scripts/fit_country_weights.py`. A country the
    file does not cover is an error, not a zero: a missing weight would
    silently make it worthless (bug shape 5)."""
    data = json.loads(FITTED_WEIGHTS_PATH.read_text())['weights']
    missing = [c for c in ids if c not in data]
    if missing:
        raise KeyError(f'fitted_country_weights.json has no weight for {missing}')
    return (tuple(data[c]['US'] for c in ids), tuple(data[c]['USSR'] for c in ids))


def fitted_importance(t: Terrain, urgency, i: int, s: int) -> float:
    """Fixed weight times turn-and-deck mass, in VP of expected scoring.

    The region's own scoring mass is its anchor's urgency (`region_urgency`);
    what a Southeast Asian country carries beyond it is Southeast Asia
    Scoring's mass, whose payout is exact and fixed (2 VP for Thailand, 1
    otherwise), so it needs no fit."""
    regional = region_urgency(t, t.region_of[i], urgency)
    value = _fitted_table(t.ids)[s][i] * regional
    if i in t.southeast_asia:
        value += (2.0 if i == t.index['Thailand'] else 1.0) * (urgency[i] - regional)
    return value


def region_urgency(t: Terrain, region: Region, urgency) -> float:
    """How much `region`'s own scoring is still worth: its scoring card's
    schedule and Final Scoring, as `urgency` carries them.

    Read from a member that nothing else scores. `urgency` is per country,
    and a Southeast Asian country's also counts Southeast Asia Scoring, which
    pays per country and never scores Asia's presence, domination or control
    tiers -- so reading Asia's urgency off Thailand would weight Asia's tiers
    at Southeast Asia's horizon. Southeast Asia Scoring stays where it
    belongs, in those countries' own importance.

    The one place a region's urgency is looked up: the regional VP term, the
    margin unit and the Shuttle Diplomacy tiebreak all call it."""
    return urgency[t.region_anchor[region]]


class Prohibitions(NamedTuple):
    """The persistent events that forbid the USSR a Coup, as flags -- the bot
    side of `Board.coup_prohibited`.

    Flags rather than the countries they cover, because NATO's shield depends
    on the US *Controlling* the country, and control is what a trial placement
    moves. The same reason the scoring overrides are derived per call."""
    nato: bool = False
    us_japan_pact: bool = False
    reformer: bool = False
    degaulle_france: bool = False
    willy_brandt: bool = False


NO_PROHIBITIONS = Prohibitions()


def coup_forbidden(t: Terrain, pos: Position, i: int, attacker: int,
                   bans: Prohibitions = NO_PROHIBITIONS) -> bool:
    """`Board.coup_prohibited` over the snapshot: whether a persistent event
    forbids `attacker` couping country `i`. DEFCON and influence are the
    caller's, exactly as they are there."""
    if attacker != USSR:
        return False
    if bans.us_japan_pact and i == t.japan:
        return True
    europe = t.region_of[i] is Region.EUROPE
    if bans.reformer and europe:
        return True
    if not (bans.nato and europe and pos.control[i] == US):
        return False
    if i == t.france and bans.degaulle_france:
        return False
    if i == t.west_germany and bans.willy_brandt:
        return False
    return True


# ---------------------------------------------------------------------------
# Conversion: how often reach becomes control.
# ---------------------------------------------------------------------------
#
# `p(stability)` is the probability that a side which REACHES a country --
# holds influence in a neighbour of it -- CONTROLS it by the time its region
# next scores. Measured 2026-09-12 by scripts/measure_access_conversion.py
# over 96 seeds and 3888 resolved opportunities:
#
#     stability   1      2      3      4      pooled
#     p           0.406  0.303  0.304  0.154  0.287
#     n           409    1199   1586   694    3888
#
# Binomial standard errors are 0.024, 0.013, 0.012, 0.014, so stability 2 and
# 3 are one number and stability 4 is a genuine cliff, not noise. Every smooth
# one-parameter form fits badly (linear chi2/dof = 13.2, exponential 16.7,
# hyperbolic 25.6, all against the binomial errors), because the shape is flat
# and then falls off rather than decaying. So the measurement IS the function:
# fitting a curve through it would add error, not remove any.
#
# The stability-4 cell is exactly three countries -- West Germany, Israel and
# Japan are the only stability-4 battlegrounds -- which is what makes the
# number pointed rather than aggregate.
#
# THIS IS ALSO THE TURN DECAY. A per-scoring conversion rate is a per-horizon
# quantity: `p` answers "by the time the region next scores", and the value
# function's turn discount asks the same question one scoring further out.
# Whatever prices "will we still have converted this by turn T" should come
# from here rather than from a second constant fitted separately -- one rule,
# one place. Not yet wired: the turn discount still uses its own weights, and
# joining them is a change to measure on its own.
CONVERSION_P: tuple[float, ...] = (0.406, 0.303, 0.304, 0.154)
CONVERSION_P_POOLED = 0.287


def conversion_p(stability: int) -> float:
    """P(reach becomes control by the next scoring) for a country of
    `stability`. Clamped outside the measured 1..4 -- the only stability-5
    country is the UK, which is not a battleground, so `access` never asks."""
    return CONVERSION_P[min(max(stability, 1), len(CONVERSION_P)) - 1]


# P(still control at the region's next scoring | control now), pooled over
# contested and uncontested holdings. Measured 2026-09-12 by
# scripts/measure_access_conversion.py alongside CONVERSION_P (same games,
# condition flipped), horizons 1 and 2; the horizon-1 pooled keep rates:
#
#     stability   1      2      3      4
#     keep        0.565  0.805  0.894  0.907
#     n           1103   3573   2952   540
#
# Censored (still waiting at game end, counted never dropped):
# {1: 404, 2: 1305, 3: 1011, 4: 198}. Contested holdings retain less at
# every stability (stability 2: 0.773 contested against 0.840 uncontested),
# so pooling is a choice: one table, no position read. Splitting on
# contested reach is the refinement path, not this branch.
#
# This is the flip half of the audit's two-state model (2026-09-13
# strategic-math follow-up): P(own next) = retention * P(own now) +
# acquisition * (1 - P(own now)). Acquisition is conversion_p, already
# priced in the access term; this prices what current control banks.
# Experiment branch experiment/turn-discount-two-state; the gate decides.
RETENTION_P: tuple[float, ...] = (0.565, 0.805, 0.894, 0.907)


def retention_p(stability: int) -> float:
    """P(control now is still control at the next scoring) for a country
    of `stability`. Same clamping as `conversion_p`, same reason."""
    return RETENTION_P[min(max(stability, 1), len(RETENTION_P)) - 1]


@functools.lru_cache(maxsize=None)
def route_decay(stability: int, base: float) -> float:
    """What each redundant route into a country of `stability` is worth,
    relative to the one before it.

    `base` is the pooled decay -- `w.access_decay`, which stays the single
    lever an A/B can pull -- and this rescales it to the stability the
    measurement actually found, holding the pooled level fixed. At the
    default it reproduces the measured 1/(1-p) per stability exactly:
    1.73 at stability 1 against 1.22 at stability 4.

    A redundant route is worth `1 - p` of the one before it, so a country
    that converts rarely gains LESS from a second route, not more: the
    second route into Israel is nearly as good as the first because neither
    is likely to land, while the second route into a stability-1 country is
    mostly wasted on a conversion the first already made.
    """
    return base * (1. - CONVERSION_P_POOLED) / (1. - conversion_p(stability))


@functools.lru_cache(maxsize=None)
def route_weight(stability: int, base: float, routes: int) -> float:
    """The symmetric share of the aggregate value of ``routes`` routes.

    With a per-route conversion probability ``p``, the aggregate probability
    model is the geometric sum ``[1 - (1 - p)**k] / p`` for ``k`` routes. The
    evaluator gives each route an equal share because no route is privileged;
    this is that sum divided by ``k``. ``route_decay`` is ``1 / (1 - p)``
    after the stability rescaling, so expressing the sum as powers avoids a
    second conversion between the two parameterizations.
    """
    if routes < 1:
        raise ValueError('route count must be positive')
    decay = route_decay(stability, base)
    aggregate = sum(decay ** -step for step in range(routes))
    return aggregate / routes


def access(t: Terrain, pos: Position, i: int, s: int, w, urgency) -> float:
    """Reach a holding in country `i` gives side `s`.

    Summed over EVERY adjacent battleground it does not control -- France pays
    for both Italy and West Germany -- each worth its control value scaled by
    1/stability, discounted by how many routes already reach it. Getting to
    battlegrounds first is most of what a non-battleground is for.

    The aggregate route value is the geometric sum of the first k route
    contributions, and all k carry an equal share: which route you call
    "first" is arbitrary, so the term is symmetric in them. See
    `route_weight` for the conversion model and `conversion_p` above for why
    the decay is a function of stability rather than one constant.

    Chains -- a battleground two steps away through a country not yet held
    (Israel -> Egypt -> Libya, Iran -> Pakistan -> India) -- count when
    `access_chain` is set, discounted by it. The term was removed on
    2026-09-12 as "not measurably worse" at 109 seeds, and the 2026-09-19
    bisect put a step of 0.050 at exactly the commit that did it
    (docs/notes/claude/2026-09-19-bisect-v0.2.1.md). It is restored here as a
    weight at 0.0 -- bit-identical to the shipped path, since the loop does
    not run -- so an arm can measure it at 1024 seeds instead of 109.

    The chain reads influence three hops from `i`, so a bot that sets it must
    widen the dependents radius to match: `value_radius(w)`, not
    `VALUE_RADIUS`. That coupling is the reason the term was expensive, and
    it is bug shape 1 if it is ever forgotten.
    """
    other = 1 - s
    inf_s = pos.inf[s]
    control, reach_them = pos.control, pos.reach[other]
    battleground, stability, neighbors = t.battleground, t.stability, t.neighbors
    home = t.home[s]
    first = neighbors[i]
    first_set = t.neighbor_set[i]
    # Locals, not globals/attributes, in the neighbour loop: the same floats,
    # fewer lookups per battleground. A native port takes these as precomputed
    # vectors wholesale.
    route_w = route_weight
    # `s` is threaded into `importance` on purpose. Without it the call
    # takes the tier path whatever `country_vp_scale` says, and `access`
    # -- the tiebreaker -- keeps pricing the battlegrounds it reaches on
    # the guessed tiers while control, progress and the reserve are on
    # fitted VP. That is two scales inside one `country_value`, which is
    # bug shape 6. With the scale at 0 the argument changes nothing.
    importance_fn = importance
    access_decay = w.access_decay
    access_chain = w.access_chain
    total = 0.
    for n in first:
        # A contested battleground -- one the opponent can already place in
        # -- is worth nothing here. It was `weight *= access_contested` with
        # the weight shipped at 0.0, deleted 2026-09-19; skipping is the same
        # value without the dead multiply.
        if battleground[n] and control[n] != s and not reach_them[n]:
            # COUNT THE ROUTES, then share the aggregate geometric value
            # symmetrically. With `p` the chance one route converts reach into
            # control before `n` scores, k routes have aggregate value
            # [1 - (1-p)^k] / p. Every route carries the same share because
            # which one you call "first" is arbitrary.
            #
            # `access_decay` is x. At the measured p = 0.308 (688 resolved
            # opportunities, scripts/measure_access_conversion.py), the
            # matching value is 1/(1-p) = 1.445, which is the shipped default.
            # It replaces `access_redundant`, a flat 0.35 applied to any
            # redundant route however many there were. The geometric sum is
            # capped as routes accumulate; it does not eventually decline.
            # `i` counts as one route BY CONSTRUCTION -- this function prices
            # what holding `i` would give, so it is a route whether or not the
            # board already shows influence there. Counting only occupied
            # neighbours made a prospective holding score the same as a sole
            # one, and `test_access_prices_reach_first_footholds_and_chains`
            # caught it: Venezuela's reach into Brazil did not fall when the
            # USSR took Brazil, because routes stayed at 1 either way.
            routes = 1
            for m in neighbors[n]:
                if m != i and inf_s[m] > 0:
                    routes += 1
            if n in home:
                routes += 1      # the superpower reaches it without a holding
            if inf_s[n] > 0:
                routes += 1      # already standing in it, not merely reaching
            weight = route_w(stability[n], access_decay, routes)
            total += weight * importance_fn(t, w, urgency, n, s) / stability[n]
        if not access_chain:
            continue
        # THE CHAIN, one step further: a battleground reachable only through
        # `n`, which nobody holds yet. Skipped when it is already reachable
        # from somewhere we stand, when the opponent can already place in it
        # (the same rule the first loop applies), and when it is a neighbour
        # of `i` -- the first loop priced that one exactly.
        if inf_s[n] > 0 or control[n] == other:
            continue  # already ours to build from, or not a step we take
        for m in neighbors[n]:
            if (not battleground[m] or m == i or m in first_set
                    or control[m] == s or inf_s[m] > 0 or m in home
                    or reach_them[m]):
                continue
            if any(inf_s[k] > 0 for k in neighbors[m]):
                continue  # reachable directly from somewhere already
            total += access_chain * importance_fn(t, w, urgency, m, s) / stability[m]
    return total


# How far `country_value` reads. `access` looks at a neighbour `n`, then asks
# whether any neighbour of `n` already holds influence -- two steps out -- and
# `reach[n]` is itself a function of influence one step from `n`, which is the
# same two. So a country keeps its value while nothing within two steps of it
# moved.
#
# It was 3 until 2026-09-12, correctly: the chain loop walked a neighbour's
# neighbours and then asked whether *those* were reachable, one hop further
# again. That loop went with `access_chain` (d941a5b), and the radius follows
# it down. Narrowing this is not cosmetic -- `dependents` is what lets the
# event sandbox reuse a basis instead of re-valuing the board per event, so a
# smaller radius is fewer countries re-valued on every trial placement.
#
# This lives next to the terms because it is a property of them: change what
# `access` walks and this has to change with it, which
# `test_value_dependents_covers_every_country_a_change_can_move` enforces --
# and it enforces it in the dangerous direction, since a radius that is too
# SMALL silently serves stale values while one too large is merely slow.
VALUE_RADIUS = 2

# The chain restored on 2026-09-19 walks one hop further, so a bot that sets
# `access_chain` reads three steps out and must say so. Ask this, never the
# constant, wherever a weights object is in hand.
VALUE_RADIUS_CHAIN = 3


def value_radius(w) -> int:
    """How far `country_value` reads under these weights: three steps with
    the `access_chain` loop on, two without it."""
    return VALUE_RADIUS_CHAIN if w.access_chain else VALUE_RADIUS


def dependents(t: Terrain, changed, radius: int = VALUE_RADIUS) -> set[int]:
    """The countries whose `country_value` can move when `changed` moves.

    Purely geometric. (It used to hold only while the `wipe` term was off --
    that term divided by a count over the whole board -- and the term was
    deleted, off and never calibrated, on 2026-09-13.)"""
    affected = set(changed)
    frontier = set(changed)
    for _ in range(radius):
        frontier = {n for i in frontier for n in t.neighbors[i]} - affected
        if not frontier:
            break
        affected |= frontier
    return affected


@functools.lru_cache(maxsize=None)
def others_moved_by(t: Terrain, i: int) -> tuple[int, ...]:
    """`dependents(t, {i})` without `i` itself, in index order: the other
    countries whose `country_value` a change at `i` can move.

    Cached on its whole input -- the static map and one index -- because
    `delta` asks it for every placement that moves presence or control. It
    reads nothing else, so the cache cannot go stale."""
    return tuple(sorted(dependents(t, {i}) - {i}))


def country_value(t: Terrain, pos: Position, i: int, s: int, w, urgency) -> float:
    """What country `i` is worth to side `s` on this board."""
    us, ussr = pos.inf[US][i], pos.inf[USSR][i]
    own, opp = (us, ussr) if s == US else (ussr, us)
    margin = own - opp
    stability = t.stability[i]
    # Control is worth what the region will still score (a battleground in an
    # unscored Early War region >> one in a region just scored, or one whose
    # scoring is turns away). That is what `urgency` carries.
    if w.country_vp_scale:
        return _fitted_country_value(t, pos, i, s, w, urgency, margin, stability, own, opp)
    imp = importance(t, w, urgency, i)
    value = imp * (1 if margin >= stability else -1 if margin <= -stability else 0)
    # Progress toward control is convex: control is worth VP, a lone point is
    # not (it can only lead there), so a half-built country is worth well
    # under half of a controlled one.
    # Clamped with comparisons, not `max`/`min`. Identical arithmetic: this
    # is the hottest function in a game (8.6M calls over two self-play games)
    # and the five builtin calls it made were 36M `max` and 30M `min` calls,
    # about a tenth of the whole profile.
    fraction = margin / stability
    if fraction > 1.0:
        fraction = 1.0
    elif fraction < -1.0:
        fraction = -1.0
    # Linear. This was `copysign(abs(fraction) ** progress_curve, fraction)`
    # with the exponent pinned at 1.0, which is `fraction` exactly; convex
    # (2.0) lost the gate at 0.33, and the knob was deleted 2026-09-13.
    value += w.progress * imp * fraction
    guard = w.reserve * imp
    over = margin - stability
    over = 0 if over < 0 else (2 if over > 2 else over)
    under = -margin - stability
    under = 0 if under < 0 else (2 if under > 2 else under)
    value += guard * (over - under)
    # (A `first_mover` tempo term stood here until 2026-09-13: presence in a
    # battleground the opponent has none in but could reach. Set to 0 over
    # 256 seeds it read 0.513 [0.475, 0.550], the highest of the ablations.)
    # First footholds open nearby battlegrounds on a later action round: a
    # stake is worth the uncontrolled battlegrounds it alone lets us reach.
    # Nothing for ground we already reach (a fourth point in Eastern Europe
    # opens nothing), and nothing for ground we hold.
    access_fn = access  # local: same call, fewer lookups per country
    access_own = access_fn(t, pos, i, s, w, urgency) if own > 0 else 0.0
    access_opp = access_fn(t, pos, i, 1 - s, w, urgency) if opp > 0 else 0.0
    value += w.access * (access_own - access_opp)
    return value


def _fitted_country_value(t: Terrain, pos: Position, i: int, s: int, w, urgency,
                          margin: int, stability: int, own: int, opp: int) -> float:
    """`country_value` on the fitted weights. The same four terms, with one
    difference the fit makes visible: a country is not worth the same to
    both sides (the 10.1.2 adjacency bonus pays only the side whose enemy
    superpower it borders, and tiers fall differently), so our control is
    priced at OUR weight and theirs at THEIRS -- the tier pair was symmetric."""
    mine = importance(t, w, urgency, i, s)
    theirs = importance(t, w, urgency, i, 1 - s)
    value = mine if margin >= stability else -theirs if margin <= -stability else 0.0
    fraction = max(-1.0, min(1.0, margin / stability))
    value += w.progress * (mine * fraction if fraction > 0 else theirs * fraction)
    value += w.reserve * (mine * min(2, max(0, margin - stability))
                          - theirs * min(2, max(0, -margin - stability)))
    access_own = access(t, pos, i, s, w, urgency) if own > 0 else 0.0
    access_opp = access(t, pos, i, 1 - s, w, urgency) if opp > 0 else 0.0
    return value + w.access * (access_own - access_opp)


def scoring_overrides(t: Terrain, pos: Position, region: Region, *,
                      formosan_resolution: bool = False,
                      shuttle_diplomacy: bool = False) -> tuple[frozenset[int], frozenset[int]]:
    """`Board.scoring_overrides` over the snapshot: the (extra_battlegrounds,
    ignored) index sets `region` scores under, given the named events."""
    extra: frozenset[int] = frozenset()
    ignored: frozenset[int] = frozenset()
    if formosan_resolution and region is Region.ASIA:
        taiwan = t.index['Taiwan']
        if pos.control[taiwan] == US:
            extra = frozenset((taiwan,))
    if shuttle_diplomacy and region in (Region.MIDDLE_EAST, Region.ASIA):
        for i in t.members[region]:
            if t.battleground[i] and pos.control[i] == USSR:
                ignored = frozenset((i,))
                break
    return extra, ignored


# Europe Control has no scoring value in the rules -- it simply wins -- so
# `region_vp` needs a number for it. It comes from `stakes`, with every
# other "what winning is worth" constant, rather than being chosen here.


def region_vp(t: Terrain, pos: Position, region: Region,
              extra_battlegrounds: frozenset[int] = frozenset(),
              ignored: frozenset[int] = frozenset(),
              europe_control_vp: float = EUROPE_CONTROL_VP,
              europe_curve: float = 0.0) -> float:
    """Net VP for the US from scoring `region` now: `Board.score_region` over
    the snapshot's control vector, with the same scoring overrides (as country
    indices rather than names).

    Europe's Control tier has no scoring value -- controlling all of Europe
    is an immediate win, not a card outcome -- so it stands in as
    `europe_control_vp`, the game's 40 VP swing unless a caller prices it
    otherwise (`StrategicWeights.europe_control_vp`, for experiments).

    `europe_curve` > 0 prices Europe as one continuous curve instead
    (`europe_curve_vp`): the tiers' step to Control becomes a slope.
    """
    presence_vp, domination_vp, control_vp = t.scoring_vp[region]
    control, battleground, home = pos.control, t.battleground, t.home
    counts = ([0, 0, 0], [0, 0, 0])  # controlled, battlegrounds, 10.1.2 bonus
    total_bg = 0
    # Overrides are rare and this walk is the value function's hottest loop,
    # so the empty case never pays for a set lookup.
    promoted, dropped = bool(extra_battlegrounds), bool(ignored)
    for i in t.members[region]:
        is_bg = battleground[i] or (promoted and i in extra_battlegrounds)
        total_bg += is_bg
        holder = NOBODY if (dropped and i in ignored) else control[i]
        if holder == NOBODY:
            continue
        tally = counts[holder]
        tally[0] += 1
        tally[1] += is_bg
        tally[2] += is_bg + (i in home[1 - holder])

    def value_for(s: int):
        side_count, side_bg, bonus = counts[s]
        opp_count, opp_bg, _ = counts[1 - s]
        if total_bg > 0 and side_bg == total_bg and side_count > opp_count:
            return None if control_vp is None else control_vp + bonus
        if side_count > opp_count and side_bg > opp_bg and side_count > side_bg:
            return domination_vp + bonus  # must also control >=1 non-battleground (10.1.1)
        if side_count > 0:
            return presence_vp + bonus
        return bonus

    if europe_curve and region is Region.EUROPE:
        return europe_curve_vp(value_for(US), value_for(USSR), europe_curve)
    us_value = value_for(US)
    if us_value is None:
        return europe_control_vp
    ussr_value = value_for(USSR)
    if ussr_value is None:
        return -europe_control_vp
    return us_value - ussr_value


NO_OVERRIDES: tuple[frozenset[int], frozenset[int]] = (frozenset(), frozenset())


def region_potential(t: Terrain, w, urgency, nets) -> float:
    """The regional term of the board potential: for each `(region, net)`
    pair, the signed VP the region would score now, weighted by that
    region's own scoring urgency, summed and times `w.region`.

    ONE rule, called by `board_value`, by `StrategicPlayer.delta` (with one
    region's VP before and after a change) and by the event sandbox, because
    three copies of it did not agree: `board_value` and the sandbox applied
    no urgency, while `delta` applied the changed country's, which for a
    Southeast Asian country includes Southeast Asia Scoring -- so Thailand
    and Pakistan credited the same Asia tier change differently and two
    placement orders reaching one board summed to different values
    (Codex M2). A region's VP is only paid when its region scores, so here
    it is weighted by when that is, on every path.

    `sum()`, like the rest of `board_value`."""
    return w.region * sum(region_urgency(t, r, urgency) * net for r, net in nets)


def board_value(t: Terrain, pos: Position, s: int, w, urgency, overrides=None) -> float:
    """Every country and every region score, for side `s`.

    `overrides` maps a region to its `scoring_overrides` pair; regions absent
    from it (and every region when it is None) score with none in force.

    Summed with `sum()`, not with an accumulator loop: CPython compensates
    float summation inside `sum()`, so the two disagree in the last bit."""
    sign = 1 if s == US else -1
    ov = (lambda _r: NO_OVERRIDES) if overrides is None else (
        lambda r: overrides.get(r, NO_OVERRIDES))
    # Locals for the per-country/per-region loops: identical floats, fewer
    # global lookups over ~100 countries plus 12 region walks per board.
    country_value_fn = country_value
    region_vp_fn = region_vp
    return (sum(country_value_fn(t, pos, i, s, w, urgency) for i in range(len(t.ids)))
            + region_potential(t, w, urgency,
                               ((region, sign * region_vp_fn(t, pos, region, *ov(region), w.europe_control_vp, w.europe_curve))
                                for region in Region)))
