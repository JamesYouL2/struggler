"""Hand survival, escape resources, and observed nuclear-loss regressions."""

import pytest

from conftest import bare_engine
from struggler.engine import Side, Action, DecisionKind as K
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.defcon import DefconPlanner, SurvivalPrior


def setup_hand(cards, side=Side.USSR, rounds=2, defcon=2, space_used=0, china=False):
    e = bare_engine()
    e.turn = 3
    e.phase = 'action_rounds'
    e.action_round = 7-rounds
    e._ars_played = 2*(e.action_round-1)  # keep the director consistent once a decision drains
    e.defcon = defcon
    e.hands[side.value] = list(cards)
    e.china_card_owner = side.value
    e.china_card_available = china
    e.space_race_attempts[side.value] = space_used
    e.board.influence['Cuba'][side.value] = 2
    # Direct card-mode decisions use the engine's real mode enumeration.
    return e


def planner(e, side=Side.USSR, **prior):
    # Exact-structure tests default the opponent hand-attack prior off; the
    # tests that exercise it set it explicitly.
    prior.setdefault('opponent_hand_attack', 0)
    obs = e.observe(side)
    bot = StrategicPlayer()
    return DefconPlanner(obs, bot.public_engine(obs), SurvivalPrior(**prior))


@pytest.mark.parametrize('side,card', [(Side.US,'We_Will_Bury_You'),
                                     (Side.USSR,'Duck_and_Cover'),
                                     (Side.USSR,'Soviets_Shoot_Down_KAL_007')])
def test_direct_reducers_are_spaced_when_possible(side, card):
    e = setup_hand([card], side, rounds=1)
    e.push_full_card_play(side, card)
    before = e.serialize()
    a = StrategicPlayer().choose_action(e.observe(side), [])
    assert a.payload['mode'] == 'space_race'
    assert e.serialize() == before
    e.step(a)
    assert e.defcon == 2 and card not in e.hands[side.value]


@pytest.mark.parametrize('side', [Side.US, Side.USSR])
@pytest.mark.parametrize('phasing_same', [True, False])
def test_hiltsw_never_loses_own_action_and_wins_borrowed_action(side, phasing_same):
    e = bare_engine()
    phasing = side if phasing_same else side.opponent
    with e._phasing_scope(phasing):
        e._fire_event(side, 'How_I_Learned_to_Stop_Worrying')
    a = StrategicPlayer().choose_action(e.observe(side), [])
    e.step(a)
    if phasing_same:
        assert e.defcon == 5 and e.winner is None
    else:
        assert e.defcon == 1 and e.winner is side


def test_space_attempt_is_reserved_for_hazardous_card():
    e = setup_hand(['Duck_and_Cover','CIA_Created','Fidel','Nasser'], rounds=3)
    p = planner(e)
    assert p.risk('Fidel','ops') == 0
    assert p.risk('Fidel','space_race') == 1
    e.push_full_card_play(Side.USSR, 'Fidel')
    assert StrategicPlayer().choose_action(e.observe(Side.USSR), []).payload['mode'] != 'space_race'


def test_china_card_provides_extra_safe_play_but_face_down_does_not():
    e = setup_hand(['CIA_Created','Fidel'], rounds=2, space_used=1)
    assert planner(e).risk() == 1
    e.china_card_available = True
    assert planner(e).risk() == 0
    e.china_card_owner = 'US'
    assert planner(e).risk() == 1


@pytest.mark.parametrize('card', ['How_I_Learned_to_Stop_Worrying','Salt_Negotiations','Nuclear_Test_Ban'])
def test_defcon_raiser_opens_escape_window(card):
    e = setup_hand(['Duck_and_Cover',card], space_used=1)
    p = planner(e, opponent_lowers_defcon=1)
    assert p.risk(card,'event') == 0
    assert p.risk(card,'ops') == 1
    e.push_full_card_play(Side.USSR, card)
    assert StrategicPlayer().choose_action(e.observe(Side.USSR), []).payload['mode'] == 'event'


def test_five_year_plan_discard_probability_and_scoring_escape():
    e = setup_hand(['Five_Year_Plan','Duck_and_Cover','Nasser'], rounds=1)
    p = planner(e)
    assert p.event_risk('Five_Year_Plan') == .5
    assert p.risk('Five_Year_Plan','ops') == .5
    e.hands['USSR'] = ['Five_Year_Plan','Asia_Scoring']
    assert planner(e).risk('Five_Year_Plan','ops') == 0
    e.hands['USSR'] = ['Five_Year_Plan','Duck_and_Cover']
    assert planner(e).risk('Five_Year_Plan','ops') == 1


def test_one_op_cia_is_not_spaceable_without_ops_bonus():
    e = setup_hand(['CIA_Created'], rounds=1)
    assert planner(e).risk() == 1
    e.turn_effects['brezhnev'] = True
    assert planner(e).risk() == 0


