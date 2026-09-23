"""The interim look that decides whether an arm's second wave is played.

Two things are under test and they fail in opposite directions.

**The boundary has to be right**, because it is what pays for looking
twice. It is computed rather than quoted, so the tests check it against two
independently published values -- the O'Brien-Fleming and Pocock two-look
boundaries for a two-sided 0.10 -- and against the error it actually spends.

**The decision has to fail open.** Every way an interim reading can be
unusable is a reason to PLAY the second wave, never to skip it: a wave-1
shard that crashed, an arm with no finished pairs, a partner that did not
report. The cost of getting that backwards is half an experiment's seeds
reported as a whole one, which is silent and unrecoverable; the cost of
getting it right and being wrong is a wave of runner time.
"""
from __future__ import annotations

import json

import pytest

from conftest import load_script

W = load_script('wave_verdict')


# --- the boundary -------------------------------------------------------

def test_the_two_look_boundary_reproduces_the_published_obrien_fleming_pair():
    """(2.373, 1.678) for a two-sided 0.10 -- the one-sided 95% this repo
    reads -- is the standard published pair. Computing it and matching the
    table is what makes the numerical integration trustworthy."""
    interim, final = W.obrien_fleming(0.10)
    assert interim == pytest.approx(2.373, abs=0.001)
    assert final == pytest.approx(1.678, abs=0.001)


def test_the_boundary_spends_exactly_the_alpha_it_was_given():
    for alpha in (0.05, 0.10, 0.20):
        interim, final = W.obrien_fleming(alpha)
        assert W.alpha_spent(interim, final) == pytest.approx(alpha, abs=1e-6)


def test_a_single_look_at_1_645_is_the_0_10_it_has_always_been():
    """The integration's sanity check: with the interim bar out of reach,
    the design collapses to one look and must spend the familiar 0.10."""
    assert W.alpha_spent(99.0, 1.645) == pytest.approx(0.10, abs=1e-3)


def test_pocock_is_reproduced_too_and_is_why_it_was_not_chosen():
    """Pocock's two-look boundary for a two-sided 0.10 is 1.875 at BOTH
    looks. Reproducing a second published design from the same integration
    is the check that the first was not a coincidence -- and 1.875 against
    1.678 is the 12% wider final interval the docstring cites as the reason
    this repo takes O'Brien-Fleming instead: measured against the 1.645 a
    single look would use, Pocock's final bar is 14% wider and
    O'Brien-Fleming's is 2%."""
    assert W.alpha_spent(1.875, 1.875) == pytest.approx(0.10, abs=1e-3)
    assert W.FINAL_BOUNDARY < 1.875


def test_looking_twice_at_the_unadjusted_bar_really_does_cost_something():
    """The premise of the whole file: judging at 1.645 at both looks spends
    more than 0.10. If this were false the boundary would be unnecessary."""
    assert W.alpha_spent(1.645, 1.645) > 0.10


# --- the decision -------------------------------------------------------

def pooled(slug='on', *, score=None, se=None, missing=(), compare_to=None, **extra):
    meta = {'compare_to': compare_to} if compare_to else {}
    entry = {'shards': 4, 'missing': list(missing), 'meta': meta,
             'score': score, 'se': se, **extra}
    return {slug: entry}


def test_a_decisive_interim_stops_the_arm():
    # z = 0.06 / 0.02 = 3.0, past 2.373.
    out = W.decide({'arms': pooled(score=0.56, se=0.02), 'paired': []})
    assert out['on']['proceed'] is False


def test_a_decisively_worse_interim_stops_too_because_that_is_a_result():
    out = W.decide({'arms': pooled(score=0.44, se=0.02), 'paired': []})
    assert out['on']['proceed'] is False
    assert out['on']['z'] < 0


def test_an_interim_short_of_the_boundary_plays_the_second_wave():
    # z = 0.04 / 0.02 = 2.0: clears 1.645 and would read as a "measurable
    # gain" at one look, and is exactly the case the boundary exists for.
    out = W.decide({'arms': pooled(score=0.54, se=0.02), 'paired': []})
    assert out['on']['proceed'] is True


def test_a_missing_wave_one_shard_plays_the_second_wave():
    out = W.decide({'arms': pooled(score=0.56, se=0.02, missing=['on--2']), 'paired': []})
    assert out['on']['proceed'] is True
    assert 'missing' in out['on']['why']


def test_an_arm_with_no_finished_pairs_plays_the_second_wave():
    out = W.decide({'arms': pooled(score=None, se=None), 'paired': []})
    assert out['on']['proceed'] is True


