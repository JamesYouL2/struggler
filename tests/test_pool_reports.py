"""Pooling against the plan: what a run was owed, not just what arrived.

The 2026-09-25 audit's F2, and seen live the day before: the tie-break's
0.5 arm lost shard 6 to a runner shutdown and pooled as `shards: 8,
missing: []` against a plan of 9, because pooling discovered shards by the
directories that existed. A shard that never uploaded was invisible, a
partial one looked whole, and the interim could stop an arm on evidence it
did not have.

These drive shard reports through the real `benchmark.main` (only the
process pool is replaced, as in `test_benchmark_stall.py`), pool them with
the real `pool_reports` against the manifest `shard_plan` builds, and hand
the result to the real `wave_verdict.decide` -- producer to consumer, the
boundary the `paired`/`pairs` defect lived on.
"""
from __future__ import annotations

import json

import pytest

from conftest import load_script
from shard_plan import build, split_waves
from struggler.bots import benchmark
from test_benchmark_stall import _fake_pool, _Results
from test_wave_verdict import _game

P = load_script('pool_reports')
W = load_script('wave_verdict')


def _plan(arms, waves=True):
    wave1, wave2 = split_waves(build(arms), waves)
    return {'waves': waves, 'shards': wave1 + wave2}


def _play(root, monkeypatch, shard, result=lambda seed: 1.0, lose=()):
    """One shard, played by `benchmark.main`: every seat of its seeds
    finishes except the (seed, side) pairs in `lose`, after which the pool
    stalls -- a PARTIAL report with its unfinished games named."""
    lo, hi = (int(x) for x in shard['seeds'].split('-'))
    games = [_game(seed, side, result(seed)) for seed in range(lo, hi + 1)
             for side in ('US', 'USSR') if (seed, side) not in lose]
    monkeypatch.setattr(benchmark, 'Pool', _fake_pool(_Results(games, stall=bool(lose))))
    d = root / f'experiment-{shard["slug"]}--{shard["shard"]}'
    d.mkdir(parents=True)
    status = benchmark.main(['--bot', 'greedy', '--opponent', 'greedy', '--workers', '1',
                             '--seeds', shard['seeds'], '--report', str(d / f'{shard["slug"]}.json')])
    assert status == (6 if lose else None)
    (d / 'arm.json').write_text(json.dumps(shard))


def _pool(root, plan, selected=None, stage='final'):
    arms = P.load(root)
    result = P.pooled(arms, plan, selected, stage)
    return {'arms': result, 'paired': P.paired(arms, result, plan, selected, stage)}


ARM = {'slug': 'on', 'seeds': '100-107', 'reserve': '900-907', 'shard': 4}


def test_an_absent_shard_is_missing_and_the_interim_fails_open(tmp_path, monkeypatch):
    """The audit's reproduction, played: wave 1 is two shards, one uploads a
    decisive report and the other never arrives. Without the manifest the
    look saw one complete-looking shard and stopped the arm."""
    arm = {'slug': 'on', 'seeds': '100-115', 'shard': 4}
    plan = _plan([arm])
    wave1 = [s for s in plan['shards'] if s['wave'] == 1]
    _play(tmp_path, monkeypatch, wave1[0])
    pooled = _pool(tmp_path, plan, stage='interim')['arms']['on']
    assert pooled['missing'] == ['experiment-on--1']
    assert pooled['complete'] is False and pooled['target'] == 8 and pooled['seeds'] == 4
    verdict = W.decide({'arms': {'on': pooled}, 'paired': []})['on']
    assert verdict['proceed'] is True and 'missing' in verdict['why']


def test_a_partial_shard_is_partial_and_its_reading_is_short(tmp_path, monkeypatch):
    plan = _plan([{'slug': 'on', 'seeds': '100-107', 'shard': 4}], waves=False)
    for s in plan['shards']:
        _play(tmp_path, monkeypatch, s, lose={(101, 'USSR')} if s['shard'] == 0 else ())
    pooled = _pool(tmp_path, plan)['arms']['on']
    assert pooled['partial'] == ['experiment-on--0'] and pooled['missing'] == []
    assert pooled['complete'] is False and pooled['dropped'] == [101]
    assert '**SHORT**' in P.markdown({'on': pooled})


def test_a_spare_shard_backfills_a_whole_lost_shard(tmp_path, monkeypatch):
    """The loss that happens: a runner dies and takes a whole core shard.
    The spare stands in for it, the reading reaches its target, and the
    censoring stays on the record -- the lost shard is still MISSING and
    its seeds are still `dropped`."""
    plan = _plan([ARM], waves=False)
    for s in plan['shards']:
        if s['shard'] != 1:
            _play(tmp_path, monkeypatch, s)
    pooled = _pool(tmp_path, plan)['arms']['on']
    assert pooled['complete'] is True and pooled['seeds'] == 8 == pooled['target']
    assert pooled['missing'] == ['experiment-on--1']
    assert pooled['dropped'] == [104, 105, 106, 107]
    assert pooled['backfilled'] == [900, 901, 902, 903]


