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
import math
import os
import random
from dataclasses import dataclass
from typing import NamedTuple

from struggler.engine import Region, Side
from struggler.engine.board import Board
from struggler.bots.strategic.stakes import EUROPE_CONTROL_VP
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
    # Countries adjacent to each superpower: reachability's first clause, the
    # wipe term's backing check, and region scoring's adjacency bonus.
    home: tuple[frozenset[int], frozenset[int]]
    members: dict[Region, tuple[int, ...]]
    # Where a country sits in its own region's member tuple, which is the key
    # the margin aggregates index their battleground fractions by.
    member_pos: tuple[int, ...]
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
DIGEST = os.environ.get('STRUGGLER_CHECK_SNAPSHOT') == '1'
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

    __slots__ = ('terrain', 'inf', 'control', 'reach', 'near', 'digest', '_zobrist')

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
        """
        t = self.terrain
        inf = self.inf
        was = (inf[US][i], inf[USSR][i])
        # Digest first, while the old values are still readable: XOR the
        # country's old contribution out and its new one in. O(1), and
        # exactly reversible, so undoing a trial placement restores the
        # digest bit for bit.
        # Almost every placement moves one side only, so each is tested
        # separately rather than XORing four table lookups unconditionally.
        if DIGEST:
            self._rehash(i, was, us, ussr)

        inf[US][i] = us
        inf[USSR][i] = ussr
        margin = us - ussr
        stability = t.stability[i]
        self.control[i] = US if margin >= stability else USSR if -margin >= stability else NOBODY
        adjacent = t.neighbors[i]
        for s, before, after in ((US, was[US], us), (USSR, was[USSR], ussr)):
            inf_s, home, reach, near = inf[s], t.home[s], self.reach[s], self.near[s]
            reach[i] = i in home or after > 0 or near[i] > 0
            if (before > 0) == (after > 0):
                continue
            step = 1 if after > 0 else -1
            for j in adjacent:
                count = near[j] + step
                near[j] = count
                reach[j] = j in home or inf_s[j] > 0 or count > 0
        return was

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


def importance(t: Terrain, w, urgency, i: int) -> float:
    """A country's tier times what its region will still score."""
    return (w.battleground if t.battleground[i] else w.control) * urgency[i]


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


def coup_targets(t: Terrain, pos: Position, holder: int, defcon: int,
                 bans: Prohibitions = NO_PROHIBITIONS) -> int:
    """How many battlegrounds `holder` has influence in that the opponent
    could coup at this DEFCON and could wipe with a 4-Ops coup on some roll.

    A battleground the opponent is forbidden to coup is not one of them: it
    is not a target, and counting it would also thin the risk spread over the
    targets that are real."""
    inf_h = pos.inf[holder]
    battleground, stability, minimum = t.battleground, t.stability, t.coup_min_defcon
    banned = any(bans)
    found = 0
    for i in range(len(inf_h)):
        held = inf_h[i]
        if held <= 0 or not battleground[i]:
            continue
        if defcon < minimum[i]:
            continue
        if 6 + 4 - 2 * stability[i] < held:
            continue
        if banned and coup_forbidden(t, pos, i, 1 - holder, bans):
            continue
        found += 1
    return found


def wipe_risk(t: Terrain, pos: Position, i: int, holder: int, held: int, other: int,
              stake_unit: float, w, defcon: int,
              bans: Prohibitions = NO_PROHIBITIONS) -> float:
    """Expected loss to `holder` from the opponent's coup wiping this country.

    The chance a 3- or 4-Ops coup removes every point (roll + Ops - 2 x
    stability >= held), where DEFCON allows a coup here, shared over the
    opponent's coupable targets, times the stake. Unbacked and the couper
    gets there first (adjacent already, or the coup's excess leaves them
    influence): the battleground flips, so the stake is holder's position
    plus the country's control value. Backed: the stake is holder's
    position, times `wipe_backed`.
    """
    if held <= 0:
        return 0.
    if defcon < t.coup_min_defcon[i]:
        return 0.
    if any(bans) and coup_forbidden(t, pos, i, 1 - holder, bans):
        return 0.  # the coup this risk is the risk of is not a legal move
    stability = t.stability[i]
    wipes = sum(1 for ops in (3, 4) for roll in range(1, 7) if roll + ops - 2 * stability >= held)
    p = wipes / 12
    if p == 0:
        return 0.
    margin = held - other
    position = stake_unit * (1 if margin >= stability else 0) \
        + w.progress * stake_unit * max(0., min(1., margin / stability))
    inf_h = pos.inf[holder]
    backed = i in t.home[holder] or any(inf_h[n] > 0 for n in t.neighbors[i])
    if backed:
        stake = w.wipe_backed * position
    else:
        first = pos.reach[1 - holder][i] or 6 + 4 - 2 * stability > held
        stake = w.wipe * (position + (stake_unit * (1 + w.progress) if first else 0.))
    return p * stake / max(1, coup_targets(t, pos, holder, defcon, bans))


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