def test_a_compare_to_arm_is_judged_on_its_paired_difference_not_its_level():
    """An anchored arm can sit at 0.56 against its anchor while the thing
    being measured -- the difference from its base arm -- is nothing. Judging
    the level would stop it on a number the dispatch was not asking about."""
    arms = {**pooled('on', score=0.560, se=0.010, compare_to='base'),
            **pooled('base', score=0.558, se=0.010)}
    pairs = [{'arm': 'on', 'minus': 'base', 'diff_exact': 0.002, 'se': 0.010, 'seeds': 512}]
    out = W.decide({'arms': arms, 'paired': pairs})
    assert out['on']['proceed'] is True, 'the level was decisive; the difference is not'


def test_a_decisive_paired_difference_stops_both_arms_of_the_pair():
    arms = {**pooled('on', score=0.60, se=0.01, compare_to='base'),
            **pooled('base', score=0.50, se=0.01)}
    pairs = [{'arm': 'on', 'minus': 'base', 'diff_exact': 0.10, 'se': 0.01, 'seeds': 512}]
    out = W.decide({'arms': arms, 'paired': pairs})
    assert out['on']['proceed'] is False
    assert out['base']['proceed'] is False


def test_a_base_arms_own_level_does_not_decide_its_pair():
    """A paired difference resolves over the seeds BOTH arms played, so the
    two ends have to move together -- and the thing they move on is the
    difference. Here the BASE arm is wildly decisive on its own level and the
    difference is nothing: stopping on the level would end the experiment
    having measured the one number nobody asked for."""
    arms = {**pooled('on', score=0.52, se=0.02, compare_to='base'),
            **pooled('base', score=0.70, se=0.01)}   # decisive on its own level
    pairs = [{'arm': 'on', 'minus': 'base', 'diff_exact': 0.01, 'se': 0.02, 'seeds': 512}]
    out = W.decide({'arms': arms, 'paired': pairs})
    assert out['on']['proceed'] is True
    assert out['base']['proceed'] is True, 'the pair must move together'
    assert 'paired' in out['base']['why']


def test_a_third_arm_joining_a_pair_is_dragged_by_it():
    """`compare_to` is a graph: an arm can be the base of two comparisons.
    A continue anywhere in a connected group has to reach all of it, or the
    group's arms end up measured on different numbers of seeds."""
    arms = {**pooled('on', score=0.70, se=0.01, compare_to='base'),
            **pooled('alt', score=0.52, se=0.02, compare_to='base'),
            **pooled('base', score=0.50, se=0.01)}
    pairs = [{'arm': 'on', 'minus': 'base', 'diff_exact': 0.20, 'se': 0.01, 'seeds': 512},
             {'arm': 'alt', 'minus': 'base', 'diff_exact': 0.01, 'se': 0.02, 'seeds': 512}]
    out = W.decide({'arms': arms, 'paired': pairs})
    assert out['alt']['proceed'] is True
    assert out['base']['proceed'] is True
    assert out['on']['proceed'] is True, 'its base continues, so it must too'
    assert 'which continues' in out['on']['why']


def test_a_paired_arm_whose_partner_never_reported_plays_the_second_wave():
    arms = pooled('on', score=0.60, se=0.01, compare_to='base')
    out = W.decide({'arms': arms, 'paired': []})
    assert out['on']['proceed'] is True


# --- selection and the CLI ---------------------------------------------

def shard(slug, i):
    return {'slug': slug, 'shard': i, 'of': 8, 'seeds': f'{i}-{i}', 'weights': {},
            'anchor': '', 'bot_ref': '', 'openings': '', 'compare_to': '', 'logs': False}


def test_select_keeps_only_the_shards_of_arms_that_proceed():
    wave2 = [shard('on', 4), shard('on', 5), shard('off', 4)]
    kept = W.select(wave2, {'on': {'proceed': False}, 'off': {'proceed': True}})
    assert [s['slug'] for s in kept] == ['off']


def test_an_arm_the_verdict_never_mentions_is_played_not_dropped():
    """An arm absent from the pooled interim did not report at all. That is a
    failure, and the fail-open rule covers it here too."""
    kept = W.select([shard('ghost', 4)], {})
    assert len(kept) == 1


