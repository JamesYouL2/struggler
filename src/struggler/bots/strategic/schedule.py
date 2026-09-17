"""When each scoring can still pay, and with what occurrence mass.

The rebuild's schedule half: from the public deck state (`public_cards`),
every future scoring opportunity as a reporting category -- this turn, later
this cycle, later cycles, final scoring -- with explicit timing and an
explicit occurrence mass. A scoring opportunity is (region payout, bucket) or
the Southeast Asia card; the payout half (`forecast`) prices the board if it
pays, this module says when it can pay and how likely that is.

Occurrence mass, deck-math version -- every number below is documented where
it is assumed, because the September proposal's failure mode was silent means
standing in for dated masses:

- Bucket 1 (this turn): 1.0 when WE hold the card. Scoring cards may not be
  held past the end of the turn (the engine forces their play:
  `Engine.must_play_scoring`), so a scoring in our hand is played this turn
  -- barring the game ending first, which nothing here models yet (see the
  gap note below). For a live card of unknown holder, `p_opponent_holds`:
  whoever holds a scoring must play it this turn, so P(it fires this turn)
  is P(the opponent holds it now), from public counts alone.
- Bucket 2 (this cycle): for a live card of unknown holder, P(it sits in the
  pile now) times P(a remaining deal this cycle delivers it), from
  `cycle_deal_masses` -- the uniform-pile deck walk sharing `deal_size` with
  `turns_to_reshuffle`. Absent when we hold it (it fires this turn, not
  later). The deal that EXHAUSTS the pile is part of this cycle, not the
  next one: the engine draws the pile to empty and reshuffles only then
  (`Engine._draw_card`), so every card still in the pile is dealt by that
  deal with certainty, and its entry is 1.0. Dropping that deal for being
  partly recycled priced a certainty at 0.12 on a turn-9 pile of five.
  Buckets 1+2 split this cycle by holder uncertainty, not timing -- an
  unseen card may be played this very turn by its holder, so bucket 2's
  range overlaps bucket 1 at turn 0.
- Bucket 3 (next cycle): the recycled card is dealt into someone's hand
  post-reshuffle -- the must-play rule (bucket 1) puts a live scoring in
  the discard pile before the reshuffle -- but then it fires the turn it is
  DEALT, not when the cycle opens. The mass is therefore P(dealt before
  game end | the reshuffle happens), from `cycle_deal_masses`'s walk
  continued over the recycled deck (`post_reshuffle_deal_masses`; pile size
  estimated by `recycled_pile_size`, the shuffle-able cards entered by then
  less removed cards, the spent Southeast Asia one-shot and a full `2 x
  hand_limit` of holdings -- every number documented in the module), times
  the share of the card that is IN that recycle:

  - the share dealt by the exhausting deal itself is played on the
    reshuffle turn, after the recycled pile was built, so it belongs to
    reshuffle 2 (bucket 4, unpriced), not here. `exhausting_deal_share`
    is that share; counting it in both bucket 2 and bucket 3 priced one
    card as being in the old pile and in the discard that replaces it;
  - a one-shot (Southeast Asia, `remove_after_event`) has no share at all.
    Its single life is spent this cycle and the card leaves the game. Held,
    it used to draw bucket 1 at 1.0 *and* bucket 3 at 0.96.

  It is still emitted only when the reshuffle precedes the horizon; that
  conditioning is the same "the reshuffle happens" prior as before, and
  game-precedes-the-reshuffle remains the gap note below.
- Bucket 4 (second reshuffle): named, never emitted, zero mass. Its
  recycled pile would include cards neither played by today nor dealt
  hence -- plays still to choose -- so its size is not derivable from
  today's public state at all; emitting a mass would be inventing one.
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
    cycle's independent chance, bucket 5 the final-scoring chance. A card
    that can only ever fire once is the exception and must sum to at most 1
    over its whole schedule -- there is no second payout to add.
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
    # How much of this card can still reach the recycled pile the reshuffle
    # builds -- the share bucket 3 is allowed to price. A card is in that
    # pile only if it is in the DISCARD when the reshuffle happens, which is
    # a question about where it is now.
    recycles = 1.0
    if state in ('hand', 'unseen'):
        # This cycle. Held: we play it this turn (the engine forbids holding
        # it past end of turn), so the whole mass sits in bucket 1. Unknown
        # holder: bucket 1 is P(the opponent holds it now) -- the holder must
        # play it this turn -- and bucket 2 is P(pile now) times P(a remaining
        # deal delivers it), from `cycle_deal_masses`, whose last deal is the
        # one that empties the pile and therefore delivers every card left in
        # it.
        if held:
            out.append(Opportunity(card, 1, 0, 0, 1.0))
        else:
            p_opp = pc.p_opponent_holds(obs, card)
            out.append(Opportunity(card, 1, 0, 0, p_opp))
            theirs, pile = pc.unseen_split(obs)
            pool = theirs + pile
            p_pile = (pile / pool) if pool > 0 else 0.0
            masses = pc.cycle_deal_masses(obs)
            survival = 1.0
            for mass in masses:
                survival *= 1.0 - mass
            deal_prob = 1.0 - survival
            if deal_prob > 0.0 and p_pile > 0.0:
                # Capped at the horizon: plays dated past game end contribute zero.
                out.append(Opportunity(card, 2, 0, min(reshuffle, horizon), p_pile * deal_prob))
            # The share dealt BY the exhausting deal is played on the
            # reshuffle turn, after the recycle has already been built, so
            # it goes to reshuffle 2 (bucket 4, unpriced) and not to bucket
            # 3. Counting it in both was pricing one card in the old pile as
            # if it were also in the discard that replaces it.
            recycles = 1.0 - p_pile * pc.exhausting_deal_share(obs)
    if once:
        # Southeast Asia is `remove_after_event`: its one life is spent the
        # moment it is played, this cycle, and nothing recycles it. Emitting
        # bucket 3 as well gave a held SEA card a lifetime occurrence of
        # 1.0 + 0.96, and the consumer sums those masses over every South
        # East Asian country.
        recycles = 0.0
    if state in ('hand', 'unseen', 'discard'):
        # Next cycle, if the reshuffle (and hence the game) gets there.
        # The card recycles with certainty (a scoring cannot go un-played
        # past the reshuffle), so the mass is P(it is dealt before game end
        # after the reshuffle), the post-reshuffle continuation of the same
        # deal walk bucket 2 uses this cycle -- times the share of it that
        # is in the discard to be recycled at all.
        if reshuffle <= horizon and recycles > 0.0:
            mass = 1.0
            for m in pc.post_reshuffle_deal_masses(obs):
                mass *= 1.0 - m
            out.append(Opportunity(card, 3, reshuffle, horizon, recycles * (1.0 - mass)))
    elif state == 'future':
        # Not yet in any deck: nothing recycles it. What it joins is the
        # pile its period's entry adds, dealt from its entry turn on --
        # same deal-walk shape, but its pile is future entries layered on
        # whatever the earlier cycles left, which the current walk does not
        # model. Flat 1.0 conditioned on entry within the horizon.
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
