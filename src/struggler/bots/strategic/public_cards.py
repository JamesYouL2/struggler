"""Where a card is, from public information only (shared by every bot)."""
from struggler.engine import Observation, Subregion
from struggler.engine.cards import (ENTRY_TURN, cards_entering, entry_turn,
                                    hand_limit, load_cards)
from struggler.engine.core import SCORING_CARD_REGION

CARDS = load_cards()
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')
LAST_TURN = 10  # Engine._advance_past_turn_boundary finishes the game after it


# P(final scoring | reaching the start of turn t), a provisional human prior.
# Source: https://twstourney.wordpress.com/2026-round-4/ (checked 2026-09-09).
# Six of 27 listed games ended at FS (games 2, 3, 8, 10, 15, 19). Ending-turn
# counts T1..T10, with FS mapped to T10: (1, 0, 1, 3, 6, 1, 2, 5, 2, 6).
# Each denominator below is the number reaching that turn. Keep all listed
# games, including held-card losses and differing bids; this is not a pure
# US+2 cohort. WBC aggregate percentages cannot supply these denominators.
# Only six games reached T10, all ending at FS: the empirical 1.0 is NOT a
# guarantee for a new position. This small, selected tournament round needs
# broader validation; the prior ignores VP, board state and action round.
# scripts/game_endings.py currently counts reason='final_vp', which misses
# some engine final-scoring endings; its output is not directly comparable.
FINAL_SCORING_ODDS = (6/27, 6/26, 6/26, 6/25, 6/22, 6/16, 6/15, 6/13, 6/8, 6/6)


def turns_to_final_scoring(obs: Observation) -> int:
    """Turns from now to the end of the last turn, when every region is scored
    once whatever the deck still holds (`Engine._finish_game`).

    This is the horizon: a scoring predicted for turn 11 never happens."""
    return max(0, LAST_TURN - obs.turn)


def final_scoring_odds(obs: Observation) -> float:
    """How likely this game is to reach final scoring at all, from here."""
    return FINAL_SCORING_ODDS[min(LAST_TURN, max(1, obs.turn)) - 1]


def card_state(obs: Observation, card: str) -> str:
    """'hand' (ours), 'discard', 'removed', 'future' (its period has not entered
    the deck yet: a static, public schedule), else 'unseen' (draw pile or the
    opponent's hand -- deliberately indistinguishable, mandate #4)."""
    if card in obs.removed_cards:
        return 'removed'
    if card in obs.hand:
        return 'hand'
    if card in obs.discard_pile:
        return 'discard'
    if obs.turn < entry_turn(CARDS[card]):
        return 'future'
    return 'unseen'


# How many cards join the draw pile at the start of each turn, from the
# static period schedule. The deck is not a fixed pool: it roughly doubles
# at turn 4 and grows by half again at turn 8.
# `True`, matching `Engine.new_game`, which is how every played game is
# built -- benchmark, gate and tests alike. `Engine.__init__` defaults the
# flag the other way, for bare engines in unit tests, and taking that
# default here made this three cards short per period in every real game.
# Caught by the engine's new "MID_WAR enters: 49 cards" log line the day
# it was added, against this file's 46. Gated by
# tests/test_public_cards.py::test_entering_matches_what_the_engine_adds.
ENTERING = {turn: len(cards_entering(CARDS, period, True))
            for period, turn in ENTRY_TURN.items() if turn > 1}


def turns_to_reshuffle(obs: Observation) -> int:
    """Turns until the draw pile runs out and the discards come back.

    Walked forward turn by turn rather than divided, because the pile is
    refilled twice on a fixed schedule -- 46 Mid War cards at turn 4 and 21
    Late War at turn 8 -- and dividing today's pile by the draw rate
    silently assumes neither happens.

    Measured over 16 self-play games before this was fixed: reshuffles land
    at turn 3 (15 of 16 games) and turn 9 (7), never more than twice in a
    game. The old estimate agreed at turns 1-2 and 8, and was early through
    the entire mid war -- asked at turn 5 it said 2.5 turns, putting the
    reshuffle at 7.5 when it actually came at 9. That matters because
    `scoring_schedule` returns `(0, reshuffle)` discounted by
    TURN_DISCOUNT ** t, so predicting 7.5 instead of 9 under-discounts the
    second scoring by about 1.4x and over-values every scoring card in hand
    through the part of the game where most scoring happens.

    Returns a value past the horizon when the pile outlasts the game, which
    `scoring_schedule` then filters: a reshuffle that never comes must
    contribute nothing, not a discounted something.
    """
    pile = obs.draw_pile_size
    for ahead in range(1, LAST_TURN - obs.turn + 1):
        turn = obs.turn + ahead
        pile += ENTERING.get(turn, 0)
        pile -= max(1, 2 * hand_limit(turn) - 2)  # both deals, less the held cards
        if pile < 0:
            return ahead
    return LAST_TURN - obs.turn + 1  # never, within this game


def scoring_schedule(obs: Observation, card: str) -> tuple[int, ...]:
    """When `card` is expected to score again, as turns from now, from the
    static period schedule and where the card is now. A live card (in a
    hand or the draw pile) scores this cycle and again after the reshuffle;
    a discarded one after the reshuffle; a card whose period has not
    entered the deck from its entry turn. Southeast Asia Scoring is
    removed after its one play.

    Capped at the end of the game. Without that, a reshuffle two turns away
    on turn 9 promised a scoring on turn 11, and the Late War is exactly
    where the remaining scorings decide the result."""
    state = card_state(obs, card)
    once = card == 'Southeast_Asia_Scoring'
    if state == 'removed' or once and state == 'discard':
        return ()
    horizon = turns_to_final_scoring(obs)
    reshuffle = turns_to_reshuffle(obs)
    if state == 'future':
        schedule = (entry_turn(CARDS[card]) - obs.turn,)
    elif state == 'discard':
        schedule = (reshuffle,)
    else:
        schedule = (0,) if once else (0, reshuffle)
    return tuple(turns for turns in schedule if turns <= horizon)


def scoring_cards_for(info) -> list[str]:
    """The scoring cards that count `info`'s country."""
    cards = [c for c, r in SCORING_CARD_REGION.items() if r is info.region]
    if Subregion.SOUTHEAST_ASIA in info.subregions:
        cards.append('Southeast_Asia_Scoring')
    return cards
