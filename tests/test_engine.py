

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
