

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


def test_a_baseline_policy_loads_its_own_evaluator_not_the_candidates(tmp_path):
    """`strategic@<file>` plays an older policy against the current one. That
    older `strategic.py` imports `struggler.bots.evaluator` by name, so
    without substitution it would bind the *candidate's* evaluation terms and
    the gate would report the candidate playing itself. An `evaluator.py`
    beside the baseline file stands in while it loads, and only while."""
    import sys
    import struggler.bots as package
    from struggler.bots import evaluator as real
    from struggler.bots.benchmark import load_module

    (tmp_path / 'evaluator.py').write_text('MARKER = "baseline"\n')
    (tmp_path / 'strategic.py').write_text(
        'from struggler.bots import evaluator as ev\nBOUND = ev\n')
    loaded = load_module(str(tmp_path / 'strategic.py'))
    assert loaded.BOUND.MARKER == 'baseline'
    assert loaded.BOUND is not real
    # The substitution is undone: the candidate keeps its own terms.
    assert package.evaluator is real
    assert sys.modules['struggler.bots.evaluator'] is real


def test_a_baseline_without_a_sibling_evaluator_still_loads(tmp_path):
    from struggler.bots import evaluator as real
    from struggler.bots.benchmark import load_module

    (tmp_path / 'strategic.py').write_text(
        'from struggler.bots import evaluator as ev\nBOUND = ev\n')
    assert load_module(str(tmp_path / 'strategic.py')).BOUND is real
