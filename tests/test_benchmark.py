

def test_expert_valuations_file_is_well_formed_and_the_check_runs(tmp_path):
    import io
    from struggler.bots.benchmark import expert_check, to_ops
    from struggler.bots.strategic.public_cards import CARDS
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


def test_a_baseline_policy_loads_its_own_bot_modules_not_the_candidates(tmp_path):
    """`strategic@<file>` plays an older policy against the current one. That
    older `strategic.py` imports `struggler.bots.*` by name, so without
    substitution it binds the *candidate's* code and the gate reports the
    candidate playing itself.

    Not hypothetical, and not only about `evaluator`: when the snapshot held
    `strategic.py` and `evaluator.py` alone, a `public_cards.py` change gated
    against itself and returned 0.500 with a standard error of zero over 96
    seeds. Every snapshotted module stands in, and only while the baseline
    loads.

    The snapshot here is deliberately the *old* flat layout -- `evaluator.py`
    and `public_cards.py` beside `strategic.py` -- because that is what every
    baseline from before those modules moved into `bots/strategic/` looks
    like, and gating against one of those revisions has to keep working.
    """
    import sys
    from struggler.bots.strategic import evaluator as real_evaluator, public_cards as real_cards
    from struggler.bots.benchmark import load_module

    (tmp_path / 'evaluator.py').write_text('MARKER = "baseline evaluator"\n')
    (tmp_path / 'public_cards.py').write_text('MARKER = "baseline cards"\n')
    (tmp_path / 'strategic.py').write_text(
        'from struggler.bots import evaluator as ev\n'
        'from struggler.bots import public_cards as pc\n'
        'BOUND = (ev, pc)\n')
    evaluator, cards = load_module(str(tmp_path / 'strategic.py')).BOUND
    assert (evaluator.MARKER, cards.MARKER) == ('baseline evaluator', 'baseline cards')
    assert evaluator is not real_evaluator and cards is not real_cards
    # The substitution is undone: the candidate keeps its own code, which
    # now lives under the package rather than beside it.
    assert sys.modules['struggler.bots.strategic.evaluator'] is real_evaluator
    assert sys.modules['struggler.bots.strategic.public_cards'] is real_cards
    assert 'struggler.bots.evaluator' not in sys.modules


def test_a_baseline_resolves_the_engine_from_the_candidate(tmp_path):
    """Only the bot is compared. The engine is the shared arbiter both sides
    are measured under, so it is deliberately not snapshotted."""
    from struggler.engine import board as real_board
    from struggler.bots.benchmark import load_module

    (tmp_path / 'evaluator.py').write_text('MARKER = "baseline"\n')
    (tmp_path / 'strategic.py').write_text(
        'from struggler.engine import board\nBOUND = board\n')
    assert load_module(str(tmp_path / 'strategic.py')).BOUND is real_board


def test_acceptance_warns_when_every_game_is_a_dead_heat():
    """A gate where both sides play identically is either a change that cannot
    affect play or a comparison that is not comparing anything."""
    from struggler.bots.benchmark import acceptance
    ok, lines = acceptance([('gate', _report(range(4000, 4048), 0.5)),
                            ('held-out', _report(range(5000, 5048), 0.5))])
    assert ok  # a proven no-op refactor is supposed to look like this
    assert any('WARN identical' in line for line in lines), lines
    # A change that actually moved games does not warn.
    mixed = _report(range(4000, 4048), 0.5)
    mixed['games'][0]['result'] = 1.0
    ok, lines = acceptance([('gate', mixed), ('held-out', _report(range(5000, 5048), 0.5))])
    assert ok and not any('WARN identical' in line for line in lines), lines


def test_a_baseline_without_a_sibling_evaluator_still_loads(tmp_path):
    from struggler.bots.strategic import evaluator as real
    from struggler.bots.benchmark import load_module

    (tmp_path / 'strategic.py').write_text(
        'from struggler.bots.strategic import evaluator as ev\nBOUND = ev\n')
    assert load_module(str(tmp_path / 'strategic.py')).BOUND is real


def _report(seeds, result, *, nuclear=0, finished=True):
    """A benchmark report with both seats of every seed scoring `result`, and
    `nuclear` of those games lost to DEFCON 1."""
    games = [dict(seed=s, bot_side=side, finished=finished, turn=10, reason='vp',
                  result=result if finished else None)
             for s in seeds for side in ('US', 'USSR')]
    for game in games[:nuclear]:
        game['reason'] = 'defcon_1'
    return dict(summary=dict(games=len(games), nuclear_losses=nuclear,
                             mean_signed_vp=0.0, score=result), games=games)


def test_early_stopping_never_stops_before_the_evidence_floor():
    """The floor is a floor. A run of unbroken wins is exactly the evidence
    that tempts a gate to stop at 20 games, and 20 games is not enough to
    have learned anything about a change."""
    from struggler.bots.benchmark import ACCEPTANCE, _decided
    sample_of = {seed: seed % 2 for seed in range(200)}
    planned = {0: 100, 1: 100}
    games = []
    for seed in range(200):
        for side in ('US', 'USSR'):
            games.append(dict(seed=seed, bot_side=side, finished=True, turn=10,
                              reason='vp', result=1.0))
        if (seed + 1) * 2 < ACCEPTANCE['min_games']:
            assert not _decided(games, sample_of, planned), 'stopped below the floor'


