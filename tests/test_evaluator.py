"""The pure evaluation terms and the snapshot they read.

`bots/evaluator.py` re-derives control, reachability and region scoring from
its own vectors instead of asking `Board` each time, so these tests pin those
vectors against `Board`'s own accessors, and pin the incremental updates
against a full rebuild.
"""
import itertools

from struggler.engine import Engine, Region, Side
from struggler.engine.rules import RULES
from struggler.engine.types import ScoringTier
from struggler.bots import evaluator as ev
from struggler.bots.strategic import StrategicPlayer, StrategicWeights


def _played_board(seed: int = 4000, steps: int = 160):
    """A board with influence actually spread around it: the opening setup
    plus a few action rounds gives controlled, contested and empty countries."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    for _ in range(steps):
        if engine.is_terminal:
            break
        engine.step(engine.pending_decision.options[0])
    return engine.board


def test_the_snapshot_reproduces_the_board_accessors_it_replaces():
    board = _played_board()
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    held = sum(1 for cid in board.countries if any(board.influence[cid].values()))
    assert held > 10, 'the fixture board should not be near-empty'
    for i, cid in enumerate(t.ids):
        holder = pos.control[i]
        assert (None if holder == ev.NOBODY else ev.SIDE_OF[holder]) is board.control(cid)
        for side in (Side.US, Side.USSR):
            assert pos.reach[ev.SIDE_INDEX[side]][i] is board.is_reachable(side, cid)


def test_region_vp_matches_the_engine_region_scoring():
    board = _played_board()
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    for region in Region:
        try:
            expected = board.score_region(region)
        except RuntimeError:
            # Europe's control tier has no VP; the evaluator stands it in as
            # +/-100, which is what the ranking needs it to be worth.
            expected = 100 if board.region_tier(Side.US, region).value == 'control' else -100
        assert ev.region_vp(t, pos, region) == expected


def test_region_vp_matches_the_engine_under_every_scoring_override():
    """The evaluator mirrors `Board.score_region` in index space, so the two
    have to agree with the scoring overrides in force as well as without
    them -- which is what lets the bot price Formosan Resolution and Shuttle
    Diplomacy instead of scoring the board as if they were not there."""
    board = _played_board()
    # The fixture leaves Taiwan uncontrolled, and Formosan Resolution only
    # promotes a Taiwan the US holds.
    board.influence['Taiwan']['US'] = board.countries['Taiwan'].stability
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    seen = [0, 0]
    for formosan, shuttle in itertools.product((False, True), repeat=2):
        for region in Region:
            names = board.scoring_overrides(region, formosan_resolution=formosan,
                                            shuttle_diplomacy=shuttle)
            indices = ev.scoring_overrides(t, pos, region, formosan_resolution=formosan,
                                           shuttle_diplomacy=shuttle)
            # The same countries, named two ways.
            assert tuple(frozenset(t.index[c] for c in group) for group in names) == indices
            for slot, group in enumerate(names):
                seen[slot] += len(group)
            try:
                expected = board.score_region(region, *names)
            except RuntimeError:
                continue  # Europe control: no VP either implementation can name
            assert ev.region_vp(t, pos, region, *indices) == expected, (region, formosan, shuttle)
    assert all(seen), 'the fixture board triggered no promotion or no drop: %s' % (seen,)


def test_score_region_agrees_with_the_tier_it_reports():
    """`score_region` inlines the tier walk that `region_tier` returns, for
    speed. Nothing else keeps the two in step."""
    board = _played_board()
    values = {ScoringTier.NONE: 0, ScoringTier.PRESENCE: 0, ScoringTier.DOMINATION: 0}
    for region in Region:
        presence, domination, control = RULES['scoring'][region.name]
        values[ScoringTier.PRESENCE] = presence
        values[ScoringTier.DOMINATION] = domination
        tiers = {s: board.region_tier(s, region) for s in (Side.US, Side.USSR)}
        if control is None and ScoringTier.CONTROL in tiers.values():
            continue  # Europe control has no VP to compare
        values[ScoringTier.CONTROL] = control
        bonus = {}
        for s in (Side.US, Side.USSR):
            bonus[s] = sum(
                (board.countries[cid].battleground + board.is_adjacent(s.opponent.value, cid))
                for cid in board.countries_in(region) if board.control(cid) is s)
        assert board.score_region(region) == (
            values[tiers[Side.US]] + bonus[Side.US]
            - values[tiers[Side.USSR]] - bonus[Side.USSR]), region


def test_incremental_writes_leave_the_snapshot_identical_to_a_full_rebuild():
    board = _played_board()
    t = ev.terrain()
    pos = ev.Position(t).sync(board)
    countries = ('Iran', 'Poland', 'Canada', 'Thailand', 'Zaire', 'West_Germany')
    for cid, us, ussr in itertools.product(countries, range(4), range(3)):
        i = t.index[cid]
        was = pos.place(i, us, ussr)
        board.influence[cid]['US'], board.influence[cid]['USSR'] = us, ussr
        reference = ev.Position(t).sync(board)
        assert pos.control == reference.control
        assert pos.reach == reference.reach
        assert pos.near == reference.near, cid
        pos.place(i, *was)
        board.influence[cid]['US'], board.influence[cid]['USSR'] = was
    assert pos.matches(board)


def test_refresh_updates_only_what_moved_and_still_matches_a_full_sync():
    board = _played_board()
    t = ev.terrain()
    # From empty: `refresh` has to reach the same state as `sync` even when
    # every country differs, because an empty snapshot is already consistent.
    assert ev.Position(t).refresh(board).matches(board)
    pos = ev.Position(t).sync(board)
    board.influence['Iran']['USSR'] = 4
    board.influence['Chile']['US'] = 2
    assert not pos.matches(board)
    assert pos.refresh(board).matches(board)


def test_terrain_drops_the_superpower_nodes_and_orders_neighbours_by_name():
    t = ev.terrain()
    board = ev.Board()
    for cid, adjacent in zip(t.ids, t.neighbors):
        names = [t.ids[i] for i in adjacent]
        assert names == sorted(n for n in board.neighbors(cid) if n in t.index)
        assert 'US' not in names and 'USSR' not in names
    # The superpower adjacency itself is kept, as each side's home set.
    assert t.ids[next(iter(t.home[ev.US]))] in board._adjacency['US']
    assert len(t.home[ev.US]) == len(board._adjacency['US'])


def test_the_terms_price_a_bare_board_without_an_observation():
    """`ones` is the no-observation case: every country counts for its
    printed value rather than for what its region will still score."""
    t = ev.terrain()
    board = _played_board()
    pos = ev.Position(t).sync(board)
    w = StrategicWeights()
    urgency = ev.ones(t)
    plain = StrategicPlayer(w)
    assert ev.board_value(t, pos, ev.US, w, urgency, 5) == plain.value(board, Side.US)
    assert ev.board_value(t, pos, ev.USSR, w, urgency, 5) == -plain.value(board, Side.US)


def test_value_dependents_covers_every_country_a_change_can_move():
    """`VALUE_RADIUS` is what lets the event sandbox reuse a basis instead of
    re-valuing the board per event, so it has to be at least as wide as the
    terms actually read. Move one country and check that nothing outside the
    claimed set moved with it."""
    board = _played_board()
    t = ev.terrain()
    w, urgency = StrategicWeights(), ev.ones(t)
    pos = ev.Position(t).sync(board)
    everywhere = range(len(t.ids))

    def values():
        return [ev.country_value(t, pos, j, ev.US, w, urgency, 5) for j in everywhere]

    for cid in ('Israel', 'Iran', 'Poland', 'Zaire', 'Chile', 'Thailand'):
        i = t.index[cid]
        for us, ussr in ((3, 0), (0, 3), (1, 1), (0, 0)):
            base = values()
            was = pos.place(i, us, ussr)
            moved = {j for j, (now, then) in enumerate(zip(values(), base)) if now != then}
            pos.place(i, *was)
            claimed = ev.dependents(t, {i})
            assert moved <= claimed, (cid, us, ussr, sorted(t.ids[j] for j in moved - claimed))
    # And the radius is not simply the whole board: a change stays local.
    assert len(ev.dependents(t, {t.index['Chile']})) < len(t.ids)
