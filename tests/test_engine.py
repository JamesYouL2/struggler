

def test_setup_bonus_places_two_more_us_points_where_the_us_already_is():
    from struggler.engine import Action, DecisionKind, Engine, Side
    engine = Engine.new_game(seed=5, setup_bonus=True)
    for _ in range(6 + 7):  # the standard Eastern/Western Europe placements
        d = engine.pending_decision
        assert d.context.get('setup') and d.context['subregion'] is not None
        engine.step(d.options[0])
    d = engine.pending_decision
    assert d.actor is Side.US
    assert {k: d.context[k] for k in ('setup', 'side', 'subregion', 'remaining')} == \
        {'setup': True, 'side': 'US', 'subregion': None, 'remaining': 2}
    offered = {a.payload['country'] for a in d.options}
    assert offered == {c for c in engine.board.countries if engine.board.influence[c]['US'] > 0}
    assert 'Iran' in offered and 'Poland' not in offered
    engine.step(Action(DecisionKind.PLACE_INFLUENCE, {'country': 'Iran'}))
    assert engine.pending_decision.context['remaining'] == 1
    engine.step(Action(DecisionKind.PLACE_INFLUENCE, {'country': 'UK'}))
    assert engine.board.influence['Iran']['US'] == 2 and engine.board.influence['UK']['US'] == 6
    assert engine.phase == 'headline'
    assert engine.serialize()['setup_bonus'] is True
    assert Engine.deserialize(engine.serialize()).setup_bonus is True
    # Without the handicap the game goes straight to the headline, and the
    # recorded state carries no new key.
    plain = Engine.new_game(seed=5)
    for _ in range(13):
        plain.step(plain.pending_decision.options[0])
    assert plain.phase == 'headline' and 'setup_bonus' not in plain.serialize()


def _europe_control_board(seed=1):
    """The US holding every Europe Battleground and more countries than the
    USSR, but far from holding all of Europe."""
    from struggler.engine import Engine, Region, ScoringTier, Side
    engine = Engine(seed=seed)
    board = engine.board
    europe = board.countries_in(Region.EUROPE)
    battlegrounds = [c for c in europe if board.countries[c].battleground]
    others = [c for c in europe if not board.countries[c].battleground]
    for cid in battlegrounds + others[:2]:
        board.influence[cid]["US"] = board.countries[cid].stability
    assert any(board.control(c) is None for c in europe)
    assert board.region_tier(Side.US, Region.EUROPE) is ScoringTier.CONTROL
    return engine


def test_scoring_europe_at_control_wins_outright_without_all_of_europe():
    """"If either side Controls Europe, that side wins when the Europe Scoring
    card is played." Control is the scoring tier -- all Battlegrounds plus
    more countries -- and the engine used to demand control of every country
    in the region, scoring this position as Domination for 10 VP instead."""
    from struggler.engine import Region, Side
    engine = _europe_control_board()
    engine._resolve_scoring_card("Europe_Scoring")
    assert engine.is_terminal
    assert engine.winner is Side.US
    assert engine.game_over_reason == "europe_control"
    assert engine.vp == 0, "an automatic victory awards no VP"


def test_final_scoring_gives_europe_control_precedence_over_vp_elsewhere():
    """Final Scoring scores every region "as if its regional scoring card had
    just been played", so Europe Control wins there too, ahead of whatever
    another region would have scored."""
    from struggler.engine import Region, Side
    engine = _europe_control_board()
    engine.turn = 10
    # A South American landslide for the USSR, which would otherwise be scored.
    for cid in engine.board.countries_in(Region.SOUTH_AMERICA):
        engine.board.influence[cid]["USSR"] = engine.board.countries[cid].stability
    engine._finish_game()
    assert engine.is_terminal
    assert engine.winner is Side.US
    assert engine.game_over_reason == "europe_control"


def test_final_scoring_is_recorded_even_when_it_ends_on_another_reason():
    """How often a game goes the distance is a calibration input (it sets
    `public_cards.FINAL_SCORING_ODDS`), and it was read off the end reason.
    But Final Scoring can end the game at 'vp' or 'europe_control' partway
    through the regions, or leave a draw with no reason at all, and each of
    those is a game that reached Final Scoring and was not counted."""
    from struggler.engine import Engine, Region, Side

    engine = Engine(seed=1)
    engine.turn = 10
    engine.vp = 19  # one region away from the 20 VP auto-victory
    for cid, info in engine.board.countries.items():
        if info.region is not Region.EUROPE:
            engine.board.influence[cid]["US"] = info.stability
    engine._finish_game()
    assert engine.winner is Side.US
    assert engine.game_over_reason == "vp", "ended before the last region was scored"
    assert engine.final_scoring_ran

    # A draw ends with no reason at all, and still reached Final Scoring.
    drawn = Engine(seed=1)
    drawn.turn = 10
    drawn._finish_game()
    assert drawn.is_terminal and drawn.winner is None and drawn.game_over_reason is None
    assert drawn.final_scoring_ran

    # A game that never got there says so, through a serialize round trip.
    unfinished = Engine(seed=1)
    assert not unfinished.final_scoring_ran
    assert "final_scoring_ran" not in unfinished.serialize()
    assert Engine.deserialize(engine.serialize()).final_scoring_ran


def test_scoring_europe_below_control_still_pays_vp():
    """The fix must not turn every Europe scoring into a win: one Battleground
    short of Control is Domination, and pays."""
    from struggler.engine import Region, ScoringTier, Side
    engine = _europe_control_board()
    board = engine.board
    contested = next(c for c in board.countries_in(Region.EUROPE)
                     if board.countries[c].battleground)
    board.influence[contested]["USSR"] = board.influence[contested]["US"] + 3
    assert board.region_tier(Side.US, Region.EUROPE) is not ScoringTier.CONTROL
    engine._resolve_scoring_card("Europe_Scoring")
    assert not engine.is_terminal
    assert engine.vp > 0  # still a US scoring, just not a win
