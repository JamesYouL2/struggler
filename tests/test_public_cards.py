"""The deck facts the scoring horizon rests on must match the engine's.

`turns_to_reshuffle` walks the draw pile forward, adding the cards each
period contributes. If its idea of "how many" differs from the engine's,
the whole scoring schedule shifts -- and it did: the constant was built
with `include_optional=False`, the default on `Engine.__init__`, while
every played game comes from `Engine.new_game`, which defaults it to
`True`. Three cards short per period, in every game the gate plays.

It was caught by a log line rather than a test, which is the argument for
both.
"""
from __future__ import annotations

import re

from struggler.bots.strategic.public_cards import (
    ENTERING,
    cycle_deal_masses,
    deal_size,
    turns_to_reshuffle,
)
from struggler.engine import Engine, Side
from struggler.engine.cards import ENTRY_TURN
from struggler.bots.greedy import GreedyPlayer


def test_entering_matches_what_the_engine_adds(caplog):
    """Played, not asserted from the same helper the constant uses: a test
    that recomputed `cards_entering` would agree with a wrong flag."""
    import logging
    sizes: dict[int, int] = {}
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    bots = {Side.US: GreedyPlayer(), Side.USSR: GreedyPlayer()}
    with caplog.at_level(logging.INFO, logger='struggler.engine'):
        steps = 0
        while not engine.is_terminal and engine.turn <= 8 and steps < 8000:
            decision = engine.pending_decision
            engine.step(decision.options[0] if decision.actor is Side.CHANCE
                        else bots[decision.actor].choose_action(engine.observe(decision.actor), []))
            steps += 1
    for record in caplog.records:
        if ' enters: ' in record.getMessage():
            msg = record.getMessage()
            turn = int(msg.split()[0][1:])
            count = int(msg.split(' enters: ')[1].split()[0])
            sizes[turn] = count
    for turn, expected in ENTERING.items():
        if turn in sizes:
            assert sizes[turn] == expected, (
                f'turn {turn}: the engine added {sizes[turn]} cards, ENTERING says '
                f'{expected}. turns_to_reshuffle will be wrong by the difference, '
                f'and so will every scoring card in hand.')
    assert sizes, 'no period entered; the fixture never reached turn 4'


def test_deal_size_shares_the_reshuffle_arithmetic():
    """One rule, one place: the deal walk and the reshuffle walk agree."""
    from struggler.engine.cards import hand_limit

    for turn in (1, 3, 4, 8, 10):
        assert deal_size(turn) == max(1, 2 * hand_limit(turn) - 2)


def test_cycle_deal_masses_are_deal_over_pile_before_and_conserve():
    """Deck math, pinned at both ends: each mass is deal/pile-before, and the
    unconditional masses plus survival sum to one."""
    from struggler.engine.core import LAST_TURN

    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(Side.US)
    masses = cycle_deal_masses(obs)
    # Re-walk the same arithmetic independently: pile + entering, deal over
    # pile-before, and the deal that empties the pile taking all of what is
    # left -- the engine draws the pile down and reshuffles only when it is
    # actually empty, so that last deal delivers a pile card with certainty.
    pile = obs.draw_pile_size
    expected: list[float] = []
    for ahead in range(1, LAST_TURN - obs.turn + 1):
        turn = obs.turn + ahead
        pile += ENTERING.get(turn, 0)
        deal = deal_size(turn)
        if pile <= 0:
            break
        if pile - deal < 0:
            expected.append(1.0)
            break
        expected.append(deal / pile)
        pile -= deal
    assert masses == tuple(expected)
    # Conservation: unconditional deal-at-k plus survival is one.
    survival = 1.0
    total = 0.0
    for mass in masses:
        total += mass * survival
        survival *= 1.0 - mass
    assert total + survival == 1.0
    # And where a reshuffle falls inside the game, survival is exactly zero:
    # nothing is left un-dealt in a pile that gets emptied.
    if turns_to_reshuffle(obs) <= LAST_TURN - obs.turn:
        assert survival == 0.0 and total == 1.0


