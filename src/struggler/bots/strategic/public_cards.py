"""Where a card is, from public information only (shared by every bot)."""
from struggler.engine import Observation, Period, Subregion
from struggler.engine.cards import (ENTRY_TURN, cards_entering, entry_turn,
                                    hand_limit, load_cards)
from struggler.engine.core import LAST_TURN, SCORING_CARD_REGION

CARDS = load_cards()
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')
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
    if card == CHINA_CARD:
        # Face up in front of whoever holds it: `obs.china_card_owner` is
        # public and it counts toward nobody's hand size. Left as 'unseen' it
        # was a permanent phantom in the unseen pool, inflating it by one for
        # the whole game and mispricing every per-card probability drawn from
        # it.
        return 'china'
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


def deck_walk(obs: Observation) -> tuple[tuple[int, int, int, int], ...]:
    """The draw pile's forward walk, one row per future deal this cycle.

    Row = `(turn, pile_before, entering, deal)`: the effective pile for the
    deal at `turn` is `pile_before + entering`, and `pile_after = effective
    - deal`, which may go negative -- that row is the *exhausting* deal (the
    pile ran out mid-deal; that is the reshuffle's trigger). Shared by
    `turns_to_reshuffle`, `cycle_deal_masses` and `post_reshuffle_deal_masses`,
    so the three walk one deck arithmetic instead of three copies of it.
    """
    pile = obs.draw_pile_size
    walk = []
    for ahead in range(1, LAST_TURN - obs.turn + 1):
        turn = obs.turn + ahead
        entering = ENTERING.get(turn, 0)
        deal = deal_size(turn)
        walk.append((turn, pile, entering, deal))
        pile += entering - deal
    return tuple(walk)


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
    for turn, pile_before, entering, deal in deck_walk(obs):
        if pile_before + entering - deal < 0:
            return turn - obs.turn
    return LAST_TURN - obs.turn + 1  # never, within this game


def deal_size(turn: int) -> int:
    """Cards dealt at the start of `turn`: both hands up to `hand_limit`,
    less the one card each side may hold over.

    One rule, one place: `turns_to_reshuffle` and `cycle_deal_masses` share
    it, so the reshuffle walk and the deal-probability walk cannot drift.
    A native port takes this as the deal arithmetic wholesale."""
    return max(1, 2 * hand_limit(turn) - 2)


def cycle_deal_masses(obs: Observation) -> tuple[float, ...]:
    """Per-deal conditional masses for the remaining full deals this cycle.

    Each entry is P(this deal delivers a given pile card | it survived to
    the deal), as `deal / pile_before`: `deal_size(turn)` cards drawn
    uniformly from the pile awaiting that deal (today's remainder plus what
    `ENTERING` adds that turn). Uniform order is the same prior
    `p_opponent_holds` uses -- the right prior, and the pile order never
    leaks -- so this is deck calculation, not a fitted half.

    The walk shares `deal_size` and `ENTERING` with `turns_to_reshuffle`,
    and stops the same way: the deal that exhausts the pile belongs to the
    next cycle (it draws partly from the recycled discards), so it is
    excluded here and counted there. No full deals left means `()`: the
    horizon is past (turn 10), the pile is empty, or the reshuffle is this
    coming deal.

    Mid-turn draws are unmodeled and documented as ~0: Our Man examines and
    returns (`events.py`), net zero after the reshuffle; Ask Not discards
    then redraws at most a hand-size handful against 14-16-card deals, rare
    and small. A scoring drawn mid-turn still fires this cycle, so these
    masses are a lower bound by that handful.

    Callers combine with the pile share: for an unseen card,
    P(dealt this cycle | pile now) = 1 - prod(1 - m), and bucket 2's mass
    is P(pile now) times that. Conservation the tests pin:
    sum(unconditional) + prod(1 - m) == 1, where unconditional_k
    = m_k * prod_{j<k}(1 - m_j)."""
    masses: list[float] = []
    for _turn, pile_before, entering, deal in deck_walk(obs):
        pile = pile_before + entering
        if pile - deal < 0:
            break  # exhausting deal: next cycle's, not this one's
        if pile <= 0:
            break
        masses.append(deal / pile)
    return tuple(masses)


