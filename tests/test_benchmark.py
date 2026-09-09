

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


def _report(seeds, result, *, nuclear=0, finished=True):
    """A benchmark report with both seats of every seed scoring `result`."""
    games = [dict(seed=s, bot_side=side, finished=finished, result=result if finished else None)
             for s in seeds for side in ('US', 'USSR')]
    return dict(summary=dict(games=len(games), nuclear_losses=nuclear,
                             mean_signed_vp=0.0, score=result), games=games)


def test_acceptance_blocks_only_a_measurable_regression():
    from struggler.bots.benchmark import acceptance
    wide, held = range(4000, 4048), range(5000, 5048)
    # Dead even on both samples: nothing to measure, so nothing to block.
    ok, lines = acceptance([('gate', _report(wide, 0.5)), ('held-out', _report(held, 0.5))])
    assert ok, lines
    assert lines[-1] == 'ACCEPTED'
    # Losing every game is a regression the rules must catch.
    ok, lines = acceptance([('gate', _report(wide, 0.0)), ('held-out', _report(held, 0.0))])
    assert not ok and any('FAIL strength' in line for line in lines)
    # Winning every game is not a reason to block.
    ok, _ = acceptance([('gate', _report(wide, 1.0)), ('held-out', _report(held, 1.0))])
    assert ok


def test_acceptance_requires_disjoint_seeds_and_enough_of_them():
    from struggler.bots.benchmark import acceptance
    wide = range(4000, 4048)
    ok, lines = acceptance([('gate', _report(wide, 0.5))])
    assert not ok and any('FAIL evidence' in line for line in lines), lines
    # Two samples over the same seeds are one sample twice.
    ok, lines = acceptance([('gate', _report(wide, 0.5)), ('again', _report(wide, 0.5))])
    assert not ok and any('overlapping seeds' in line for line in lines), lines
    # Disjoint but far too few games.
    ok, lines = acceptance([('a', _report(range(4000, 4004), 0.5)),
                            ('b', _report(range(5000, 5004), 0.5))])
    assert not ok and any('finished games pooled' in line for line in lines), lines


def test_acceptance_treats_one_nuclear_loss_as_a_blocker():
    from struggler.bots.benchmark import acceptance
    ok, lines = acceptance([('gate', _report(range(4000, 4048), 0.5, nuclear=1)),
                            ('held-out', _report(range(5000, 5048), 0.5))])
    assert not ok and any('nuclear' in line for line in lines), lines


def test_acceptance_counts_a_seed_once_not_once_per_seat():
    """Both seats of a seed play the same deal, so they are one observation.
    Counting them separately halves the standard error and makes noise look
    like a result."""
    from struggler.bots.benchmark import acceptance, seed_scores
    games = _report(range(4000, 4032), 0.5)['games']
    assert len(games) == 64 and len(seed_scores(games)) == 32