def test_an_unreadable_interim_file_plays_every_wave_two_shard(tmp_path, capsys):
    """The outermost fail-open: a corrupt or absent pooled report must cost a
    wave of runner time, not half the experiment."""
    wave2 = [shard('a', 4), shard('b', 4)]
    (tmp_path / 'wave2.json').write_text(json.dumps(wave2))
    (tmp_path / 'pooled.json').write_text('{not json at all')
    out = tmp_path / 'next.json'
    assert W.main([str(tmp_path / 'pooled.json'), '--wave2', str(tmp_path / 'wave2.json'),
                   '--out', str(out)]) == 0
    assert json.loads(out.read_text()) == wave2
    assert 'UNREADABLE' in capsys.readouterr().out


def test_the_cli_writes_the_surviving_shards_and_reports_the_count(tmp_path, capsys):
    wave2 = [shard('on', 4), shard('off', 4)]
    (tmp_path / 'wave2.json').write_text(json.dumps(wave2))
    (tmp_path / 'pooled.json').write_text(json.dumps({
        'arms': {**pooled('on', score=0.60, se=0.01), **pooled('off', score=0.51, se=0.01)},
        'paired': []}))
    out = tmp_path / 'next.json'
    assert W.main([str(tmp_path / 'pooled.json'), '--wave2', str(tmp_path / 'wave2.json'),
                   '--out', str(out)]) == 0
    assert [s['slug'] for s in json.loads(out.read_text())] == ['off']
    assert 'count=1' in capsys.readouterr().out


# --- the producer-to-consumer boundary -----------------------------------

P = load_script('pool_reports')


def _game(seed, side, result):
    """One seat-game as `benchmark` reports it, with every field
    `summarize` reads and nothing else."""
    return {'seed': seed, 'bot_side': side, 'result': result, 'finished': True,
            'winner': side if result == 1 else ('' if result == 0.5 else 'X'),
            'reason': 'vp', 'turn': 10, 'signed_vp': 0, 'projected_vp': 0, 'total': 0,
            'bg_diff': {'Europe': 0}, 'value': 0, 'defcon': 3, 'seconds': 1.0,
            'searches': 0, 'search_seconds': 0.0}


def _write_shard(root, slug, shard, seeds, result, compare_to=''):
    d = root / f'experiment-{slug}--{shard}'
    d.mkdir()
    games = [_game(s, side, result(s)) for s in seeds for side in ('US', 'USSR')]
    (d / f'{slug}.json').write_text(json.dumps({'games': games}))
    (d / 'arm.json').write_text(json.dumps({'compare_to': compare_to} if compare_to else {}))


def test_the_real_pooled_file_reaches_the_paired_verdict(tmp_path):
    """The file `decide` reads is the one `pool_reports.main` WRITES, not a
    dict built to the consumer's expectations. Until 2026-09-23 the producer
    wrote `paired` and the consumer read `pairs`; every test above built its
    own `pairs` and passed, and every paired arm on CI played both waves.

    Three pairs through the real CLI: decisive (both arms stop), inconclusive
    (both play), and a partner that never reported (fail open)."""
    shards = tmp_path / 'shards'
    shards.mkdir()
    seeds = range(40)
    # Decisive: the candidate wins every other seed its base drew.
    _write_shard(shards, 'base', 0, seeds, lambda s: 0.5)
    _write_shard(shards, 'on', 0, seeds, lambda s: 1.0 if s % 2 else 0.5, compare_to='base')
    # Inconclusive: the same seeds, the difference alternates in sign.
    _write_shard(shards, 'flat-base', 0, seeds, lambda s: 0.5)
    _write_shard(shards, 'flat', 0, seeds, lambda s: (1.0, 0.0, 0.5, 0.5)[s % 4],
                 compare_to='flat-base')
    # A partner that never reported.
    _write_shard(shards, 'orphan', 0, seeds, lambda s: 1.0, compare_to='ghost')

    out = tmp_path / 'pooled.json'
    assert P.main([str(shards), '--json', str(out)]) == 0
    pooled_json = json.loads(out.read_text())
    assert W.PAIRED_KEY in pooled_json, 'the producer and the consumer name the field differently'

    verdicts = W.decide(pooled_json)
    assert verdicts['on']['proceed'] is False and verdicts['base']['proceed'] is False
    assert verdicts['on']['z'] > W.INTERIM_BOUNDARY
    assert 'paired' in verdicts['on']['why']
    assert verdicts['flat']['proceed'] is True and verdicts['flat-base']['proceed'] is True
    assert verdicts['flat']['z'] is not None, 'readable, just not decisive'
    assert verdicts['orphan']['proceed'] is True and verdicts['orphan']['z'] is None
