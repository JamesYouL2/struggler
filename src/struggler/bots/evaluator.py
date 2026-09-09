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
from dataclasses import dataclass

from struggler.engine import Region, Side
from struggler.engine.board import Board
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

    def side_of(self, cid: str) -> int:
        return self.index[cid]


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
        coup_min_defcon=tuple(RULES['coup_min_defcon'].get(board.countries[cid].region.name, 2)
                              for cid in ids),
    )


class Position:
    """One board's influence and the vectors derived from it.

    `control` and `reach` are what `Board.control` and `Board.is_reachable`
    return, held as vectors because the terms ask for them tens of times per
    country and the answers only change where influence does. `near[s][i]`
    counts `i`'s neighbours holding side `s` influence, which is the only
    part of reachability that a change at a *neighbour* can move.
    """

    __slots__ = ('terrain', 'inf', 'control', 'reach', 'near')

    def __init__(self, t: Terrain | None = None):
        t = t if t is not None else terrain()
        n = len(t.ids)
        self.terrain = t
        self.inf = ([0] * n, [0] * n)
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

    def place(self, i: int, us: int, ussr: int) -> tuple[int, int]:
        """Set country `i`'s influence; return what it was.

        Control can only move for `i` itself. Reachability can only move for
        `i` and its neighbours, and only when this crosses the boundary
        between holding influence here and holding none.
        """
        t = self.terrain
        inf = self.inf
        was = (inf[US][i], inf[USSR][i])
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


def coup_targets(t: Terrain, pos: Position, holder: int, defcon: int) -> int:
    """How many battlegrounds `holder` has influence in that the opponent
    could coup at this DEFCON and could wipe with a 4-Ops coup on some roll."""
    inf_h = pos.inf[holder]
    battleground, stability, minimum = t.battleground, t.stability, t.coup_min_defcon
    found = 0
    for i in range(len(inf_h)):
        held = inf_h[i]
        if held <= 0 or not battleground[i]:
            continue
        if defcon < minimum[i]:
            continue
        if 6 + 4 - 2 * stability[i] >= held:
            found += 1
    return found


def wipe_risk(t: Terrain, pos: Position, i: int, holder: int, held: int, other: int,
              stake_unit: float, w, defcon: int) -> float:
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
    return p * stake / max(1, coup_targets(t, pos, holder, defcon))


def access(t: Terrain, pos: Position, i: int, s: int, w, urgency) -> float:
    """Reach a holding in country `i` gives side `s`.

    The adjacent battlegrounds it does not control, each worth its control
    value scaled by 1/stability. Full weight when this holding alone reaches
    one, `access_redundant` when another holding already does (insurance, and
    one more direction to contest from). Chains count too, discounted by
    `access_chain`: a battleground two steps away through a country not yet
    held (Israel -> Egypt -> Libya, Iran -> Pakistan -> India, Australia ->
    Malaysia -> Thailand). Getting to battlegrounds first is most of what a
    non-battleground is for.

    This reads influence up to two hops out, which is why it is not memoised
    on the country it prices: see the commit that removed that memo.
    """
    other = 1 - s
    inf_s = pos.inf[s]
    control, reach_them = pos.control, pos.reach[other]
    battleground, stability, neighbors = t.battleground, t.stability, t.neighbors
    home = t.home[s]
    first = neighbors[i]
    first_set = t.neighbor_set[i]
    total = 0.
    for n in first:
        if battleground[n] and control[n] != s:
            if n in home or inf_s[n] > 0:
                weight = w.access_redundant  # present already; this adds a direction
            elif any(inf_s[m] > 0 for m in neighbors[n] if m != i):
                weight = w.access_redundant  # reachable through another holding
            else:
                weight = 1.
            if reach_them[n]:
                weight *= w.access_contested
            total += weight * importance(t, w, urgency, n) / stability[n]
        if inf_s[n] > 0 or control[n] == other:
            continue  # already ours to build from, or not a step we take
        for m in neighbors[n]:
            if (not battleground[m] or m == i or m in first_set
                    or control[m] == s or inf_s[m] > 0 or m in home):
                continue
            if any(inf_s[k] > 0 for k in neighbors[m]):
                continue  # reachable directly from somewhere already
            contested = w.access_contested if reach_them[m] else 1.
            total += w.access_chain * contested * importance(t, w, urgency, m) / stability[m]
    return total


def country_value(t: Terrain, pos: Position, i: int, s: int, w, urgency, defcon: int) -> float:
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
        value -= wipe_risk(t, pos, i, s, own, opp, imp, w, defcon)
    if opp > 0 and w.wipe > 0:
        value += wipe_risk(t, pos, i, 1 - s, opp, own, imp, w, defcon)
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


def region_vp(t: Terrain, pos: Position, region: Region) -> int:
    """Net VP for the US from scoring `region` now: `Board.score_region` over
    the snapshot's control vector.

    Europe's Control tier has no scoring value (controlling all of Europe is
    an immediate win, not a card outcome), so it stands in as +/-100, which is
    what `StrategicPlayer.region_score` did with the exception `score_region`
    raises there.
    """
    presence_vp, domination_vp, control_vp = t.scoring_vp[region]
    control, battleground, home = pos.control, t.battleground, t.home
    counts = ([0, 0, 0], [0, 0, 0])  # controlled, battlegrounds, 10.1.2 bonus
    total_bg = 0
    for i in t.members[region]:
        is_bg = battleground[i]
        total_bg += is_bg
        holder = control[i]
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
        return 100
    ussr_value = value_for(USSR)
    if ussr_value is None:
        return -100
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


def board_value(t: Terrain, pos: Position, s: int, w, urgency, defcon: int) -> float:
    """Every country, every region score, every region margin, for side `s`.

    Summed with `sum()`, not with an accumulator loop: CPython compensates
    float summation inside `sum()`, so the two disagree in the last bit."""
    sign = 1 if s == US else -1
    return (sum(country_value(t, pos, i, s, w, urgency, defcon) for i in range(len(t.ids)))
            + w.region * sum(sign * region_vp(t, pos, region) for region in Region)
            + sum(sign * margin_basis(t, pos, region, w, urgency)[0] for region in Region))
