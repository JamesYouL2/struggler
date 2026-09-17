"""The rebuild's schedule half: when each scoring can still pay, and with what mass.

`bots/strategic/schedule.py` turns the public deck state into explicit
opportunities -- (card, bucket, timing range, occurrence) -- one per scoring
per category. These tests pin the rules-grounded parts (held cards fire this
turn, spent one-shots and removed cards contribute zero, final scoring covers
the six regions and never Southeast Asia) and the documented assumptions
(deck-math holder masses, the unmodeled early-ending gap).
"""
from dataclasses import replace

from struggler.engine import Engine, Region, Side
from struggler.engine.core import SCORING_CARD_REGION
from struggler.bots.strategic import public_cards as pc
from struggler.bots.strategic import schedule as sch


def _obs(**kwargs):
    """A fresh deal's US observation with fields overridden: the deck inputs
    the schedule reads, without playing a game to arrange them."""
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    obs = engine.observe(Side.US)
    return replace(obs, **kwargs) if kwargs else obs


def _by_card(opps):
    grouped = {}
    for opp in opps:
        grouped.setdefault(opp.card, []).append(opp)
    return grouped


def test_full_schedule_names_every_card_in_order_no_bucket_four():
    grouped = _by_card(sch.full_schedule(_obs()))
    assert list(grouped) == [*list(SCORING_CARD_REGION), sch.SEA_SCORING]
    for card, opps in grouped.items():
        buckets = [o.bucket for o in opps]
        assert buckets == sorted(buckets), f"{card}: categories latest-last"
        assert sch.BUCKET_SECOND_RESHUFFLE not in buckets
        for opp in opps:
            assert 0.0 <= opp.occurrence <= 1.0
            assert 0 <= opp.turns_lo <= opp.turns_hi


def test_live_unknown_holder_uses_deck_math_this_cycle_and_returns_next():
    obs = _obs(discard_pile=(), removed_cards=())
    for card in SCORING_CARD_REGION:
        if pc.card_state(obs, card) != 'unseen':
            continue  # dealt into a hand; the held test below owns that case
        opps = _by_card(sch.opportunities(obs, card))[card]
        by_bucket = {o.bucket: o for o in opps}
        # Bucket 1 is P(the opponent holds it now): the holder must play a
        # scoring this turn, so this is deck calculation, not a half.
        assert by_bucket[1].occurrence == pc.p_opponent_holds(obs, card)
        # Bucket 2 is P(pile now) times P(a remaining full deal delivers it).
        theirs, pile = pc.unseen_split(obs)
        pool = theirs + pile
        masses = pc.cycle_deal_masses(obs)
        survival = 1.0
        for mass in masses:
            survival *= 1.0 - mass
        expected_b2 = (pile / pool) * (1.0 - survival)
        assert by_bucket[2].occurrence == expected_b2
        assert by_bucket[1].occurrence + by_bucket[2].occurrence <= 1.0 + 1e-12
        assert by_bucket[1].turns_lo == by_bucket[1].turns_hi == 0
        # Bucket 3 is the post-reshuffle walk times the share of the card
        # that is IN the recycled pile: what the exhausting deal delivers is
        # played after the recycle was built, so it is reshuffle 2's.
        survival = 1.0
        for m in pc.post_reshuffle_deal_masses(obs):
            survival *= 1.0 - m
        recycles = 1.0 - (pile / pool) * pc.exhausting_deal_share(obs)
        assert by_bucket[3].occurrence == recycles * (1.0 - survival)
        assert 0.0 < by_bucket[3].occurrence <= 1.0
        break
    else:
        raise AssertionError('expected at least one unseen scoring in a fresh deal')


def test_no_full_deals_left_omits_bucket_two():
    """Turn 10 has no future deal this cycle: bucket 1 stays, bucket 2 goes."""
    obs = _obs(turn=10)
    assert pc.cycle_deal_masses(obs) == ()
    for card in SCORING_CARD_REGION:
        if pc.card_state(obs, card) != 'unseen':
            continue
        buckets = {o.bucket for o in sch.opportunities(obs, card)}
        assert 2 not in buckets
        assert 1 in buckets
        break
    else:
        raise AssertionError('expected at least one unseen scoring at turn 10')


def test_held_card_fires_this_turn_only():
    obs = _obs(hand=('Africa_Scoring',))
    opps = _by_card(sch.opportunities(obs, 'Africa_Scoring'))['Africa_Scoring']
    by_bucket = {o.bucket: o for o in opps}
    # The engine forbids holding a scoring past end of turn, so the whole
    # this-cycle mass sits in bucket 1; nothing waits for later this cycle.
    assert by_bucket[1].occurrence == 1.0
    assert 2 not in by_bucket


def test_discarded_card_returns_only_next_cycle():
    obs = _obs(hand=(), discard_pile=('Africa_Scoring',))
    assert pc.card_state(obs, 'Africa_Scoring') == 'discard'
    opps = _by_card(sch.opportunities(obs, 'Africa_Scoring'))['Africa_Scoring']
    assert {o.bucket for o in opps} == {3, 5}