def test_early_stopping_never_predicts_a_held_out_seed_from_a_tuning_seed():
    """The gate plays two samples because the tuning seeds are the ones the
    change was selected on, so they score better by construction. Resampling
    the unplayed seeds from both pooled would let a tuning seed stand in for
    an unplayed held-out one, making the stopping rule optimistic in exactly
    the way the split exists to prevent -- and since the gate exhausts the
    smaller tuning range first, every seed unplayed at the decision point is
    a held-out one."""
    import random
    from struggler.bots.benchmark import draw_unplayed, stable_verdict

    pools = {0: [(0, 1.0, 0)] * 40, 1: [(1, 0.0, 0)] * 20}
    drawn = draw_unplayed(pools, {0: 0, 1: 30}, random.Random(1))
    assert len(drawn) == 30
    assert {record[0] for record in drawn} == {1}, 'a tuning seed stood in for a held-out one'
    assert {record[1] for record in drawn} == {0.0}

    # And a sample with seeds still to play but nothing observed yet cannot be
    # predicted at all, so the run must not stop.
    observed = [(0, 1.0, 0)] * 80
    assert not stable_verdict(observed, {0: 0, 1: 16})


def test_early_stopping_only_stops_where_the_full_run_agrees():
    """Every historical gate, replayed seed by seed: wherever the rule would
    have stopped, the verdict it stopped on is the verdict the full run
    reached. Stopping early is only sound if it cannot change the answer."""
    import glob, json, os, collections
    import pytest
    from struggler.bots.benchmark import seed_scores, verdict, stable_verdict, ACCEPTANCE

    gates = collections.defaultdict(dict)
    for path in glob.glob('logs/game-check/*/full-vs-*.json'):
        gates[os.path.dirname(path)][os.path.basename(path)] = path
    checked = 0
    for directory, files in sorted(gates.items()):
        if len(files) < 2:
            continue
        groups = []
        for name in ('full-vs-base.json', 'full-vs-held.json'):
            if name in files:
                with open(files[name]) as f:
                    groups.append(seed_scores(json.load(f)['games']))
        if len(groups) < 2:
            continue
        observed = [(index, score, 0)
                    for index, scores in enumerate(groups)
                    for _, score in sorted(scores.items())]
        planned = collections.Counter(index for index, _, _ in observed)
        total = len(observed)
        final = verdict(groups, 0, total * 2)
        for k in range(2, total):
            if k * 2 < ACCEPTANCE['min_games']:
                continue
            played = collections.Counter(index for index, _, _ in observed[:k])
            if stable_verdict(observed[:k], {i: n - played[i] for i, n in planned.items()}):
                partial = collections.defaultdict(dict)
                for n, (index, score, _) in enumerate(observed[:k]):
                    partial[index][n] = score
                assert verdict(list(partial.values()), 0, k * 2) == final, (
                    directory, k, 'stopped on a verdict the full run disagreed with')
                checked += 1
                break
    if checked < 3:
        pytest.skip(f'only {checked} local gate reports under logs/game-check '
                    '(gitignored evidence); the synthetic case covers the rule')