def recycled_pile_size(obs: Observation, turn: int) -> int:
    """Estimated size of the deck when the reshuffle at `turn` reaches the
    recycled discards: every shuffle-able card that has entered by then
    (the same universe `ENTERING` counts, Early War included, optional cards
    included), less the removed cards and the spent Southeast Asia Scoring
    (its one played life takes it out of every later cycle -- the discard
    state makes that public), less the cards both players are still holding.

    The holding estimate is `2 * hand_limit(turn)`: both hands were topped
    up before the exhausting deal fell short, so each holds a full limit,
    and the deal's recycled remainder tops them further. That remainder is
    left out of the estimate, which biases the pile small -- this pile is
    the denominator of a later deal mass -- so the bucket-3 masses it feeds
    are a lower bound by at most one partial deal.
    """
    entered = len(cards_entering(CARDS, Period.EARLY_WAR, True))
    entered += sum(n for t, n in ENTERING.items() if t <= turn)
    live = entered - len(obs.removed_cards)
    if 'Southeast_Asia_Scoring' in obs.discard_pile:
        live -= 1  # the one-shot is out of every later cycle once discarded
    return max(0, live - 2 * hand_limit(turn))


def post_reshuffle_deal_masses(obs: Observation) -> tuple[float, ...]:
    """Per-deal conditional masses for the deals after the (first) reshuffle,
    down to the end of the game: each entry is P(a recycled card is dealt in
    that deal | it survived the deals before it), the same `deal / pile`
    shape as `cycle_deal_masses` over the recycled deck. The deck's size is
    `recycled_pile_size`'s estimate, and its shortage against the
    exhausting deal is taken from the shared `deck_walk`, not guessed: the
    reshuffle fires mid-deal, so that deal's remainder is drawn from the
    recycle at mass `deficit / recycle` and the rest of the deal was
    already drawn.

    Uniform order is the same prior `p_opponent_holds` uses -- the pile
    order never leaks -- so this is deck calculation over a documented
    pile-size estimate, not a fitted half. A deal that exceeds the pile
    before the last turn is reshuffle 2: its leftover belongs to the next
    cycle, which no pricing model exists for yet, so the walk stops there.
    The last turn's exhausting deal is IN, fully: every card it deals is
    played before final scoring. What nobody drew is the walk's documented
    truncation (prod(1 - m) is the never-dealt mass).

    Returns () when the reshuffle is absent (the pile outlasts the game) or
    past the horizon (turn 10).
    """
    reshuffle = turns_to_reshuffle(obs)
    if reshuffle > turns_to_final_scoring(obs):
        return ()
    start = obs.turn + reshuffle
    deficit = 0
    for _turn, pile_before, entering, deal in deck_walk(obs):
        if pile_before + entering - deal < 0:
            deficit = deal - (pile_before + entering)
            break
    pile = recycled_pile_size(obs, start)
    masses: list[float] = []
    for turn in range(start, LAST_TURN + 1):
        if turn > start:
            # The reshuffle turn's entries were drawn pre-exhaust (they are
            # inside deck_walk's effective pile there); adding them again
            # here would double-count them.
            pile += ENTERING.get(turn, 0)
        deal = deficit if turn == start else deal_size(turn)
        if pile <= 0:
            break
        if deal <= 0:
            continue
        if pile - deal < 0 and turn < LAST_TURN:
            break  # an exhausting deal before the last one: reshuffle 2's
        masses.append(min(deal, pile) / pile)
        pile -= deal
    return tuple(masses)



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


def scoring_buckets(obs: Observation, card: str) -> tuple[int, ...]:
    """Which of the five future-scoring buckets `card` can still pay in.

    The buckets (docs/notes/claude/2026-09-12-value-times-probability-times-discount.md):
    1 scores this turn, 2 before the reshuffle but not this turn, 3 after
    reshuffle 1, 4 after reshuffle 2, 5 the end-of-game final scoring.

    Derived from `scoring_schedule`, so the horizon cap and the
    Southeast-Asia-once rule apply unchanged: a live card (in a hand or the
    draw pile) names buckets 1+2 this cycle and bucket 3 post-reshuffle; a
    discarded or not-yet-entered one names bucket 3; a gone one names none.
    Bucket 4 is never emitted yet -- no second-reshuffle timing exists, so
    it carries zero mass -- and bucket 5 is priced separately from
    `final_scoring_odds`, as before. Naming the terms is the plumbing; the
    probabilities each bucket pays with are factor 2 of the rebuild.

    Behaviour-preserving by construction: buckets 1+2 split this cycle
    equally (the consumer weights each at half), so 1+2 sum to exactly what
    the old turns==0 term priced, and bucket 3 is the old post-reshuffle
    term unchanged. The parity corpus holds the line."""
    buckets: list[int] = []
    for turns in scoring_schedule(obs, card):
        if turns == 0:
            buckets.extend((1, 2))
        else:
            buckets.append(3)
    return tuple(buckets)


def scoring_cards_for(info) -> list[str]:
    """The scoring cards that count `info`'s country."""
    cards = [c for c, r in SCORING_CARD_REGION.items() if r is info.region]
    if Subregion.SOUTHEAST_ASIA in info.subregions:
        cards.append('Southeast_Asia_Scoring')
    return cards
