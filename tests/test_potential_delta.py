"""The potential priced as linear weights (`StrategicPlayer.potential_delta`).

The v3 plan's step 5. `forecast.member_weights` gives the exact per-position
weights; this is what the ranking path would call. Its contract has three
parts, and each is a test here:

1. **Exact** when a trial moves one member's triple, because each member's
   weights fold in every other member and `(q' - q)` sums to zero.
2. **First order** when several move -- the interaction terms are dropped --
   with the error measured against the full recompute rather than assumed.
3. **Honest about what it cannot see**: a trial that changes the region's
   scoring overrides returns None instead of a wrong number.

The oracle throughout is `scoring_potential`, the DP the weights replace.
"""
import logging
import statistics

import pytest

from struggler.engine import Engine, Region, Side
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic import forecast as fcst


def _played(seed: int = 4000, steps: int = 120):
    logging.disable(logging.CRITICAL)
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    for _ in range(steps):
        d = engine.pending_decision
        if d is None or engine.is_terminal:
            break
        engine.step(d.options[0] if d.actor is Side.CHANCE
                    else StrategicPlayer().choose_action(engine.observe(d.actor), []))
    return engine


def _ranking_bot(engine, side=Side.US):
    obs = engine.observe(side)
    bot = StrategicPlayer()
    bot.prepare(obs)
    # The tables are a per-decision cache, opened by `rank_actions`; these
    # tests call `potential_delta` directly, so they open it the same way.
    bot._weight_table_cache = {}
    return bot, obs


def _members_moved(bot, cid, own):
    """How many member triples, in every region the trial reaches, move."""
    t, pos = bot._terrain, bot._position
    i = t.index[cid]
    regions = {t.region_of[i]} | {t.region_of[n] for n in t.neighbors[i]}
    before = {r: [fcst._horizon_triple(t, pos, m, 1) for m in t.members[r]] for r in regions}
    was = pos.place(i, pos.inf[ev.US][i] + own, pos.inf[ev.USSR][i])
    after = {r: [fcst._horizon_triple(t, pos, m, 1) for m in t.members[r]] for r in regions}
    pos.place(i, *was)
    return sum(a != b for r in regions for a, b in zip(after[r], before[r], strict=True))


def _trials(bot, obs, countries):
    """(cid, own, members moved, priced, exact) for each trial."""
    board = bot.board
    base = bot.scoring_potential(board, Side.US)
    out = []
    for cid in countries:
        for own in (1, 3):
            moved = _members_moved(bot, cid, own)
            priced = bot.potential_delta(obs, cid, own=own)
            original = dict(board.influence[cid])
            board.influence[cid]['US'] += own
            probe = StrategicPlayer()
            probe.prepare(obs)              # same context, moved board
            exact = probe.scoring_potential(board, Side.US) - base
            board.influence[cid].update(original)
            out.append((cid, own, moved, priced, exact))
    return out


def test_one_member_moving_is_priced_exactly():
    """The identity the whole design rests on: with one triple moved, the dot
    product IS the potential difference, to floating point."""
    engine = _played()
    bot, obs = _ranking_bot(engine)
    countries = list(bot.board.countries)[:40]
    checked = 0
    for cid, own, moved, priced, exact in _trials(bot, obs, countries):
        if moved != 1 or priced is None:
            continue
        assert priced == pytest.approx(exact, abs=1e-9), (cid, own, priced, exact)
        checked += 1
    assert checked >= 5, f'only {checked} single-member trials in the sample'


def test_a_trial_across_a_regional_border_prices_both_regions():
    """Libya is Middle Eastern and borders Africa, so a placement there moves
    Africa's forecast through reach. Pricing only the country's own region
    was wrong by 0.074 VP on every Libya trial -- the one single-member case
    that was not exact, and the reason `potential_delta` walks the regions of
    the country AND its neighbours."""
    engine = _played()
    bot, obs = _ranking_bot(engine)
    t = bot._terrain
    i = t.index['Libya']
    assert t.region_of[i] is Region.MIDDLE_EAST
    assert any(t.region_of[n] is Region.AFRICA for n in t.neighbors[i])
    (_cid, _own, _moved, priced, exact), = _trials(bot, obs, ['Libya'])[:1]
    assert priced == pytest.approx(exact, abs=1e-9)