def access(t: Terrain, pos: Position, i: int, s: int, w, urgency) -> float:
    """Reach a holding in country `i` gives side `s`.

    Summed over EVERY adjacent battleground it does not control -- France pays
    for both Italy and West Germany -- each worth its control value scaled by
    1/stability, discounted by how many routes already reach it. Getting to
    battlegrounds first is most of what a non-battleground is for.

    The discount is `route_decay(stability) ** (1 - k)` for k routes, and all
    k carry the SAME weight: which route you call "first" is arbitrary, so the
    term is symmetric in them. See the loop for why the exponent is geometric,
    and `conversion_p` above for why the base is a function of stability and
    not one constant.

    Chains -- a battleground two steps away through a country not yet held
    (Israel -> Egypt -> Libya, Iran -> Pakistan -> India) -- used to count
    here too, discounted by `access_chain`. Removed 2026-09-12: ablated alone
    at 128 seeds and not measurably worse (0.491 +/-0.063 over 109 seeds,
    215 games), while being 92% of the traversal this function can do. It was
    also the only reason this read influence two hops out, which is what made
    it unmemoisable on the country it prices.
    """
    other = 1 - s
    inf_s = pos.inf[s]
    control, reach_them = pos.control, pos.reach[other]
    battleground, stability, neighbors = t.battleground, t.stability, t.neighbors
    home = t.home[s]
    first = neighbors[i]
    total = 0.
    for n in first:
        if battleground[n] and control[n] != s:
            # COUNT THE ROUTES, then discount geometrically. With `p` the
            # chance one route converts reach into control before `n` scores,
            # k routes give P(control) = 1 - (1-p)^k, so each additional route
            # is worth (1-p) of the one before. Symmetric by construction: all
            # k routes carry the SAME weight, because which one you call
            # "first" is arbitrary -- the maintainer's point, and the reason
            # this is `x ** (1 - k)` rather than a per-route ordering.
            #
            # `access_decay` is x. At the measured p = 0.308 (688 resolved
            # opportunities, scripts/measure_access_conversion.py) the matching
            # value is 1/(1-p) = 1.445, which is the shipped default. It
            # replaces `access_redundant`, a flat 0.35 applied to any redundant
            # route however many there were -- so three routes paid
            # 1 + 0.35 + 0.35 while this pays 3 * x**-2.
            # `i` counts as one route BY CONSTRUCTION -- this function prices
            # what holding `i` would give, so it is a route whether or not the
            # board already shows influence there. Counting only occupied
            # neighbours made a prospective holding score the same as a sole
            # one, and `test_access_prices_reach_first_footholds_and_chains`
            # caught it: Venezuela's reach into Brazil did not fall when the
            # USSR took Brazil, because routes stayed at 1 either way.
            routes = 1
            routes += sum(1 for m in neighbors[n] if m != i and inf_s[m] > 0)
            if n in home:
                routes += 1      # the superpower reaches it without a holding
            if inf_s[n] > 0:
                routes += 1      # already standing in it, not merely reaching
            weight = route_decay(stability[n], w.access_decay) ** (1 - routes)
            if reach_them[n]:
                weight *= w.access_contested
            total += weight * importance(t, w, urgency, n) / stability[n]
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


def dependents(t: Terrain, changed, radius: int = VALUE_RADIUS) -> set[int]:
    """The countries whose `country_value` can move when `changed` moves.

    Purely geometric, and true only while `wipe` is off: with it on,
    `wipe_risk` divides by `coup_targets`, which counts the whole board, and
    no country keeps its value. Callers handle that case."""
    affected = set(changed)
    frontier = set(changed)
    for _ in range(radius):
        frontier = {n for i in frontier for n in t.neighbors[i]} - affected
        if not frontier:
            break
        affected |= frontier
    return affected


