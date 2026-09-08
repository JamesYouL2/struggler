"""Where a card is, from public information only (shared by every bot)."""
from struggler.engine import Observation
from struggler.engine.cards import entry_turn, load_cards

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