def test_no_coup_target_and_nuclear_subs_remove_cia_coup_route():
    e = setup_hand(['CIA_Created'], rounds=1)
    assert planner(e).event_risk('CIA_Created') == 1
    e.board.influence['Cuba']['USSR'] = 0
    assert planner(e).event_risk('CIA_Created') == 0
    e.board.influence['Cuba']['USSR'] = 2
    e.turn_effects['nuclear_subs'] = True
    assert planner(e).event_risk('CIA_Created') == 0


def test_un_intervention_spends_two_cards_without_firing_event():
    e = setup_hand(['Duck_and_Cover','UN_Intervention','CIA_Created'], rounds=2, space_used=1)
    assert planner(e).risk('Duck_and_Cover','un_intervention') == 1  # leaves only CIA for last round
    e.china_card_available = True
    assert planner(e).risk('Duck_and_Cover','un_intervention') == 0


def test_ask_not_discards_hazard_then_stops_and_has_uncertain_replacements():
    card = 'Ask_Not_What_Your_Country_Can_Do_For_You'
    e = setup_hand([card,'Lone_Gunman'], Side.US, rounds=2, space_used=1)
    p = planner(e, Side.US)
    assert 0 < p.risk(card,'event') < p.risk(card,'ops')
    e.hands['US'].remove(card)
    e._fire_event(Side.US, card)
    bot = StrategicPlayer()
    a = bot.choose_action(e.observe(Side.US), [])
    assert a.payload['choice'] == 'Lone_Gunman'
    # No hidden cards are supplied to the planner; only the real engine draws.
    e.hands['US'].append('Fidel')
    e.step(a)
    assert bot.choose_action(e.observe(Side.US), []).payload['choice'] == 'stop'


def test_aldrich_ames_removes_safe_play_to_preserve_us_suicide_card():
    e = setup_hand(['Lone_Gunman','Fidel'], Side.US, rounds=2, space_used=1)
    e._fire_event(Side.USSR, 'Aldrich_Ames_Remix')
    a = StrategicPlayer().choose_action(e.observe(Side.USSR), [])
    assert a.payload['choice'] == 'Fidel'
    e.step(a)
    assert e.hands['US'] == ['Lone_Gunman']


def test_search_budget_and_features_are_explicit():
    e = setup_hand(['Duck_and_Cover','CIA_Created','Fidel'], rounds=3)
    p = planner(e, max_states=1)
    f = p.features()
    assert 0 <= f['turn_loss_risk'] <= 1
    assert f['hazardous_cards'] == 2
    assert f['search_truncated']
    with pytest.raises(ValueError):
        SurvivalPrior(opponent_lowers_defcon=float('nan'))


# -- coups that create targets, and headlines that resolve second -------------