def country_value(t: Terrain, pos: Position, i: int, s: int, w, urgency, defcon: int,
                  bans: Prohibitions = NO_PROHIBITIONS) -> float:
    """What country `i` is worth to side `s` on this board."""
    us, ussr = pos.inf[US][i], pos.inf[USSR][i]
    own, opp = (us, ussr) if s == US else (ussr, us)
    margin = own - opp
    stability = t.stability[i]
    # Control is worth what the region will still score (a battleground in an
    # unscored Early War region >> one in a region just scored, or one whose
    # scoring is turns away). That is what `urgency` carries.
    imp = importance(t, w, urgency, i)
    value = imp * (1 if margin >= stability else -1 if margin <= -stability else 0)
    # Progress toward control is convex: control is worth VP, a lone point is
    # not (it can only lead there), so a half-built country is worth well
    # under half of a controlled one.
    fraction = max(-1.0, min(1.0, margin / stability))
    value += w.progress * imp * math.copysign(abs(fraction) ** w.progress_curve, fraction)
    # Wipe risk (see StrategicWeights.wipe): the couper's expected take.
    if own > 0 and w.wipe > 0:
        value -= wipe_risk(t, pos, i, s, own, opp, imp, w, defcon, bans)
    if opp > 0 and w.wipe > 0:
        value += wipe_risk(t, pos, i, 1 - s, opp, own, imp, w, defcon, bans)
    guard = w.reserve * imp
    value += guard * (min(2, max(0, margin - stability)) - min(2, max(0, -margin - stability)))
    if t.battleground[i] and (own > 0) != (opp > 0):
        # Tempo is worth most where control is cheap: per stability, like
        # every other per-Op term (a 4-stability contest is the least
        # valuable Op on the board).
        if own > 0 and pos.reach[1 - s][i]:
            value += w.first_mover * imp / stability
        elif opp > 0 and pos.reach[s][i]:
            value -= w.first_mover * imp / stability
    # First footholds open nearby battlegrounds on a later action round: a
    # stake is worth the uncontrolled battlegrounds it alone lets us reach.
    # Nothing for ground we already reach (a fourth point in Eastern Europe
    # opens nothing), and nothing for ground we hold.
    value += w.access * (access(t, pos, i, s, w, urgency) * (own > 0)
                         - access(t, pos, i, 1 - s, w, urgency) * (opp > 0))
    return value


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
              ignored: frozenset[int] = frozenset()) -> int:
    """Net VP for the US from scoring `region` now: `Board.score_region` over
    the snapshot's control vector, with the same scoring overrides (as country
    indices rather than names).

    Europe's Control tier has no scoring value -- controlling all of Europe
    is an immediate win, not a card outcome -- so it stands in as
    `EUROPE_CONTROL_VP`.
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

    us_value = value_for(US)
    if us_value is None:
        return EUROPE_CONTROL_VP
    ussr_value = value_for(USSR)
    if ussr_value is None:
        return -EUROPE_CONTROL_VP
    return us_value - ussr_value


def _contribution(is_bg: bool, stability: int, us: int, ussr: int):
    """One country's share of the region aggregates: per side (controlled
    countries, fractional battlegrounds, progress)."""
    margin = us - ussr
    if margin >= stability:
        return (1, float(is_bg), 1.), (0, 0., 0.)
    if -margin >= stability:
        return (0, 0., 0.), (1, float(is_bg), 1.)
    if us > 0 and margin > 0:
        frac = margin / stability
        return (0, is_bg * frac, frac), (0, 0., 0.)
    if ussr > 0 and margin < 0:
        frac = -margin / stability
        return (0, 0., 0.), (0, is_bg * frac, frac)
    return (0, 0., 0.), (0, 0., 0.)


def _bg_total(fractions: dict) -> float:
    """Sum the per-member battleground fractions in member order. The full
    walk adds a 0.0 for every other member and `x + 0.0 == x`, so this is
    bitwise identical to it, which keeps a swapped aggregate from reordering
    near-ties against a freshly computed one."""
    total = 0.
    for _, value in sorted(fractions.items()):
        total += value
    return total


def _unit(t: Terrain, region: Region, w, urgency) -> tuple[float, bool, float]:
    presence_vp, domination_vp, _ = t.scoring_vp[region]
    sw = urgency[t.members[region][0]]
    # One battleground's control value in this region is the unit; the
    # domination gap is in presence units.
    return w.battleground * sw, sw >= w.margin_live, (domination_vp - presence_vp) / presence_vp


def _credit(agg, unit: float, live: bool, gap: float, w) -> float:
    """Net US credit from the aggregates [countries, battlegrounds, best progress]."""
    net = 0.
    for s, sign in ((US, 1), (USSR, -1)):
        mine, theirs = agg[s], agg[1 - s]
        credit = 0.
        if live and mine[0] == 0:
            credit += w.margin_presence * mine[2]
        bg_margin = max(-2., min(2., mine[1] - theirs[1]))
        c_margin = max(-2, min(2, mine[0] - theirs[0]))
        credit += gap * (w.margin_battleground * bg_margin + w.margin_country * c_margin)
        net += sign * credit * unit
    return net


def margin_basis(t: Terrain, pos: Position, region: Region, w, urgency):
    """Partial credit toward the region's next scoring tier, net for the US,
    with the aggregates it came from: `(net, agg, unit, live, gap, fractions,
    members)`. See `StrategicWeights.margin_presence`."""
    unit, live, gap = _unit(t, region, w, urgency)
    members = t.members[region]
    us, ussr = pos.inf
    battleground, stability = t.battleground, t.stability
    agg = ([0, 0., 0.], [0, 0., 0.])
    fractions = ({}, {})
    for where, i in enumerate(members):
        for s, (countries, bgf, progress) in enumerate(
                _contribution(battleground[i], stability[i], us[i], ussr[i])):
            a = agg[s]
            a[0] += countries
            a[1] += bgf
            if bgf:
                fractions[s][where] = bgf
            if progress > a[2]:
                a[2] = progress
    return _credit(agg, unit, live, gap, w), agg, unit, live, gap, fractions, members


def margin_swapped(t: Terrain, pos: Position, region: Region, basis, i: int,
                   was_us: int, was_ussr: int, w, urgency) -> float:
    """The region margin after country `i` moved from `(was_us, was_ussr)` to
    what the snapshot now holds, by swapping that one country's contribution
    into `basis`'s aggregates. Falls back to a full pass only when the country
    may have held the region's best progress toward presence."""
    _, agg, unit, live, gap, fractions, _members = basis
    is_bg, stability = t.battleground[i], t.stability[i]
    old = _contribution(is_bg, stability, was_us, was_ussr)
    new = _contribution(is_bg, stability, pos.inf[US][i], pos.inf[USSR][i])
    where = t.member_pos[i]
    adjusted = [None, None]
    for s, (o, n) in enumerate(zip(old, new)):
        a = agg[s]
        if o[2] > 0 and o[2] >= a[2] and n[2] < o[2]:
            return margin_basis(t, pos, region, w, urgency)[0]
        if n[1] == o[1]:
            bg_total = a[1]  # unchanged, and exactly as the walk summed it
        else:
            swapped = dict(fractions[s])
            if n[1]:
                swapped[where] = n[1]
            else:
                swapped.pop(where, None)
            bg_total = _bg_total(swapped)
        adjusted[s] = [a[0] - o[0] + n[0], bg_total, max(a[2], n[2])]
    return _credit(adjusted, unit, live, gap, w)


NO_OVERRIDES: tuple[frozenset[int], frozenset[int]] = (frozenset(), frozenset())


def board_value(t: Terrain, pos: Position, s: int, w, urgency, defcon: int,
                overrides=None, bans: Prohibitions = NO_PROHIBITIONS) -> float:
    """Every country, every region score, every region margin, for side `s`.

    `overrides` maps a region to its `scoring_overrides` pair; regions absent
    from it (and every region when it is None) score with none in force.

    Summed with `sum()`, not with an accumulator loop: CPython compensates
    float summation inside `sum()`, so the two disagree in the last bit."""
    sign = 1 if s == US else -1
    ov = (lambda r: NO_OVERRIDES) if overrides is None else (
        lambda r: overrides.get(r, NO_OVERRIDES))
    return (sum(country_value(t, pos, i, s, w, urgency, defcon, bans) for i in range(len(t.ids)))
            + w.region * sum(sign * region_vp(t, pos, region, *ov(region)) for region in Region)
            + sum(sign * margin_basis(t, pos, region, w, urgency)[0] for region in Region))
