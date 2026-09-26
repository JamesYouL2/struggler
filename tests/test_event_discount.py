"""Events still to come discount the countries they are aimed at.

The maintainer's rule (2026-09-26): Vietnam is worth less than Laos while
Vietnam Revolts is live, South Korea less than North Korea (Korean War),
Egypt less than Libya (Nasser), and Mid and Late War cards count before
they enter the deck. `StrategicWeights.event_exposure` prices it (0 as
shipped, exact); `public_cards.p_event_fires` is each card's chance to
fire; `evaluator.event_discount` turns both into a per-country multiplier.
"""
from __future__ import annotations

import dataclasses

import pytest

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic import public_cards as pc
from struggler.engine import Engine, Side


def _obs(turn: int = 1, side: Side = Side.US, **changes):
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(side)
    return dataclasses.replace(obs, turn=turn, **changes)


def _discount(obs, weight: float = 0.5):
    bot = StrategicPlayer(StrategicWeights(event_exposure=weight))
    bot.prepare(obs)
    t = bot._terrain
    return {c: bot._discount[t.index[c]] for c in t.ids}


def test_off_is_nothing_at_all():
    bot = StrategicPlayer()
    bot.prepare(_obs())
    assert bot._discount is None


def test_the_maintainers_examples_discount_the_target_not_its_neighbour():
    d = _discount(_obs())
    assert d['Vietnam'] < d['Laos_Cambodia'] == 1.0
    assert d['South_Korea'] < d['North_Korea']
    assert d['Egypt'] < d['Libya']


def test_a_removed_card_discounts_nothing():
    obs = _obs(turn=3)
    live = _discount(obs)['Vietnam']
    gone = _discount(dataclasses.replace(obs, removed_cards=tuple(obs.removed_cards) + ('Vietnam_Revolts',)))
    assert live < 1.0
    assert gone['Vietnam'] == 1.0


def test_late_war_cards_count_before_they_enter_the_deck():
    """Iranian Hostage Crisis (Late War) is aimed at Iran; on turn 1 it is
    not in any deck yet and still discounts Iran."""
    obs = _obs(turn=1)
    assert pc.card_state(obs, 'Iranian_Hostage_Crisis') == 'future'
    assert pc.p_event_fires(obs, 'Iranian_Hostage_Crisis') == 1.0
    assert _discount(obs)['Iran'] < 1.0


@pytest.mark.parametrize('state, expected', [('removed', 0.0), ('hand', 1.0)])
def test_p_event_fires_at_the_ends(state, expected):
    obs = _obs(turn=2)
    if state == 'removed':
        obs = dataclasses.replace(obs, removed_cards=tuple(obs.removed_cards) + ('Nasser',))
    else:
        obs = dataclasses.replace(obs, hand=tuple(obs.hand) + ('Nasser',))
    assert pc.p_event_fires(obs, 'Nasser') == expected


def test_p_event_fires_is_a_probability_for_every_card():
    obs = _obs(turn=5)
    for card in pc.CARDS:
        assert 0.0 <= pc.p_event_fires(obs, card) <= 1.0, card


def test_the_multiplier_is_bounded_by_the_weight_and_most_of_the_map_is_untouched():
    """Summing every share saturated the map (Canada at the full discount
    from Marshall Plan, Socialist Governments, Pershing II...). Only aimed
    events count, so most countries carry no discount at all."""
    d = _discount(_obs(), weight=0.3)
    assert min(d.values()) >= 1.0 - 0.3
    assert d['Canada'] == 1.0
    assert sum(v == 1.0 for v in d.values()) > len(d) / 2
    assert ev.event_discount(StrategicPlayer()._terrain, 0.0, {}) is None