def test_cycle_deal_masses_count_matches_the_reshuffle_walk():
    """The masses name every deal up to and including the one that exhausts
    the pile, so their count is the reshuffle distance -- or every turn left
    when the pile outlasts the game."""
    from dataclasses import replace

    from struggler.engine.core import LAST_TURN

    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(Side.US)
    reshuffle = turns_to_reshuffle(obs)
    horizon = LAST_TURN - obs.turn
    masses = cycle_deal_masses(obs)
    if reshuffle <= horizon:
        assert len(masses) == reshuffle
        assert masses[-1] == 1.0, 'the exhausting deal takes every card left'
    else:
        assert len(masses) == horizon
    # Past the end: no future deal, no masses.
    late = replace(obs, turn=10)
    assert cycle_deal_masses(late) == ()


def test_the_exhausting_deal_share_is_the_survival_to_that_deal():
    """`exhausting_deal_share` is the part of today's pile first dealt on the
    reshuffle turn itself -- played after the recycled pile was built, so
    bound for reshuffle 2 and not for the bucket 3 the schedule prices."""
    from dataclasses import replace

    from struggler.engine.core import LAST_TURN
    from struggler.bots.strategic.public_cards import exhausting_deal_share

    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(Side.US)
    survival = 1.0
    for mass in cycle_deal_masses(obs)[:-1]:
        survival *= 1.0 - mass
    assert exhausting_deal_share(obs) == survival
    # A pile that is drained by the very next deal: every card in it now is
    # dealt by that deal, so the whole share is the exhausting one.
    imminent = replace(obs, turn=9, draw_pile_size=5)
    assert turns_to_reshuffle(imminent) == 1
    assert exhausting_deal_share(imminent) == 1.0
    # A pile that outlasts the game has no exhausting deal to share.
    never = replace(obs, turn=9, draw_pile_size=500)
    assert turns_to_reshuffle(never) > LAST_TURN - never.turn
    assert exhausting_deal_share(never) == 0.0


def test_entering_covers_every_period_after_the_first():
    assert set(ENTERING) == {t for t in ENTRY_TURN.values() if t > 1}


def test_the_docstring_quotes_the_counts_the_constant_derives():
    """The counts drift in prose after they are fixed in code.

    `ENTERING` was three cards short per period because it took
    `Engine.__init__`'s flag rather than `Engine.new_game`'s; the constant
    was corrected and the same wrong numbers survived in the docstring
    twenty lines below it, and from there into two working notes. That is
    shape 4 -- two statements of one rule, drifting -- so the prose is
    checked against the constant rather than trusted to be re-read.
    """
    doc = turns_to_reshuffle.__doc__ or ''
    quoted = {period: int(count) for count, period
              in re.findall(r'(\d+)\s+(Mid|Late) War', doc)}
    assert quoted == {'Mid': ENTERING[4], 'Late': ENTERING[8]}, (
        f'the docstring quotes {quoted} but ENTERING derives '
        f'{{"Mid": {ENTERING[4]}, "Late": {ENTERING[8]}}}. Fix the prose, '
        f'not this test: the constant is checked against the engine by '
        f'test_entering_matches_what_the_engine_adds.')


