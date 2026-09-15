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

from struggler.bots.strategic.public_cards import ENTERING, turns_to_reshuffle
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
