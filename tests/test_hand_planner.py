"""The assignment solver's exactness: `bots/strategic/hand_planner.py`.

Prices in, allocation out, arithmetic exact -- so unlike the game-level
tests these assert on designed numbers, not approximations. Each test is
one constraint or one ruling from
`docs/notes/pi/2026-09-22-assignment-planner-design.md`.
"""
from __future__ import annotations

import pytest

from struggler.bots.strategic.hand_planner import (
    NEG, Card, plan_hand, solve_hand,
)


def _play(*prices: float) -> tuple[float, ...]:
    return tuple(prices)


def test_the_solver_allocates_headline_rounds_and_holds_and_sums_exactly():
    cards = [
        Card('A', headline=5.0, play=_play(1.0, 1.0), hold=0.5),
        Card('B', headline=4.0, play=_play(3.0, 3.0), hold=0.1),
        Card('C', play=_play(2.0, 2.0), hold=0.9),
        Card('D', play=_play(0.4, 0.4), hold=2.0),
    ]
    plan = solve_hand(cards, rounds=2)
    assert plan is not None
    assert plan.headline == 'A'          # 5.0 beats B's 4.0
    assert set(plan.rounds) == {('play', 'B'), ('play', 'C')}
    assert plan.holds == ('D',)          # holding D (2.0) beats playing it
    assert plan.value == 12.0            # 5 + 3 + 2 + 2


def test_the_headline_is_chosen_knowing_what_the_hand_needs():
    # A headlines better but plays better still; the plan headlines B so
    # A's play is not stranded. Per-card pricing headlines A and scores 6.
    cards = [
        Card('A', headline=6.0, play=_play(5.0, 5.0), hold=0.0),
        Card('B', headline=5.5, play=_play(0.0, 0.0), hold=0.0),
    ]
    plan = solve_hand(cards, rounds=1)
    assert plan is not None
    assert plan.headline == 'B'
    assert plan.rounds == (('play', 'A'),)
    assert plan.value == 10.5            # 5.5 + 5.0, against 6.0 + 0.0


def test_a_scoring_card_is_never_held_even_at_a_price_loss():
    scoring = Card('S', play=_play(-10.0, -10.0), may_hold=False)
    other = Card('T', play=_play(0.0, 0.0), hold=5.0)
    plan = solve_hand([scoring, other], rounds=1, headline_slots=0)
    assert plan is not None
    assert plan.rounds == (('play', 'S'),)   # forced to play, never held
    assert plan.holds == ('T',)
    assert plan.value == -5.0                # and it pays for the privilege


def test_the_un_unit_consumes_two_cards_in_one_round():
    un = Card('U', un_play=2.0, hold=0.0)
    partner = Card('P', play=_play(1.0, 1.0), un_partner=7.0, hold=0.0)
    filler = Card('X', play=_play(3.0, 3.0), hold=0.0)
    plan = solve_hand([un, partner, filler], rounds=2,
                      headline_slots=0, un_key='U')
    assert plan is not None
    # UN + P in one unit (2.0 + 7.0) plus X (3.0) beats P and X played
    # separately (1.0 + 3.0) by exactly the suppressed event.
    assert ('un', 'U', 'P') in plan.rounds
    assert ('play', 'X') in plan.rounds
    assert plan.holds == ()
    assert plan.value == 12.0


def test_the_space_pick_goes_to_space_only_when_it_pays():
    pick = Card('P', play=_play(1.0, 1.0), space=4.0, hold=0.5)
    other = Card('X', play=_play(3.0, 3.0), hold=0.0)
    plan = solve_hand([pick, other], rounds=1, headline_slots=0,
                      space_keys=('P',))
    assert plan is not None
    assert plan.rounds == (('space', 'P'),)  # 4.0 > 3.0 + 0.0 and > 1.0 + 0.0
    assert plan.holds == ('X',)
    assert plan.value == 4.0

    # But the pick is not conscripted: when playing it pays better, it plays.
    rich = Card('P', play=_play(6.0, 6.0), space=4.0, hold=0.5)
    plan = solve_hand([rich, other], rounds=1, headline_slots=0,
                      space_keys=('P',))
    assert plan is not None
    assert plan.rounds == (('play', 'P'),)
    assert plan.value == 6.0


def test_the_two_solve_mix_returns_both_allocations_with_their_weights():
    picks = [
        Card('P', play=_play(0.1, 0.1), space=4.0, hold=0.0),
        Card('Q', play=_play(0.1, 0.1), space=3.0, hold=0.0),
        Card('X', play=_play(5.0, 5.0), hold=0.0),
    ]
    plans = plan_hand(picks, rounds=3, headline_slots=0,
                      space_keys=('P', 'Q'),
                      space_slot_weights=((1, 0.6), (2, 0.4)))
    assert plans is not None
    assert [(p.probability, p.slots) for p in plans] == [(0.6, 1), (0.4, 2)]
    one, two = plans
    assert [u for u in one.assignment.rounds if u[0] == 'space'] == \
        [('space', 'P')]
    assert [u for u in two.assignment.rounds if u[0] == 'space'] == \
        [('space', 'P'), ('space', 'Q')]


def test_scoring_timing_follows_the_plan_not_a_constant():
    # Ruling 5: G's play adds 2.0 to the scoring region, so S scores for
    # 3.0 after it and 1.0 before it. The fixed point finds that order;
    # `+2 x action_round` would have nudged blindly.
    gain_card = Card('G', play=_play(5.0, 5.0), hold=0.0)
    scoring = Card('S', play=_play(1.0, 1.0), may_hold=False)
    plans = plan_hand([gain_card, scoring], rounds=2, headline_slots=0,
                      gain={'G': 2.0})
    assert plans is not None
    plan = plans[0].assignment
    assert plan.rounds == (('play', 'G'), ('play', 'S'))
    assert plan.value == 8.0            # 5.0 + (1.0 + 2.0 planned before it)


def test_more_scoring_cards_than_play_slots_is_infeasible_not_a_crash():
    two_scoring = [
        Card('S1', play=_play(1.0, 1.0), may_hold=False),
        Card('S2', play=_play(1.0, 1.0), may_hold=False),
    ]
    assert solve_hand(two_scoring, rounds=1, headline_slots=0) is None
    plan = solve_hand(two_scoring, rounds=2, headline_slots=0)
    assert plan is not None
    assert set(plan.rounds) == {('play', 'S1'), ('play', 'S2')}


def test_input_order_does_not_change_the_plan():
    cards = [
        Card('A', headline=5.0, play=_play(1.0, 1.0), hold=0.5),
        Card('B', headline=4.0, play=_play(3.0, 3.0), hold=0.1),
        Card('C', play=_play(2.0, 2.0), hold=0.9),
    ]
    forward = solve_hand(cards, rounds=2)
    backward = solve_hand(list(reversed(cards)), rounds=2)
    assert forward == backward


def test_ineligible_slots_are_poisoned_not_ranked():
    # A card priced NEG everywhere playable can only be held or decline
    # the hand entirely.
    anchor = Card('H', headline=2.0, play=_play(2.0), hold=0.0)
    filler = Card('F', play=_play(1.5), hold=0.0)
    dead = Card('Z', hold=0.25)
    plan = solve_hand([anchor, filler, dead], rounds=1, headline_slots=1)
    assert plan is not None
    assert plan.headline == 'H'
    assert plan.rounds == (('play', 'F'),)
    assert plan.holds == ('Z',)
    assert plan.value == 3.75
    assert NEG < 0.0  # the sentinel is the poison it is meant to be