def test_future_card_names_its_entry_turn():
    obs = _obs(turn=1)
    card = next(c for c in SCORING_CARD_REGION if pc.card_state(obs, c) == 'future')
    opps = _by_card(sch.opportunities(obs, card))[card]
    by_bucket = {o.bucket: o for o in opps}
    assert 1 not in by_bucket and 2 not in by_bucket
    assert by_bucket[3].turns_lo == pc.entry_turn(pc.CARDS[card]) - 1


def test_removed_and_spent_cards_contribute_zero():
    obs = _obs(hand=(), removed_cards=('Asia_Scoring',), discard_pile=('Southeast_Asia_Scoring',))
    grouped = _by_card(sch.full_schedule(obs))
    assert 'Asia_Scoring' not in grouped  # removed: gone
    assert sch.SEA_SCORING not in grouped  # discarded: the one-shot never fires again


def test_final_scoring_covers_the_six_regions_never_the_southeast():
    obs = _obs()
    grouped = _by_card(sch.full_schedule(obs))
    for card in SCORING_CARD_REGION:
        finals = [o for o in grouped[card] if o.bucket == 5]
        assert len(finals) == 1
        assert finals[0].occurrence == pc.final_scoring_odds(obs)
        assert finals[0].turns_lo == finals[0].turns_hi == pc.turns_to_final_scoring(obs)
    if sch.SEA_SCORING in grouped:
        assert all(o.bucket != 5 for o in grouped[sch.SEA_SCORING])


def test_beyond_game_end_contributes_zero():
    """A pile that outlasts the game: no next-cycle opportunity, final scoring intact."""
    obs = _obs(turn=9, draw_pile_size=1000)
    horizon = pc.turns_to_final_scoring(obs)
    assert pc.turns_to_reshuffle(obs) > horizon
    for card in SCORING_CARD_REGION:
        if pc.card_state(obs, card) in ('hand', 'unseen', 'discard'):
            buckets = {o.bucket for o in sch.opportunities(obs, card)}
            assert 3 not in buckets
            assert 5 in buckets
    for opp in sch.full_schedule(obs):
        assert opp.turns_hi <= horizon


def test_recycled_pile_size_is_the_documented_accounting():
    """entered by the reshuffle turn, less removed, less the held estimate,
    less the spent one-shot -- the whole formula, pinned so it cannot drift
    silently."""
    obs = _obs(hand=(), removed_cards=(), discard_pile=('Asia_Scoring', 'Diplo_Aid'))
    reshuffle = pc.turns_to_reshuffle(obs)
    start = obs.turn + reshuffle
    early = len(pc.cards_entering(pc.CARDS, pc.Period.EARLY_WAR, True))
    entered = early + sum(n for t, n in pc.ENTERING.items() if t <= start)
    expected = max(0, entered - 2 * pc.hand_limit(start))
    assert pc.recycled_pile_size(obs, start) == expected


def test_post_reshuffle_walk_bounds_and_identity():
    """Each mass lies in (0, 1]; reshuffle 1 is `turns_to_reshuffle` turns
    ahead; () when the reshuffle is absent."""
    obs = _obs()
    reshuffle = pc.turns_to_reshuffle(obs)
    assert reshuffle <= pc.turns_to_final_scoring(obs)
    masses = pc.post_reshuffle_deal_masses(obs)
    assert masses
    for m in masses:
        assert 0.0 < m <= 1.0
    assert all(m < 1.0 for m in masses[:-1])  # a 1.0 ends the walk
    late = _obs(turn=9, draw_pile_size=1000)  # pile outlasts the game
    assert pc.turns_to_reshuffle(late) > pc.turns_to_final_scoring(late)
    assert pc.post_reshuffle_deal_masses(late) == ()
    assert pc.post_reshuffle_deal_masses(_obs(turn=10)) == ()


def test_bucket_three_is_the_dealt_before_game_end_mass():
    """Bucket 3 no longer assumes the whole recycled card is dealt: the
    same walk value for every recycling state, < the old flat 1.0 only
    while a deal can fall past the horizon."""
    obs = _obs(hand=(), discard_pile=('Africa_Scoring',))
    assert pc.card_state(obs, 'Africa_Scoring') == 'discard'
    survival = 1.0
    for m in pc.post_reshuffle_deal_masses(obs):
        survival *= 1.0 - m
    hmm = _obs(hand=('Africa_Scoring',))
    discard = [o.occurrence for o in sch.opportunities(obs, 'Africa_Scoring') if o.bucket == 3]
    held = [o.occurrence for o in sch.opportunities(hmm, 'Africa_Scoring') if o.bucket == 3]
    assert discard == held == [1.0 - survival]


def test_region_of_and_unknown_cards():
    assert sch.region_of('Africa_Scoring') is Region.AFRICA
    assert sch.region_of(sch.SEA_SCORING) is None
    obs = _obs()
    try:
        sch.opportunities(obs, 'The_China_Card')
    except ValueError:
        pass
    else:
        raise AssertionError('non-scoring cards must raise, not schedule')


