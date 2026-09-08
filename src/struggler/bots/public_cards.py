"""Where a card is, from public information only (shared by every bot)."""
from struggler.engine import Observation, Subregion
from struggler.engine.cards import entry_turn, hand_limit, load_cards
from struggler.engine.core import SCORING_CARD_REGION

CARDS = load_cards()
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')


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
    removed after its one play."""
    state = card_state(obs, card)
    once = card == 'Southeast_Asia_Scoring'
    if state == 'removed' or once and state == 'discard':
        return ()
    reshuffle = turns_to_reshuffle(obs)
    if state == 'future':
        return (entry_turn(CARDS[card]) - obs.turn,)
    if state == 'discard':
        return (reshuffle,)
    return (0,) if once else (0, reshuffle)


def scoring_cards_for(info) -> list[str]:
    """The scoring cards that count `info`'s country."""
    cards = [c for c, r in SCORING_CARD_REGION.items() if r is info.region]
    if Subregion.SOUTHEAST_ASIA in info.subregions:
        cards.append('Southeast_Asia_Scoring')
    return cards