def test_the_discount_is_pinned_to_the_horizon_it_was_fitted_against():
    """`scoring_discount` is fitted against `turns_to_reshuffle`'s output, and
    nothing connected them until this.

    THE DEFECT THIS GATES IS NOT A VALUE, IT IS A COUPLING. `scoring_schedule`
    discounts the second scoring by `scoring_discount ** turns_to_reshuffle`,
    so the two are one estimate wearing two names: move the horizon and the
    discount is refitted whether anyone meant to or not, silently, with every
    test still green.

    That is not hypothetical. 9b90ef0 lengthened the turn-3 horizon from 1.55
    turns to 5.10 -- CORRECTLY; the constant it fixed is checked against the
    engine by `test_entering_matches_what_the_engine_adds`. At the shipped
    discount of 0.8 that cut the second scoring's weight from 0.708 to 0.320
    and turn-3 urgency by 22.7%, and a four-anchor drift bisect measured the
    commit at about 8 points of strength. Every test passed throughout,
    because each half was right on its own.

    So this pins the PRODUCT, not either factor. A change to the horizon is
    allowed; a change that silently moves what a scoring card is worth is
    not. If this fails, the question is not "what is the new horizon" but
    "what does `scoring_discount` have to become to keep the product where
    the strength measurements put it".
    """
    # Branch experiment/turn-discount-two-state: the scalar this guarded is
    # superseded -- `_scoring_weight_uncached` no longer reads
    # `scoring_discount`, so the old product would pass while guarding
    # nothing. The tripwire moves to the new product for the same abstract
    # fixture: a live card (this cycle plus one post-reshuffle cycle) on a
    # stability-2 battleground banks r + r squared. Same function as before:
    # a change that silently moves what a scoring card is worth must fail
    # here, not in a gate post-mortem. If the gate rejects the branch, this
    # rewrite goes away with it.
    from struggler.bots.strategic.evaluator import retention_p

    r = retention_p(2)
    urgency = r + r ** 2
    assert 1.35 <= urgency <= 1.55, (
        f'two-cycle scoring urgency is {urgency:.3f} at retention {r}. See '
        f'docs/notes/claude/2026-09-12-the-reshuffle-fix-cost-eight-points.md '
        f'before changing either the table or the compounding.')


def test_scoring_buckets_name_five_terms_and_reproduce_the_schedule():
    """Step 1 of the value rebuild: the sum can name its terms.

    `scoring_buckets` derives from `scoring_schedule`, so the horizon cap
    and the Southeast-Asia-once rule apply unchanged: turns==0 becomes
    buckets (1, 2), any later scheduled scoring becomes bucket 3, no
    schedule means no buckets. Bucket 4 (post-reshuffle-2) is never emitted
    yet -- no second-reshuffle timing exists -- and bucket 5 (final scoring)
    is priced separately from `final_scoring_odds`, as before.

    Behaviour-preserving by construction: buckets 1+2 at half weight sum to
    exactly what the old turns==0 term priced, bucket 3 is the old
    post-reshuffle term unchanged. If this fails, the widening moved what a
    scoring card is worth and the parity corpus -- not this test -- is what
    needs re-capture review.
    """
    import dataclasses

    from struggler.bots.strategic import evaluator as ev
    from struggler.bots.strategic.public_cards import scoring_buckets, scoring_schedule

    engine = Engine(seed=0)
    obs = engine.observe(Side.US)
    cards = ('Middle_East_Scoring', 'Asia_Scoring', 'Africa_Scoring',
             'Europe_Scoring', 'South_America_Scoring', 'Southeast_Asia_Scoring')
    r, hand_mult = ev.retention_p(2), 1.2
    for turn in range(1, 11):
        now = dataclasses.replace(obs, turn=turn)
        for card in cards:
            buckets = scoring_buckets(now, card)
            assert set(buckets) <= {1, 2, 3}, (turn, card, buckets)
            schedule = scoring_schedule(now, card)
            if not schedule:
                assert buckets == (), (turn, card)
                continue
            expected = [b for t in schedule for b in ((1, 2) if t == 0 else (3,))]
            assert tuple(expected) == buckets, (turn, card, schedule, buckets)
            for held in (False, True):
                old = sum(r ** (1 if t == 0 else 2) * (hand_mult if held and t == 0 else 1.)
                          for t in schedule)
                new = sum((0.5 * r * (hand_mult if held else 1.) if b in (1, 2)
                           else r ** 2) for b in buckets)
                assert old == new, (turn, card, held, old, new)