# -- a one-shot pays once, and a card in the pile is dealt before it recycles --


def _sea_states():
    """Every deck state the Southeast Asia card can be in and still pay, as
    (label, observation). `remove_after_event` means a played one is
    `removed`, not `discard`, so those two are the ends of its life."""
    base = _obs(hand=(), discard_pile=(), removed_cards=())
    return [
        ('held', replace(base, turn=4, hand=(sch.SEA_SCORING,), draw_pile_size=10)),
        ('unseen, pile exhausts next deal', replace(base, turn=9, draw_pile_size=5)),
        ('unseen, mid cycle', replace(base, turn=5, draw_pile_size=40)),
        ('unseen, pile outlasts the game', replace(base, turn=9, draw_pile_size=500)),
        ('future era', replace(base, turn=1)),
    ]


def test_a_one_shot_never_accumulates_more_than_one_lifetime_play():
    """Southeast Asia Scoring is removed after its event, so the sum of its
    occurrence masses over the whole schedule is at most 1.

    It was not. `once` guarded the discarded card and final scoring but not
    the generic recycling block, so a held SEA card took bucket 1 at 1.0 and
    a bucket 3 of 0.96 on top -- and `_scoring_weight_uncached` sums exactly
    these masses for every South East Asian country. 99 of the corpus's
    records carried a SEA lifetime mass above one.
    """
    for label, obs in _sea_states():
        opps = sch.opportunities(obs, sch.SEA_SCORING)
        total = sum(o.occurrence for o in opps)
        assert total <= 1.0 + 1e-12, (label, [(o.bucket, o.occurrence) for o in opps])
        assert all(o.bucket != 5 for o in opps), (label, 'final scoring is by region')
    # ...and the states where it is gone contribute nothing at all.
    for gone in ('removed_cards', 'discard_pile'):
        obs = _obs(hand=(), **{gone: (sch.SEA_SCORING,)})
        assert sch.opportunities(obs, sch.SEA_SCORING) == ()


def test_a_held_one_shot_fires_this_turn_and_never_again():
    """The must-play rule fires it this turn; `remove_after_event` takes it
    out of the game. There is no later opportunity to name."""
    obs = replace(_obs(hand=(sch.SEA_SCORING,)), turn=4, draw_pile_size=10)
    assert [(o.bucket, o.occurrence) for o in sch.opportunities(obs, sch.SEA_SCORING)] \
        == [(1, 1.0)]
    # The region card in the same position DOES recycle: the one-shot rule is
    # about this card, not about holding a scoring.
    held_region = replace(_obs(hand=('Asia_Scoring',)), turn=4, draw_pile_size=10)
    assert {o.bucket for o in sch.opportunities(held_region, 'Asia_Scoring')} == {1, 3, 5}


def test_a_card_in_the_pile_is_certainly_dealt_by_the_deal_that_empties_it():
    """Turn 9, five cards left, a sixteen-card deal: every one of those five
    is dealt at turn 10 before the reshuffle can happen (`Engine._draw_card`
    empties the pile first). With the opponent holding nothing, the card is
    in the pile with certainty and so is its play.

    The walk used to drop that deal entirely for being partly recycled,
    which priced the certainty at 0.121 -- and then also charged it a
    bucket 3, as though the same card were in the old pile and in the
    discard that replaces it.
    """
    obs = replace(_obs(hand=(), discard_pile=(), removed_cards=()),
                  turn=9, draw_pile_size=5, opponent_hand_size=0)
    assert pc.card_state(obs, 'Asia_Scoring') == 'unseen'
    assert pc.turns_to_reshuffle(obs) == 1
    by_bucket = {o.bucket: o.occurrence for o in sch.opportunities(obs, 'Asia_Scoring')}
    assert by_bucket[1] == 0.0, 'the opponent holds nothing'
    assert by_bucket[2] == 1.0, 'the exhausting deal delivers it'
    assert 3 not in by_bucket, 'played on the reshuffle turn: reshuffle 2, not this one'
    assert by_bucket[5] == pc.final_scoring_odds(obs)


def test_a_discarded_card_still_takes_the_whole_recycled_walk():
    """The negative control on the conditioning above: it is about where the
    card is, not about suppressing bucket 3. A card already in the discard
    is entirely in the pile the reshuffle builds."""
    obs = replace(_obs(hand=(), removed_cards=()), turn=9,
                  draw_pile_size=5, discard_pile=('Asia_Scoring',))
    assert pc.card_state(obs, 'Asia_Scoring') == 'discard'
    survival = 1.0
    for m in pc.post_reshuffle_deal_masses(obs):
        survival *= 1.0 - m
    by_bucket = {o.bucket: o.occurrence for o in sch.opportunities(obs, 'Asia_Scoring')}
    assert by_bucket[3] == 1.0 - survival
    assert by_bucket[3] > 0.0
