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
    the deck yet: a static, public schedule), 'china' (face up in front of a
    player, and whose owner is public), else 'unseen'.

    'unseen' means "in the draw pile or the opponent's hand" and the engine
    will not say which -- but that is a statement about `observe()`, not about
    what may be inferred. The docstring here used to say the two were
    "deliberately indistinguishable, mandate #4", which misread the mandate:
    it forbids `observe()` exposing the opponent's card *identities* and the
    identity of undrawn cards, and in the same breath makes the opponent's
    hand *count* public. `p_opponent_holds` below does the inference from
    public counts alone, which is what a strong player does at the table.
    """
    if card in obs.removed_cards:
        return 'removed'
    if card in obs.hand:
        return 'hand'
    if card in obs.discard_pile:
        return 'discard'
    # EXPERIMENT (branch experiment/china-phantom, not for main): the China Card
    # is put back into the unseen pool, as it was before bc5ef93, to test
    # whether removing that phantom is what cost HEAD five points against
    # c0ccd95 on the 2026-09-12 gate ladder.
    if obs.turn < entry_turn(CARDS[card]):
        return 'future'
    return 'unseen'


CHINA_CARD = 'The_China_Card'


def unseen_cards(obs: Observation) -> tuple[str, ...]:
    """Every card that is either in the opponent's hand or the draw pile.

    By elimination from public information: the full card set for the eras in
    play, less what has been played, removed, is in our own hand, or is the
    China Card.
    """
    return tuple(cid for cid in CARDS if card_state(obs, cid) == 'unseen')


def unseen_split(obs: Observation) -> tuple[int, int]:
    """`(cards of theirs, cards in the pile)` -- both public counts."""
    return obs.opponent_hand_size, obs.draw_pile_size


def p_opponent_holds(obs: Observation, card: str) -> float:
    """How likely the opponent holds `card`, from public information alone.

    Every input is something mandate #4 explicitly leaves public: their hand
    *count*, the draw pile *size*, the discard pile, the removed cards, and
    our own hand. No card identity of theirs is read.

    Uniform over the unseen pool, which is the right prior and is not the
    interesting part. The interesting part is that the pool shrinks: the draw
    pile empties before every reshuffle, so this rises toward 1 for every
    unseen card as the reshuffle approaches. At the end of turn 2 the Early War
    pile is down to about nine cards (8.8 measured, against the ~5 the first
    arithmetic predicted), and what is left is known *as a set* --
    which is why a strong player knows most of an opponent's hand going into
    turn 3, and why the turn-3 reshuffle is where the information is.

    Returns 0.0 for a card that is not unseen -- ours, played, removed, the
    China Card, or one whose era has not entered.
    """
    if card_state(obs, card) != 'unseen':
        return 0.0
    theirs, pile = unseen_split(obs)
    pool = theirs + pile
    if pool <= 0:
        return 0.0
    return min(1.0, theirs / pool)


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
    refilled twice on a fixed schedule -- 49 Mid War cards at turn 4 and 22
    Late War at turn 8, the counts `ENTERING` derives -- and dividing
    today's pile by the draw rate
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
    if state == 'removed' or (once and state == 'discard'):
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