def test_spares_count_only_as_backfill(tmp_path, monkeypatch):
    """Everything finished: the spares played and count for nothing -- a
    planned N reads N, never N plus whatever spare work landed."""
    plan = _plan([ARM], waves=False)
    for s in plan['shards']:
        _play(tmp_path, monkeypatch, s, result=lambda seed: 0.0 if seed >= 900 else 1.0)
    pooled = _pool(tmp_path, plan)['arms']['on']
    assert pooled['seeds'] == 8 and pooled['backfilled'] == [] and pooled['score'] == 1.0


def test_a_pair_counts_the_first_n_seeds_finished_in_both_arms(tmp_path, monkeypatch):
    """Each arm loses a DIFFERENT seed. Backfilling each arm on its own
    (the old per-shard reserve) left the pair two seeds short; counting the
    pair against the plan backfills both from the spares and reads N."""
    base = {**ARM, 'slug': 'base'}
    on = {**ARM, 'compare_to': 'base'}
    plan = _plan([base, on], waves=False)
    for s in plan['shards']:
        lose = ({(100, 'US')} if s['slug'] == 'base' and s['shard'] == 0 else
                {(105, 'US')} if s['slug'] == 'on' and s['shard'] == 1 else ())
        _play(tmp_path, monkeypatch, s, lose=lose)
    pair = _pool(tmp_path, plan)['paired'][0]
    assert pair['seeds'] == 8 and pair['complete'] is True
    assert pair['dropped'] == [100, 105]


def test_a_skipped_wave_two_is_the_design_not_a_loss(tmp_path, monkeypatch):
    """The interim stopped the arm: wave 2 is skipped, not missing, the
    reading is complete on wave 1, and its interval is quoted at the
    interim bar it cleared."""
    plan = _plan([ARM])
    for s in plan['shards']:
        if s['wave'] == 1:
            _play(tmp_path, monkeypatch, s)
    pooled = _pool(tmp_path, plan, selected=[])['arms']['on']
    assert pooled['missing'] == [] and pooled['complete'] is True and pooled['target'] == 4
    assert len(pooled['skipped']) == 3
    assert (pooled['stage'], pooled['bar']) == ('interim', pytest.approx(W.INTERIM_BOUNDARY))


def test_the_final_bar_is_the_sequential_one_when_there_were_waves(tmp_path, monkeypatch):
    """Audit F5: a two-look run's final interval at the fixed-sample 1.645
    advertises a bar the design did not use."""
    plan = _plan([ARM])
    for s in plan['shards']:
        _play(tmp_path, monkeypatch, s, result=lambda seed: (1.0, 0.0, 0.5)[seed % 3])
    pooled = _pool(tmp_path, plan, selected=None)['arms']['on']
    assert (pooled['stage'], pooled['bar']) == ('final', pytest.approx(W.FINAL_BOUNDARY))
    assert pooled['halfwidth'] == round(W.FINAL_BOUNDARY * pooled['se'], 3)
    no_waves = _plan([ARM], waves=False)
    assert _pool(tmp_path, no_waves)['arms']['on']['bar'] == W.SINGLE_LOOK


def test_the_cli_reads_the_manifest_and_a_missing_selection_as_all_of_wave_two(tmp_path, monkeypatch):
    plan = _plan([ARM])
    shards = tmp_path / 'shards'
    for s in plan['shards']:
        if s['wave'] == 1:
            _play(shards, monkeypatch, s)
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    out = tmp_path / 'pooled.json'
    assert P.main([str(shards), '--json', str(out), '--plan', str(tmp_path / 'plan.json'),
                   '--selected', str(tmp_path / 'absent.json')]) == 0
    arm = json.loads(out.read_text())['arms']['on']
    # No selection arrived, so wave 2 was owed -- and never played.
    assert len(arm['missing']) == 3 and arm['complete'] is False


def test_the_pooled_table_carries_the_event_measurement(tmp_path, monkeypatch):
    """The maintainer's 2026-09-24 ask: every experiment's collect table
    says what fired and how many event choices were blind."""
    plan = _plan([{'slug': 'on', 'seeds': '100-101', 'shard': 2}], waves=False)
    _play(tmp_path, monkeypatch, plan['shards'][0])
    arms = P.load(tmp_path)
    for g in arms['on']['games']:
        g.update(events_fired={'Fidel': 1}, blind_picks={'Chernobyl': 1},
                 event_choices={'Chernobyl|unpriced': 1, 'Blockade|decided': 1})
    result = P.pooled(arms, plan)
    assert result['on']['blind_picks'] == {'Chernobyl': 4}
    table = P.markdown(result)
    assert '**Event measurement**' in table and 'Chernobyl 4' in table
