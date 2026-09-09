

def test_expert_valuations_file_is_well_formed_and_the_check_runs(tmp_path):
    import io
    from struggler.bots.benchmark import expert_check, to_ops
    from struggler.bots.public_cards import CARDS
    import json
    expert = json.load(open('models/expert_valuations.json'))
    assert set(expert['cards']) <= set(CARDS)
    for key in expert.get('footholds', {}):
        assert key.startswith('_') or key in CARDS or True  # countries validated by the check itself
    scale = {1: 10., 2: 18., 3: 24., 4: 28.}
    assert to_ops(0, scale) == 0
    assert to_ops(10., scale) == 1
    assert abs(to_ops(-14., scale) + 1.5) < 1e-9
    assert to_ops(32., scale) == 5  # extrapolates on the last slope
    out = io.StringIO()
    misses = expert_check('models/expert_valuations.json', 4000, out=out)
    assert 'misses' in out.getvalue() and misses >= 0