def test_battleground_coup_is_priced_by_the_hand_at_the_lower_defcon():
    # Seed 2402, T2 AR4: USSR couped Zaire from DEFCON 3 holding CIA Created
    # and Five Year Plan with no spare play; its new Zaire influence became
    # the CIA coup target and the turn was lost.
    e = setup_hand(['CIA_Created', 'Five_Year_Plan', 'US_Japan_Mutual_Defense_Pact'], rounds=3,
                   defcon=3, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0  # no DEFCON-2-legal target for the US yet
    e.board.influence['Zaire']['US'] = 2
    e.board.influence['Kenya']['US'] = 1
    e._push(Side.USSR, K.OPS_TYPE, (Action(K.OPS_TYPE, {'type': 'coup'}), Action(K.OPS_TYPE, {'type': 'influence'})),
            {'side': 'USSR', 'ops': 3, 'bonus': None, 'allow_coup': True})
    bot = StrategicPlayer(survival_prior=SurvivalPrior(opponent_hand_attack=0))
    obs = e.observe(Side.USSR)
    bot.choose_action(obs, [])
    assert bot.coup_survival_risk(obs, 'Kenya') == 0
    assert bot.coup_survival_risk(obs, 'Zaire') == pytest.approx(1.0)
    e._decision_stack.pop()
    e._push(Side.USSR, K.COUP_TARGET, tuple(Action(K.COUP_TARGET, {'country': c}) for c in ('Zaire', 'Kenya')),
            {'ops': 3, 'bonus': None})
    assert bot.choose_action(e.observe(Side.USSR), []).payload['country'] == 'Kenya'


def test_headline_pick_prices_the_opponent_headline_resolving_first():
    # Seed 2400, T10: the US headlined Lone Gunman at DEFCON 3; the USSR's
    # higher-Ops headline resolved first and DEFCON was 2 when it fired.
    hand = ['Lone_Gunman', 'Decolonization', 'Socialist_Governments', 'Nasser', 'Fidel',
            'Independent_Reds', 'Korean_War', 'The_Voice_Of_America', 'An_Evil_Empire']
    e = setup_hand(hand, Side.US, rounds=7, defcon=3)
    e.board.influence['Nigeria']['US'] = 2
    e.phase = 'headline'
    e._push_headline(Side.US)
    p = planner(e, Side.US, opponent_lowers_defcon=1)
    assert p.risk('Lone_Gunman', 'event') == 0  # naive: fires at DEFCON 3
    assert p.headline_pick_risk('Lone_Gunman') > 0.8  # a 1-Ops card almost always resolves second
    assert p.headline_pick_risk('Socialist_Governments') == 0
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['card'] != 'Lone_Gunman'


def test_pending_own_headline_is_a_forced_event_before_the_action_rounds():
    e = setup_hand(['Decolonization', 'Socialist_Governments'], Side.US, rounds=7, defcon=3)
    e.board.influence['Nigeria']['US'] = 2
    e.phase = 'headline'
    e._headline_pending = [['US', 'Lone_Gunman']]
    obs = e.observe(Side.US)
    assert obs.headline_pending == (('US', 'Lone_Gunman'),)
    p = planner(e, Side.US)
    assert p.pending_headline == 'Lone_Gunman' and p.rounds == 6  # turn 3: six rounds, no headline card to count
    assert p.risk() == 0
    e.defcon = 2
    assert planner(e, Side.US).risk() == 1
    # Couping a battleground to DEFCON 2 with that headline still to come is fatal.
    e.defcon = 3
    e.board.influence['Zaire']['USSR'] = 2
    e._push(Side.US, K.COUP_TARGET, (Action(K.COUP_TARGET, {'country': 'Zaire'}),), {'ops': 2, 'bonus': None})
    bot = StrategicPlayer()
    bot.choose_action(e.observe(Side.US), [])
    assert bot.coup_survival_risk(e.observe(Side.US), 'Zaire') == 1


# -- discard events, traps, and opponent hand attacks -------------------------


def test_blockade_self_discard_is_refused_when_it_strands_a_suicide_card():
    # Seed 2401, T9 AR5 (logs/game-check/2401-strategic-strategic.debug.log):
    # the US paid Socialist Governments to Blockade and was left holding
    # Lone Gunman for the last round.
    hand = ['Allende', 'Blockade', 'Lone_Gunman', 'Socialist_Governments']
    e = setup_hand(hand, Side.US, rounds=3, space_used=1)
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.risk() == 0 and p.risk('Blockade', 'ops') == 0
    e.hands['US'].remove('Blockade')
    e._fire_event(Side.US, 'Blockade')
    decision = e.observe(Side.US).pending_decision
    assert decision.kind is K.EVENT_CHOICE and decision.context['event'] == 'Blockade'
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.mid_play and p.rounds == 2
    assert p.discard_risk('Socialist_Governments') == 1
    assert p.discard_risk(None) == 0
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['choice'] == 'refuse'


def test_blockade_discard_is_an_exit_for_a_three_ops_hazard():
    e = setup_hand(['We_Will_Bury_You', 'Blockade', 'Fidel'], Side.US, rounds=2, space_used=1)
    p = planner(e, Side.US, opponent_hand_attack=0)
    assert p.risk('We_Will_Bury_You', 'ops') == 1
    assert p.risk('Blockade', 'ops') == 0
    assert p.risk('Fidel', 'ops') == 0  # Blockade can still pay WWBY away next round
    e.hands['US'].remove('Blockade')
    e._fire_event(Side.US, 'Blockade')
    assert StrategicPlayer().choose_action(e.observe(Side.US), []).payload['choice'] == 'We_Will_Bury_You'


def test_self_bear_trap_disposes_of_us_events_without_firing_them():
    hand = ['Bear_Trap', 'Grain_Sales_to_Soviets', 'CIA_Created', 'The_Voice_Of_America']
    e = setup_hand(hand, rounds=3, space_used=1)
    p = planner(e, opponent_hand_attack=0)
    assert p.risk('Grain_Sales_to_Soviets', 'ops') == 1
    assert p.risk('CIA_Created', 'ops') == 1
    assert p.risk('Bear_Trap', 'ops') == 0
    e.game_effects['bear_trap'] = True
    p = planner(e, opponent_hand_attack=0)
    assert p.trapped and p.risk() == 0
    assert p.features()['trapped'] == 1


def test_trap_step_pays_the_card_that_keeps_the_hand_safest():
    # Trapped USSR must pay a 2+ Ops card: paying Voice of America keeps a
    # safe 2-Ops card (Fidel) for the round after an escape; paying Fidel
    # leaves Grain Sales as the only later play if the die frees us.
    e = setup_hand(['Fidel', 'Grain_Sales_to_Soviets', 'CIA_Created'], rounds=2, space_used=1)
    e.game_effects['bear_trap'] = True
    e._push_trap_step(Side.USSR, 'bear_trap')
    p = planner(e, opponent_hand_attack=0)
    assert p.mid_play and p.rounds == 1
    assert p.discard_risk('Grain_Sales_to_Soviets', escape_roll=True) == 0
    assert p.discard_risk('Fidel', escape_roll=True) == pytest.approx(4/6)
    a = StrategicPlayer().choose_action(e.observe(Side.USSR), [])
    assert a.payload['card'] == 'Grain_Sales_to_Soviets'


def test_opponent_hand_attack_prior_prices_a_missing_spare_card():
    e = setup_hand(['CIA_Created', 'Fidel', 'Nasser'], rounds=2, space_used=1)
    assert planner(e, opponent_hand_attack=0).risk() == 0
    assert planner(e, opponent_hand_attack=.5).risk() == pytest.approx(.5)
    assert planner(e, opponent_hand_attack=1).risk() == 1
    # One spare safe card absorbs the single attack between two rounds...
    e.hands['USSR'].append('Decolonization')
    assert planner(e, opponent_hand_attack=1).risk() == 0
    # ...but three rounds leave room for two attacks: three plays plus two
    # stolen cards need five safe cards alongside the held hazard.
    e.action_round = 7-3
    assert planner(e, opponent_hand_attack=1).risk() == 1
    e.hands['USSR'].append('Warsaw_Pact_Formed')
    assert planner(e, opponent_hand_attack=1).risk() == 1
    e.hands['USSR'].append('Arab_Israeli_War')
    assert planner(e, opponent_hand_attack=1).risk() == 0


def test_five_year_plan_and_missile_envy_chains_only_matter_at_defcon_2():
    from struggler.engine import Side
    for defcon, expected in ((5, 0.), (2, SurvivalPrior().unknown_chain_loss)):
        e = bare_engine()
        e.phase = 'action_rounds'
        e.defcon = defcon
        e.hands['US'] = ['Five_Year_Plan', 'Missile_Envy']
        e.hands['USSR'] = ['Nasser']
        e._push_action_round_play(Side.US)
        planner = DefconPlanner(e.observe(Side.US), e, SurvivalPrior(opponent_hand_attack=0))
        assert planner.event_risk('Five_Year_Plan') == expected
        assert planner.event_risk('Missile_Envy') == expected


def test_the_defcon_drop_prior_matches_what_was_measured():
    """`opponent_lowers_defcon` shipped at 0.75 with no rationale, applied
    once per remaining round. The event is labelled and counted in
    `models/opponent-model-v1.json.report.json` -- "did the opponent lower
    DEFCON between our pick and our next" -- at a base rate near 0.10. The
    prior is held a little above that (humans Coup more freely than these
    bots, and a survival prior should err toward caution) and far below the
    old guess."""
    import json
    from pathlib import Path
    from struggler.bots.strategic.defcon import SurvivalPrior

    report = json.loads(Path('models/opponent-model-v1.json.report.json').read_text())
    measured = report['test']['defcon_drop']['rate']
    prior = SurvivalPrior().opponent_lowers_defcon
    assert measured < prior <= 4 * measured, (
        f'prior {prior} should sit just above the measured rate {measured:.3f}')
    assert prior < 0.5, 'the old 0.75 expected DEFCON to fall almost every round'


def test_the_hand_attack_prior_is_not_fitted_to_bot_games():
    """Its measured base rate (0.003-0.006) is an artefact of the opponent
    being a bot: these bots play the attack cards for Ops or Space, while
    strong humans always event them. Fitting to that would tune the planner
    to an opponent it should not expect."""
    import json
    from pathlib import Path
    from struggler.bots.strategic.defcon import SurvivalPrior

    report = json.loads(Path('models/opponent-model-v1.json.report.json').read_text())
    measured = report['test']['hand_attack']['rate']
    assert SurvivalPrior().opponent_hand_attack > 10 * measured


# -- the 2026-09-18 hand-safety audit (docs/notes/codex/2026-09-18-hand-planner-audit.md) --


def ranked_with_risk(e, side=Side.USSR, **prior):
    prior.setdefault('opponent_hand_attack', 0)
    bot = StrategicPlayer(survival_prior=SurvivalPrior(**prior))
    obs = e.observe(side)
    return bot, obs, [(key, action, bot.action_risk(obs, action)) for key, action in bot.rank_actions(obs)]


@pytest.mark.parametrize('spare', ['space', 'un'])
def test_certain_defeat_in_the_key_means_certain_defeat_in_the_planner(spare):
    # F1: a card whose Ops play fires a lethal event, but which has a legal
    # mode that does not fire it, was keyed -1 while the planner said 0.
    e = setup_hand(['Duck_and_Cover', 'Fidel'] + (['UN_Intervention'] if spare == 'un' else []),
                   rounds=2, defcon=2, space_used=1 if spare == 'un' else 0)
    e._push_action_round_play(Side.USSR)
    _, _, ranked = ranked_with_risk(e)
    assert {a.payload['card'] for _, a, _ in ranked} >= {'Duck_and_Cover', 'Fidel'}
    for key, action, (_, risk) in ranked:
        assert (key[0] < 0) == (risk >= 1), (action.payload, key, risk)


def test_a_spaceable_suicide_card_still_ranks_as_defeat_once_the_space_slot_is_used():
    # The control for F1: without an attempt, Duck and Cover's only plays fire it.
    e = setup_hand(['Duck_and_Cover', 'Fidel'], rounds=2, defcon=2, space_used=1)
    e._push_action_round_play(Side.USSR)
    _, _, ranked = ranked_with_risk(e)
    key = next(k for k, a, _ in ranked if a.payload['card'] == 'Duck_and_Cover')
    assert key[0] < 0


@pytest.mark.parametrize('side,card,payer,country', [
    (Side.USSR, 'CIA_Created', Side.US, 'West_Germany'),
    (Side.USSR, 'CIA_Created', Side.US, 'Turkey'),
    (Side.US, 'Lone_Gunman', Side.USSR, 'Cuba'),
])
@pytest.mark.parametrize('can_pay', [True, False])
def test_cuban_missile_crisis_protects_only_while_its_target_cannot_cancel_it(side, card, payer, country, can_pay):
    # F2: the engine offers the CMC side a defuse at every atomic boundary,
    # our own borrowed-Coup action included; paying 2 lifts the ban.
    e = setup_hand([card, 'Decolonization' if side is Side.USSR else 'Marshall_Plan'],
                   side=side, rounds=1, defcon=2, space_used=1)
    if side is Side.US:
        e.board.influence['Panama']['US'] = 1  # a battleground for the USSR to Coup
    e.turn_effects['cuban_missile_crisis'] = payer.value
    for c in ('Cuba', 'West_Germany', 'Turkey'):
        e.board.influence[c][payer.value] = 0
    e.board.influence[country][payer.value] = 2 if can_pay else 1
    assert planner(e, side).event_risk(card) == (1. if can_pay else 0.)
    assert e.cmc_defuse_countries(payer) == ([country] if can_pay else [])


def test_cancellable_cuban_missile_crisis_does_not_tempt_the_bot_into_cia():
    # F2 through the real decisions: with one round left, CIA Created must be held.
    e = setup_hand(['CIA_Created', 'Fidel'], rounds=1, defcon=2, space_used=1)
    e.turn_effects['cuban_missile_crisis'] = 'US'
    e.board.influence['West_Germany']['US'] = 4
    e._push_action_round_play(Side.USSR)
    assert StrategicPlayer().choose_action(e.observe(Side.USSR), []).payload['card'] == 'Fidel'


def test_an_event_that_creates_the_first_coup_target_is_priced_on_the_board_it_leaves():
    # F3: Fidel's event puts 3 USSR in Cuba, the first battleground the US
    # can Coup with CIA Created. The frozen board said zero; the play lost.
    e = setup_hand(['CIA_Created', 'Fidel'], rounds=2, defcon=2, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0
    e._push_action_round_play(Side.USSR)
    e.step(Action(K.ACTION_ROUND_PLAY, {'card': 'Fidel'}))
    _, _, ranked = ranked_with_risk(e)
    risks = {a.payload['mode']: r for _, a, (_, r) in ranked}
    assert risks['event'] == 1 and risks['ops'] == 0
    assert ranked[0][1].payload['mode'] != 'event'
    # The reverse order is safe, so this is not a ban on Fidel: with CIA
    # Created gone, the same event is priced at zero.
    e = setup_hand(['Fidel', 'Nasser'], rounds=2, defcon=2, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0
    e.push_full_card_play(Side.USSR, 'Fidel')
    _, _, ranked = ranked_with_risk(e)
    assert {a.payload['mode']: r for _, a, (_, r) in ranked}['event'] == 0


def test_a_placement_that_creates_the_first_coup_target_is_priced():
    # F3 for Ops: placing into an empty battleground is the same new target.
    e = setup_hand(['CIA_Created', 'Fidel'], rounds=2, defcon=2, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0
    e.hands['USSR'].remove('Fidel')  # Fidel is being played for its Ops
    e._push(Side.USSR, K.PLACE_INFLUENCE,
            tuple(Action(K.PLACE_INFLUENCE, {'country': c}) for c in ('Cuba', 'Afghanistan')),
            {'ops_remaining': 1, 'phasing_player': 'USSR'})
    _, _, ranked = ranked_with_risk(e)
    risks = {a.payload['country']: r for _, a, (_, r) in ranked}
    assert risks == {'Cuba': 1, 'Afghanistan': 0}
    assert ranked[0][1].payload['country'] == 'Afghanistan'


# -- the 2026-09-20 technical-correctness audit (docs/notes/codex/2026-09-20-technical-correctness.md) --


def cleared_board_setup(cards, side, rounds=1, defcon=2, space_used=1):
    """`setup_hand` with every country emptied first, so a test states all
    the influence it means to price: `setup_hand`'s own Cuba point is the
    unrestricted borrowed-Coup target the F1 defect hid behind."""
    e = setup_hand(cards, side=side, rounds=rounds, defcon=defcon, space_used=space_used)
    for country in e.board.influence:
        e.board.influence[country] = {'US': 0, 'USSR': 0}
    return e


@pytest.mark.parametrize('card,side,target,access', [
    ('Ortega_Elected_in_Nicaragua', Side.US, 'Cuba', 'Nicaragua'),
    ('Tear_Down_This_Wall', Side.USSR, 'Italy', 'Austria'),
])
def test_a_restricted_borrowed_coup_is_latent_where_only_geography_withholds_it(card, side, target, access):
    # F1: `latent_hazards` asked the unrestricted Coup question, so a card
    # held safe by its own geography read as not latent whenever the
    # opponent had any legal unrestricted battleground Coup elsewhere -- and
    # the placement planner switched itself off exactly when the next
    # placement could create the restricted target.
    e = cleared_board_setup([card], side)
    e.board.influence['Angola'][side.value] = 1  # a legal UNRESTRICTED battleground Coup at DEFCON 2
    assert target in e.board.neighbors(access)
    p = planner(e, side)
    assert p.event_risk(card) == 0  # safe now: the free Coup cannot reach its own geography
    assert p.latent_hazards(p.hand) == [card]
    e.board.influence[target][side.value] = 1  # the first eligible battleground appears in it
    assert planner(e, side).event_risk(card) == 1


@pytest.mark.parametrize('card,side,target,access,ops_card', [
    ('Ortega_Elected_in_Nicaragua', Side.US, 'Cuba', 'Nicaragua', 'NATO'),
    ('Tear_Down_This_Wall', Side.USSR, 'Italy', 'Austria', 'Nasser'),
])
def test_a_placement_that_creates_a_restricted_borrowed_coups_first_target_is_priced(card, side, target, access, ops_card):
    # F1 through the real decisions: the ranking keeps its placement
    # planner (the defect switched it off), the placement inside the card's
    # geography is priced as the loss it creates, and the control outside
    # the geography is not -- the unrestricted Angola target makes both
    # placements legal Coup targets for a NORMAL coup, but only the
    # in-geography one for the card's free Coup.
    e = cleared_board_setup([card, ops_card], side, rounds=2)
    e.board.influence['Angola'][side.value] = 1  # the unrelated unrestricted target
    e.board.influence[access][side.value] = 1    # our access for the placement
    assert target in e.board.neighbors(access)
    e.board.influence['Zaire'][side.value] = 0
    e.hands[side.value].remove(ops_card)  # the Ops card is being played
    e._push(side, K.PLACE_INFLUENCE,
            tuple(Action(K.PLACE_INFLUENCE, {'country': c}) for c in (target, 'Zaire')),
            {'ops_remaining': 1, 'phasing_player': side.value})
    bot, _, ranked = ranked_with_risk(e, side)
    assert bot._planner is not None  # the restricted card is latent, so the planner stays
    risks = {a.payload['country']: r for _, a, (_, r) in ranked}
    assert risks == {target: 1, 'Zaire': 0}
    assert ranked[0][1].payload['country'] == 'Zaire'


def test_an_event_that_fills_a_restricted_coups_geography_is_priced_on_the_board_it_leaves():
    # F1 through `_mode_risk`'s resimulation guard: Tear Down This Wall sits
    # latent in the remaining hand (its Europe is empty), and John Paul II's
    # event puts the first US point in a European battleground. The frozen
    # board prices the play at zero; the board it leaves is the loss.
    e = cleared_board_setup(['Tear_Down_This_Wall', 'John_Paul_II_Elected_Pope'], Side.USSR,
                            rounds=2, defcon=2)
    e.board.influence['Angola']['USSR'] = 1  # a legal unrestricted target, the F1 trap
    # John Paul II removes 2 USSR from Poland and adds 1 US: leave 3, so one
    # USSR point survives to be the free Coup's removable target.
    e.board.influence['Poland']['USSR'] = 3
    e._push_action_round_play(Side.USSR)
    e.step(Action(K.ACTION_ROUND_PLAY, {'card': 'John_Paul_II_Elected_Pope'}))
    _, _, ranked = ranked_with_risk(e)
    risks = {a.payload['mode']: r for _, a, (_, r) in ranked}
    assert risks == {'ops': 1, 'event': 1}


@pytest.mark.parametrize('latent', [True, False])
def test_a_resolved_event_is_applied_once_in_the_replanned_hand(latent):
    # F2: the post-event re-plan transitioned the play a second time, so
    # Duck and Cover resolved at DEFCON 3 was priced as a reducer starting
    # at 2 -- a certain turn loss -- and both modes collapsed onto the
    # game's priced score. The control keeps CIA Created non-latent (Cuba
    # manned), where no re-plan runs and the answer was already (0, 0).
    e = setup_hand(['Duck_and_Cover', 'CIA_Created'], rounds=1, defcon=3, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0 if latent else 2
    e._push_action_round_play(Side.USSR)
    e.step(Action(K.ACTION_ROUND_PLAY, {'card': 'Duck_and_Cover'}))
    bot, obs, ranked = ranked_with_risk(e, opponent_lowers_defcon=0)
    assert {a.payload['mode']: ir for _, a, ir in ranked} == {'event': (0, 0), 'ops': (0, 0)}
    keys = {a.payload['mode']: key for key, a, _ in ranked}
    assert keys['event'][2] != keys['ops'][2]
    assert all(key[2] != pytest.approx(-bot.game_value(obs)) for key in keys.values())
    # The real engine's outcome, taken independently of the planner's price.
    e.step(next(a for _, a, _ in ranked if a.payload['mode'] == 'event'))
    assert e.defcon == 2 and not e.is_terminal


def test_the_replanned_hand_counts_the_events_trap_once():
    # F2's stateful case: Bear Trap's event IS trap state. The continuation
    # must start from the effects already resolved and count each once --
    # with the trap in force a trapped round disposes of Grain Sales without
    # firing its event and the hand survives, where a re-plan that lost the
    # effect must play it at DEFCON 2 and reads as certain loss.
    e = cleared_board_setup(['Bear_Trap', 'Grain_Sales_to_Soviets', 'Tear_Down_This_Wall'],
                            Side.USSR, rounds=3, defcon=3)
    # Cuba gives Grain Sales a target and makes it hazardous at 2, while
    # Europe stays empty -- Tear Down This Wall is latent on want of
    # geography, which is what runs the re-plan at all.
    e.board.influence['Cuba']['USSR'] = 2
    e._push_action_round_play(Side.USSR)
    e.step(Action(K.ACTION_ROUND_PLAY, {'card': 'Bear_Trap'}))
    bot, obs, ranked = ranked_with_risk(e, opponent_lowers_defcon=1)
    assert bot._after_event(obs, 'Bear_Trap').game_effects == {'bear_trap': True}
    assert {a.payload['mode']: ir for _, a, ir in ranked} == {'event': (0, 0), 'ops': (0, 0)}


@pytest.mark.parametrize('opponent_box,expected', [(0, 1/3), (2, 1.)])
def test_reaching_box_two_in_the_search_grants_the_second_attempt(opponent_box, expected):
    # F4: success (4 in 6) reaches box 2 first and allows spacing KAL too;
    # failure, or an opponent already there, leaves one disposal for two hazards.
    e = setup_hand(['Duck_and_Cover', 'Soviets_Shoot_Down_KAL_007', 'CIA_Created'], rounds=2, defcon=2)
    e.space_race['USSR'], e.space_race['US'] = 1, opponent_box
    assert planner(e, opponent_lowers_defcon=0).risk('Duck_and_Cover', 'space_race') == pytest.approx(expected)


@pytest.mark.parametrize('root,opponent', [(r, o) for r in range(4) for o in range(4)])
def test_the_simulated_attempt_allowance_matches_the_engine(root, opponent):
    # Derived, so proved equal: advance the engine's marker one box at a
    # time and ask it, against the planner's answer for that box. The box-2
    # holder follows from the markers: whoever alone has reached it.
    e = setup_hand(['Fidel'], rounds=2, defcon=3)
    e.space_race['USSR'], e.space_race['US'] = root, opponent
    if (root >= 2) != (opponent >= 2):
        e.game_effects['space_race_double_attempt_holder'] = 'USSR' if root >= 2 else 'US'
    p = planner(e)
    for pos in range(root, 5):
        assert p.attempts_allowed(pos) == e._space_attempts_allowed(Side.USSR), (pos, e.game_effects)
        e.advance_space_race_box(Side.USSR)


def test_the_choice_log_reports_the_planner_risk_not_the_key(caplog):
    # F5: the key's middle slot is 0 for every priced kind, and the log read
    # it. Nuclear Subs leaves the US no DEFCON-lowering Coup, so the guard
    # is off and the 0.15 prior is genuinely accepted for Decolonization.
    import logging
    e = setup_hand(['Duck_and_Cover', 'Decolonization'], rounds=2, defcon=3, space_used=1)
    e.turn_effects['nuclear_subs'] = True
    e._push_action_round_play(Side.USSR)
    bot = StrategicPlayer(survival_prior=SurvivalPrior(opponent_hand_attack=0))
    obs = e.observe(Side.USSR)
    with caplog.at_level(logging.INFO, logger='struggler.bots.strategic'):
        choice = bot.choose_action(obs, [])
    risk = bot.action_risk(obs, choice)[1]
    assert choice.payload['card'] == 'Decolonization' and risk == pytest.approx(.15)
    assert 'accepting turn-loss risk 0.150' in caplog.text


# -- the last safe disposal window (step 2 of the 2026-09-18 plan) --------------


def closing_window(cards, side=Side.USSR, **kw):
    e = setup_hand(cards, side=side, rounds=2, defcon=3, space_used=1, **kw)
    for c, v in [('Italy', 3), ('France', 3), ('West_Germany', 4), ('Egypt', 2)]:
        e.board.influence[c]['US'] = v
    e._push_action_round_play(side)
    return e


def test_cia_created_is_played_while_defcon_three_still_makes_it_safe():
    # The audit's F5 fixture: holding CIA past this round, a legal US Coup
    # in Cuba drops DEFCON and the held CIA becomes a forced loss.
    e = closing_window(['CIA_Created', 'Decolonization'])
    bot, obs, ranked = ranked_with_risk(e)
    assert ranked[0][1].payload['card'] == 'CIA_Created'
    assert bot.cornered_after_drop(obs, next(a for _, a, _ in ranked if a.payload['card'] == 'Decolonization'))


def test_a_spare_card_to_hold_keeps_the_exit_open():
    # The control: a third card means CIA Created can be held after the
    # drop, so Decolonization is not cornered and wins on the board.
    e = closing_window(['CIA_Created', 'Decolonization', 'Fidel'])
    bot, obs, ranked = ranked_with_risk(e)
    assert not any(bot.cornered_after_drop(obs, a) for _, a, _ in ranked)
    assert ranked[0][1].payload['card'] != 'CIA_Created'


def test_lone_gunman_is_the_mirror_for_the_us():
    e = setup_hand(['Lone_Gunman', 'Marshall_Plan'], side=Side.US, rounds=2, defcon=3, space_used=1)
    e._push_action_round_play(Side.US)
    _, _, ranked = ranked_with_risk(e, Side.US)
    assert ranked[0][1].payload['card'] == 'Lone_Gunman'


def test_no_legal_drop_leaves_the_prior_in_charge():
    # Nuclear Subs: US battleground Coups do not lower DEFCON, so there is no
    # legal drop to guard against; Duck and Cover's risk stays the prior.
    e = setup_hand(['Duck_and_Cover', 'Decolonization'], rounds=2, defcon=3, space_used=1)
    e.turn_effects['nuclear_subs'] = True
    e._push_action_round_play(Side.USSR)
    bot, obs, ranked = ranked_with_risk(e)
    assert not any(bot.cornered_after_drop(obs, a) for _, a, _ in ranked)


@pytest.mark.parametrize('guard', [0.0, 0.3, 1.0])
def test_the_guard_charges_a_cornered_play_its_drop_probability_at_the_whole_game(guard):
    # `last_window_guard` is P(the opponent takes the legal drop). A play
    # that is certain loss after it carries at least that residual, priced
    # at game_value; 0 switches the guard off entirely.
    from struggler.bots.strategic import StrategicWeights
    e = closing_window(['CIA_Created', 'Decolonization'])
    bot = StrategicPlayer(StrategicWeights(last_window_guard=guard),
                          survival_prior=SurvivalPrior(opponent_hand_attack=0))
    obs = e.observe(Side.USSR)
    ranked = bot.rank_actions(obs)
    decol = next(a for _, a in ranked if a.payload['card'] == 'Decolonization')
    key = next(k for k, a in ranked if a is decol)
    assert bot.cornered_after_drop(obs, decol) == (guard > 0)
    raw, total = bot.score(obs, decol), bot.action_risk(obs, decol)[1]
    residual = max(total, guard)
    assert key[2] == pytest.approx((1 - residual) * raw - residual * bot.game_value(obs))
    if guard == 0:
        # The property is that the GUARD demotes a cornered play, so it is
        # tested as a comparison against the guard at full strength -- not as
        # "the cornered play is top", which was true only while the other
        # card in hand happened to be worth less. The 2026-09-20 turn curve
        # (`vp_swing` 3.0) re-priced CIA Created above it and broke that
        # reading without touching the guard.
        strict = StrategicPlayer(StrategicWeights(last_window_guard=1.0),
                                 survival_prior=SurvivalPrior(opponent_hand_attack=0))
        other = closing_window(['CIA_Created', 'Decolonization'])
        strict_ranked = strict.rank_actions(other.observe(Side.USSR))
        strict_key = next(k for k, a in strict_ranked if a.payload['card'] == 'Decolonization')
        # The play is worth strictly more with the guard off than with it at
        # full strength -- by the whole game, since the guard prices a certain
        # drop at `game_value`. Rank position would not see it here: CIA
        # Created outranks this play either way.
        assert key[2] > strict_key[2]
        assert strict_key[2] == pytest.approx(-bot.game_value(obs), rel=1e-6)
