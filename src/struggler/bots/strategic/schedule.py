"""When each scoring can still pay, and with what occurrence mass.

The rebuild's schedule half: from the public deck state (`public_cards`),
every future scoring opportunity as a reporting category -- this turn, later
this cycle, later cycles, final scoring -- with explicit timing and an
explicit occurrence mass. A scoring opportunity is (region payout, bucket) or
the Southeast Asia card; the payout half (`forecast`) prices the board if it
pays, this module says when it can pay and how likely that is.

Occurrence mass, first version -- every number below is documented where it
is assumed, because the September proposal's failure mode was silent means
standing in for dated masses:

- Bucket 1 (this turn): 1.0 when WE hold the card. Scoring cards may not be
  held past the end of the turn (the engine forces their play:
  `Engine.must_play_scoring`), so a scoring in our hand is played this turn
  -- barring the game ending first, which nothing here models yet (see the
  gap note below). 0.5 for a live card whose holder is unknown.
- Bucket 2 (this cycle): 0.5 for a live card of unknown holder, 0.0 when we
  hold it (it fires this turn, not later). The halves preserve exactly what
  the current urgency consumer prices for this cycle; they are holder
  uncertainty, not timing -- an unseen card may be played this very turn by
  its holder, so bucket 2's range overlaps bucket 1 at turn 0. Shaping the
  halves by who likely holds it (`p_opponent_holds`) is factor-2 work.
- Bucket 3 (next cycle): 1.0 whenever the card returns post-reshuffle
  (live or discarded) or enters a future period -- same documented gap about
  the game getting there.
- Bucket 4 (second reshuffle): named, never emitted, zero mass. No timing
  model exists for it; emitting it would be inventing one.
- Bucket 5 (final scoring): `final_scoring_odds` for each of the six region
  cards. Never for Southeast Asia: final scoring scores every *region*
  (`Engine._finish_game`), and the one-shot card is gone by then if played,
  unplayed-but-live cards... -- no: a live SEA card still scores its regions
  at final through Asia's tiers, but the SEA card itself never fires there.
  Its mass lives only in buckets 1-3.

Gap note (applies to every mass above): nothing discounts for the game
ending early -- the 20 VP auto-victory, Europe control, DEFCON loss,
Wargames. "Removed scoring opportunities and opportunities beyond game end
contribute zero" is honored (they are absent, not zero-weighted); early
endings before a live scoring are the unmodeled part, and the README
forbids equating a rules deadline with certainty. That model is later work;
these masses say what the deck guarantees, nothing more.

Timing is turns from now as a (lo, hi) range per category -- never one date
per category. Ranges may overlap (see buckets 1+2 above); a timing model
narrows them, it does not re-split the mass.
"""
from __future__ import annotations

from typing import NamedTuple

from struggler.engine import Observation, Region
from struggler.engine.core import SCORING_CARD_REGION
from struggler.bots.strategic import public_cards as pc

SEA_SCORING = 'Southeast_Asia_Scoring'

# Every scoring opportunity the schedule can name, in a fixed order: the six
# region cards in `SCORING_CARD_REGION` order, Southeast Asia last.
SCORING_CARDS: tuple[str, ...] = (*tuple(SCORING_CARD_REGION), SEA_SCORING)

# Bucket 4 exists in the five-bucket vocabulary and carries zero mass until a
# second-reshuffle timing model exists. It is named here so a consumer that
# iterates 1..5 finds silence, not a KeyError-shaped surprise.
BUCKET_SECOND_RESHUFFLE = 4


class Opportunity(NamedTuple):
    """One scoring's one category: `card` may pay in `bucket` between
    `turns_lo` and `turns_hi` turns from now, with occurrence mass
    `occurrence` -- P(it pays before game end | today's public deck state).

    Masses are in [0, 1] but need not sum to anything across buckets: buckets
    1+2 split this cycle's mass by holder uncertainty, bucket 3 is the next
    cycle's independent chance, bucket 5 the final-scoring chance.
    """

    card: str
    bucket: int
    turns_lo: int
    turns_hi: int
    occurrence: float


def opportunities(obs: Observation, card: str) -> tuple[Opportunity, ...]:
    """Every future scoring opportunity for one scoring card, latest category last."""
    if card not in SCORING_CARDS:
        raise ValueError(f"not a scoring card: {card}")
    state = pc.card_state(obs, card)
    if state == 'removed':
        return ()
    once = card == SEA_SCORING
    if once and state == 'discard':
        return ()  # spent: the one-shot never fires again
    horizon = pc.turns_to_final_scoring(obs)
    reshuffle = pc.turns_to_reshuffle(obs)
    out: list[Opportunity] = []
    held = state == 'hand'
    if state in ('hand', 'unseen'):
        # This cycle. Held: we play it this turn (the engine forbids holding
        # it past end of turn), so the whole mass sits in bucket 1. Unknown
        # holder: the documented halves.
        out.append(Opportunity(card, 1, 0, 0, 1.0 if held else 0.5))
        if not held:
            # Capped at the horizon: plays dated past game end contribute zero.
            out.append(Opportunity(card, 2, 0, min(reshuffle, horizon), 0.5))
    if state in ('hand', 'unseen', 'discard'):
        # Next cycle, if the reshuffle (and hence the game) gets there.
        if reshuffle <= horizon:
            out.append(Opportunity(card, 3, reshuffle, horizon, 1.0))
    elif state == 'future':
        entry = pc.entry_turn(pc.CARDS[card]) - obs.turn
        if entry <= horizon:
            out.append(Opportunity(card, 3, entry, horizon, 1.0))
    if not once:
        # Final scoring reaches every region's tiers, whatever the deck holds.
        out.append(Opportunity(card, 5, horizon, horizon, pc.final_scoring_odds(obs)))
    return tuple(out)


def full_schedule(obs: Observation) -> tuple[Opportunity, ...]:
    """Every scoring opportunity still in the game, cards in `SCORING_CARDS` order."""
    out: list[Opportunity] = []
    for card in SCORING_CARDS:
        out.extend(opportunities(obs, card))
    return tuple(out)


def region_of(card: str) -> Region | None:
    """The region whose tiers `card` scores, or None for Southeast Asia's own payout."""
    if card == SEA_SCORING:
        return None
    return SCORING_CARD_REGION[card]
