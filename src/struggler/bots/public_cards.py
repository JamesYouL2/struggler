"""Where a card is, from public information only (shared by every bot)."""
from struggler.engine import Observation, Subregion
from struggler.engine.cards import entry_turn, hand_limit, load_cards
from struggler.engine.core import SCORING_CARD_REGION

CARDS = load_cards()
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')
LAST_TURN = 10  # Engine._advance_past_turn_boundary finishes the game after it


# P(the game reaches final scoring | it is still running on this turn), by
# turn. Measured over 192 bot-vs-bot games with `scripts/game_endings.py`;
# rerun it to recalibrate.
#
# Final scoring is NOT guaranteed, which is the thing worth knowing here. Only
# 24.5% of those games reached it: 67.2% ended early on the 20 VP auto-victory
# and 7.3% on Wargames, and a DEFCON-1 loss ends one too. Nor does the chance
# climb toward certainty as the game runs on -- 0.42 at turn 9, 0.47 at turn
# 10 -- because a game still alive that late is usually alive precisely
# because it is close, and close games still get decided on VP during turn 10.
# `0.8 ** (10 - turn)`, which is what treating it as certain and discounting
# it like everything else would give, is more than double the real odds from
# turn 8 on.
#
# These are bot games, and a generous proxy: strong human players push for the
# 20 VP win harder than this bot does, so the true odds are lower still.
FINAL_SCORING_ODDS = (0.24, 0.24, 0.24, 0.25, 0.27, 0.29, 0.32, 0.37, 0.42, 0.47)


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


def turns_to_reshuffle(obs: Observation) -> int:
    """Turns until the draw pile runs out and the discards come back."""
    per_turn = max(1, 2 * hand_limit(obs.turn) - 2)  # both deals, less the held cards
    return max(1, -(-obs.draw_pile_size // per_turn))


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