def test_several_members_moving_is_first_order_and_the_error_is_measured():
    """Dropping the interaction terms is the named approximation. The bound
    here is what it measures on a played board -- a regression that made the
    expansion worse would break it, and a claim of exactness would be
    false."""
    engine = _played()
    bot, obs = _ranking_bot(engine)
    countries = list(bot.board.countries)[:40]
    rels = [abs(priced - exact) / abs(exact)
            for _cid, _own, moved, priced, exact in _trials(bot, obs, countries)
            if moved > 1 and priced is not None and abs(exact) > 1e-9]
    assert len(rels) >= 20, f'only {len(rels)} multi-member trials in the sample'
    rels.sort()
    assert statistics.median(rels) < 0.03, f'median relative error {statistics.median(rels):.2%}'
    assert rels[int(len(rels) * 0.95)] < 0.12, f'p95 relative error {rels[int(len(rels) * 0.95)]:.1%}'


def test_a_trial_that_changes_the_scoring_overrides_refuses_to_price_it():
    """The overrides read control, so a flip can add or remove a Formosan
    promotion or a Shuttle-ignored member -- a different scoring rule from
    the one the table was built under. The weights cannot see that, so the
    answer is None and the caller recomputes."""
    engine = _played()
    bot, obs = _ranking_bot(engine)
    t, pos = bot._terrain, bot._position
    region = Region.ASIA
    taiwan = t.index['Taiwan']

    real = bot._overrides_for
    seen = {}

    def fake(r, p, flags=None):
        # Formosan Resolution promotes Taiwan only while it is US-controlled:
        # exactly an override that appears with the flip being priced.
        base = real(r, p, flags)
        if r is region and p.control[taiwan] == ev.US:
            seen['fired'] = True
            return (frozenset({taiwan}) | base[0], base[1])
        return base

    bot._overrides_for = fake
    try:
        need = t.stability[taiwan] + pos.inf[ev.USSR][taiwan]
        assert bot.potential_delta(obs, 'Taiwan', own=need + 2) is None
    finally:
        bot._overrides_for = real
    assert seen.get('fired'), 'the fixture never produced the override it tests'


def test_the_tables_are_keyed_on_the_board_they_describe():
    """Bug shape 1. The weights are a per-position object: a table built on
    one board must never be served for another. They are keyed on
    `Position.digest` rather than dropped on every board move, because a
    trial placement moves the board and puts it back -- and rebuilding six
    regions at two horizons per candidate cost 2.80 s a ranking, which is
    the 2026-09-17 descope over again.

    So the contract is not "cleared when the board moves", it is "the board
    is part of the key": a moved board gets its own entry, and the original
    board gets its original entry back after an undo.
    """
    engine = _played()
    bot, obs = _ranking_bot(engine)
    t, pos = bot._terrain, bot._position
    region = t.region_of[t.index['Iran']]

    first = bot._weight_tables(region)
    assert bot._weight_tables(region) is first, 'the same board rebuilt its table'

    i = t.index['Iran']
    was = pos.place(i, pos.inf[ev.US][i] + 3, pos.inf[ev.USSR][i])
    moved = bot._weight_tables(region)
    assert moved is not first, 'a moved board was served the old board\'s table'
    assert moved[1][1] != first[1][1], 'the weights did not move with the board'

    pos.place(i, *was)
    assert bot._weight_tables(region) is first, 'an undone board did not get its table back'


def test_the_trial_plans_are_what_the_inline_walk_used_to_build():
    """`_trial_plans` precomputes what `potential_delta` rebuilt per call.

    The plan is pure terrain, so it can be checked against the walk it
    replaced without playing anything: for every country, the regions a
    trial touches, the members of each whose triple can move, where those
    sit in `member_weights`'s indexing, and Southeast Asia's payouts. A
    precomputed table that disagrees with the loop it replaced is the
    quietest possible defect -- every number stays plausible.
    """
    from struggler.bots.strategic.policy import SCORING_CARD_REGION

    player = StrategicPlayer()
    t = player._terrain
    cards_by_region = {r: c for c, r in SCORING_CARD_REGION.items()}
    plans = player._trial_plans
    assert len(plans) == len(t.ids)

    for i in range(len(t.ids)):
        touched = {i} | set(t.neighbors[i])
        want = {}
        for region in {t.region_of[i]} | {t.region_of[n] for n in t.neighbors[i]}:
            moved = tuple(m for m in t.members[region] if m in touched)
            if moved:
                want[region] = moved
        got = {entry[0]: entry[1] for entry in plans[i]}
        assert got == want, f'{t.ids[i]}: touched regions/members differ'

        for region, moved, slots, sea, card in plans[i]:
            where = {m: k for k, m in enumerate(t.members[region])}
            assert slots == tuple(where[m] for m in moved)
            assert card is cards_by_region[region]
            assert sea == tuple((k, 2.0 if t.ids[m] == 'Thailand' else 1.0)
                                for k, m in enumerate(moved) if m in t.southeast_asia)