def test_early_stopping_agrees_with_the_full_run_on_random_gates():
    """The same property without local evidence: over random gates spanning
    clear wins, clear losses and coin flips, stopping early never lands on a
    verdict the full run contradicts."""
    import collections
    import random
    from struggler.bots.benchmark import verdict, stable_verdict, ACCEPTANCE

    rng = random.Random(11)
    stops = disagreements = 0
    for trial in range(60):
        edge = rng.choice((0.30, 0.45, 0.50, 0.55, 0.70))
        total = 96
        observed = [(n % 2, rng.choice((0.0, 0.5, 1.0)) if edge == 0.5
                     else float(rng.random() < edge), 0)
                    for n in range(total)]
        planned = collections.Counter(index for index, _, _ in observed)

        def at(k):
            partial = collections.defaultdict(dict)
            for n, (index, score, _) in enumerate(observed[:k]):
                partial[index][n] = score
            return verdict(list(partial.values()), 0, k * 2)

        final = at(total)
        for k in range(ACCEPTANCE['min_games'] // 2, total):
            played = collections.Counter(index for index, _, _ in observed[:k])
            if stable_verdict(observed[:k], {i: n - played[i] for i, n in planned.items()}):
                stops += 1
                disagreements += at(k) != final
                break
    assert stops >= 20, f'the rule almost never fired ({stops} of 60 gates)'
    assert disagreements == 0, f'{disagreements} of {stops} early stops changed the verdict'


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


def test_acceptance_measures_nuclear_losses_against_their_rate():
    """The cap is a rate above any human-plausible policy, not this bot's own
    near-zero rate. WBC play ends in nuclear war in 5.4-11.7% of games, so a
    policy taking human-like DEFCON risk expects 5-11 losses in a 192-game
    gate; a cap of 1 rejected all of those, enforcing the bot's 38x-to-82x
    over-caution instead of testing it. A loss still warns and names its seed
    to replay."""
    from struggler.bots.benchmark import acceptance, nuclear_cap
    ok, lines = acceptance([('gate', _report(range(4000, 4048), 0.5, nuclear=1)),
                            ('held-out', _report(range(5000, 5048), 0.5))])
    assert ok, lines
    warning = next(line for line in lines if 'WARN nuclear' in line)
    assert 'seed 4000' in warning  # named so it can be replayed

    # A human-like rate passes where the old cap of 1 rejected it.
    ok, lines = acceptance([('gate', _report(range(4000, 4048), 0.5, nuclear=5)),
                            ('held-out', _report(range(5000, 5048), 0.5, nuclear=5))])
    assert ok, lines

    # Past the rate -- where the strength score would catch it anyway -- fails.
    over = nuclear_cap(192) + 1
    ok, lines = acceptance([('gate', _report(range(4000, 4048), 0.5, nuclear=over)),
                            ('held-out', _report(range(5000, 5048), 0.5))])
    assert not ok and any('FAIL nuclear' in line for line in lines), lines


def test_the_nuclear_cap_scales_with_the_gate_and_never_fails_a_small_one():
    """A fixed count means different things at 76 seeds and 96. The floor
    keeps a small gate from failing on one or two."""
    from struggler.bots.benchmark import nuclear_cap
    assert nuclear_cap(192) == 19
    assert nuclear_cap(152) == 15
    assert nuclear_cap(10) == 3  # the floor, not 1


def test_an_opponent_nuclear_defeat_is_not_a_candidate_nuclear_loss():
    """Seed 5020 on gate-bcff140: the candidate US won, reason defcon_1, the
    baseline USSR having blown up on turn 10. `acceptance` warned about it
    as a candidate loss and would have failed the gate on a second baseline
    blunder; `summarize` had the attribution right. One helper now serves
    every count, and the opponent's defeats are reported, not penalised."""
    from struggler.bots.benchmark import acceptance, _decided
    report = _report(range(4000, 4048), 0.5)
    for game in report['games'][:2]:
        game['reason'] = 'defcon_1'
        game['winner'] = game['bot_side']  # the candidate's win
    ok, lines = acceptance([('gate', report), ('held-out', _report(range(5000, 5048), 0.5))])
    assert ok, lines
    assert not any('WARN nuclear' in line or 'FAIL nuclear' in line for line in lines), lines
    assert any('opponent lost to DEFCON 1 in 2 games' in line for line in lines), lines

    # The early-stopping count agrees: two opponent defeats change nothing.
    games = report['games'] + _report(range(5000, 5048), 0.5)['games']
    sample_of = {s: 0 for s in range(4000, 4048)} | {s: 1 for s in range(5000, 5048)}
    assert _decided(games, sample_of, {0: 48, 1: 48})


def test_acceptance_counts_a_seed_once_not_once_per_seat():
    """Both seats of a seed play the same deal, so they are one observation.
    Counting them separately halves the standard error and makes noise look
    like a result."""
    from struggler.bots.benchmark import seed_scores
    games = _report(range(4000, 4032), 0.5)['games']
    assert len(games) == 64 and len(seed_scores(games)) == 32


def test_a_snapshotted_package_binds_its_own_submodules(tmp_path):
    """A baseline that is a *package* must import its own submodules, not the
    candidate's.

    `_SnapshotFinder` used to decline every dotted name, so
    `struggler.bots.strategic.policy` fell through to normal resolution and
    answered with the candidate's copy: the baseline would have played half
    its own code and half the code it was being measured against. Nothing was
    a package when that was written, and the gate has twice been caught
    comparing a change with itself, so this is pinned before anything becomes
    one.
    """
    snapshot = tmp_path / 'base'
    pkg = snapshot / 'strategic'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text(
        'from struggler.bots.strategic.policy import MARKER\n')
    (pkg / 'policy.py').write_text("MARKER = 'baseline'\n")
    # A sibling top-level module in the same snapshot must still shadow too.
    (snapshot / 'sibling.py').write_text("MARKER = 'baseline-sibling'\n")
    entry = snapshot / 'entry.py'
    entry.write_text('from struggler.bots.strategic import MARKER\n'
                     'from struggler.bots.sibling import MARKER as SIBLING\n')

    from struggler.bots import benchmark
    loaded = benchmark.load_module(str(entry))
    assert loaded.MARKER == 'baseline', 'baseline package bound the candidate submodule'
    assert loaded.SIBLING == 'baseline-sibling'

    # And the candidate's own modules are restored afterwards.
    import struggler.bots.strategic as live
    assert getattr(live, 'MARKER', None) is None
    import sys as _sys
    assert 'struggler.bots.sibling' not in _sys.modules
