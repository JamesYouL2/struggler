"""The parity corpus: every position in tests/corpus/positions.json.gz was
captured from the current evaluator and planner (scripts/capture_corpus.py).
Any refactor of the evaluation path, and any native kernel, must reproduce
these outputs: exact rankings and top actions, values within tolerance,
identical planner risks in the recorded query order, identical truncation
and node counts. Regenerate the corpus only by an explicit commit
(docs/RUST_PORT_PLAN.md, Option C step 1)."""
import dataclasses
import gzip
import json
import math
import os
import pathlib
import subprocess
import sys

import pytest

from struggler.engine import Engine, Region, Side
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.bots.rollout import RolloutPolicy
from struggler.bots.strategic import StrategicPlayer, StrategicWeights

CORPUS = pathlib.Path(__file__).parent / 'corpus' / 'positions.json.gz'
ABS, REL = 1e-9, 1e-9
REQUIRED = ('engine', 'side', 'kind', 'ranking', 'production_nodes', 'weights', 'prior', 'options',
            'country_value', 'region_score', 'region_margin', 'ops_value', 'event_value')
PLANNER_REQUIRED = ('probes', 'nodes_after_probes', 'truncated')


def _close(a, b):
    return math.isclose(a, b, rel_tol=REL, abs_tol=ABS)


@pytest.fixture(scope='module')
def corpus():
    with gzip.open(CORPUS, 'rt') as f:
        return json.load(f)


def test_corpus_schema_and_provenance(corpus):
    assert corpus['version'] == 3
    assert len(corpus['source_revision']) == 40 and corpus['generator_sha256']
    records = corpus['records']
    assert len(records) > 200
    for rec in records:
        missing = [k for k in REQUIRED if k not in rec]
        assert not missing, (rec['seed'], rec['turn'], missing)
        if 'planner' in rec:
            assert all(k in rec['planner'] for k in PLANNER_REQUIRED)
    assert {r['side'] for r in records} == {'US', 'USSR'}
    assert len({r['kind'] for r in records}) >= 4
    assert any(r.get('planner_limited', {}).get('truncated') for r in records), 'no truncated planner case'
    assert any('rollout_ranking' in r for r in records)
    assert any('placements' in r for r in records)
    assert any('gains' in r.get('placements', {}) for r in records)


def test_placement_ranking_is_independent_of_python_hash_seed():
    """Unordered adjacency walks used to move record 121 by one ulp and
    reorder Iran/Italy/South Africa between fresh Python processes."""
    root = pathlib.Path(__file__).parents[1]
    probe = """
import gzip, json
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.engine import Engine, Side
with gzip.open(r'%s', 'rt') as stream:
    rec = json.load(stream)['records'][121]
engine = Engine.deserialize(rec['engine'])
bot = StrategicPlayer(StrategicWeights(**rec['weights']),
                      survival_prior=SurvivalPrior(**rec['prior']))
print(json.dumps([a.payload for _key, a in bot.rank_actions(engine.observe(Side(rec['side'])))],
                 sort_keys=True))
""" % CORPUS
    outputs = []
    for seed in ('0', '1', '2'):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(root / 'src'))
        outputs.append(subprocess.check_output([sys.executable, '-c', probe], env=env, text=True))
    assert len(set(outputs)) == 1


def _ranking(ranked):
    return [{'payload': a.payload, 'key': list(key)} for key, a in ranked]


def _same_ranking(got, want):
    if [g['payload'] for g in got] != [w['payload'] for w in want]:
        return 'order'
    for g, w in zip(got, want):
        if len(g['key']) != len(w['key']) or not all(_close(x, y) for x, y in zip(g['key'], w['key'])):
            return ('key', g['payload'], g['key'], w['key'])
    return None


def _replay_probes(planner, probes):
    for op, card, want in probes:
        got = (planner.risk() if op == 'whole_hand' else planner.risk(card) if op == 'risk'
               else planner.event_risk(card) if op == 'event_risk' else bool(planner.hazardous(card)))
        if op == 'hazardous':
            if got != want:
                return (op, card, got, want)
        elif not _close(got, want):
            return (op, card, got, want)
    return None


def test_every_record_pins_every_weight(corpus):
    """A record that omits a weight is not a reproducible record.

    `StrategicWeights(**rec['weights'])` fills anything absent from the
    *current* defaults, so a weight added after capture silently takes
    whatever the code says today -- and the oracle drifts with the thing
    it exists to check. That is not hypothetical: `reply_ops` and
    `reply_model` were added after this corpus was captured, and every
    record reproduced fine until the day `reply_model`'s default changed
    from 0 to 3, at which point 525 records "failed" against behaviour
    they had never recorded.

    The records were backfilled with the values in force at capture
    (`reply_model=0`, the search not yet existing). This test is what
    stops the next weight repeating it: add a field to StrategicWeights
    and the corpus must be told what it was, or re-captured.
    """
    fields = {f.name for f in dataclasses.fields(StrategicWeights)}
    for i, rec in enumerate(corpus['records']):
        missing = sorted(fields - set(rec['weights']))
        extra = sorted(set(rec['weights']) - fields)
        assert not missing and not extra, (
            f'record {i} pins {len(rec["weights"])} of {len(fields)} weights '
            f'(missing {missing}, unknown {extra}). An absent weight is filled '
            f'from the current default, so the record stops meaning what it '
            f'recorded -- backfill it at its capture-time value or re-capture.')


def test_evaluator_and_planner_reproduce_the_corpus(corpus):
    mismatches = []
    for i, rec in enumerate(corpus['records']):
        engine = Engine.deserialize(rec['engine'])
        side = Side(rec['side'])
        obs = engine.observe(side)
        weights = StrategicWeights(**rec['weights'])
        prior = SurvivalPrior(**rec['prior'])
        bot = StrategicPlayer(weights, survival_prior=prior)
        bad = _same_ranking(_ranking(bot.rank_actions(obs)), rec['ranking'])
        if bad:
            mismatches.append((i, 'ranking', bad))
            continue
        nodes = bot._planner.nodes if bot._planner is not None else None
        if nodes != rec['production_nodes']:
            mismatches.append((i, 'production_nodes', nodes, rec['production_nodes']))
        probe = StrategicPlayer(weights, survival_prior=prior)
        probe.rank_actions(obs)
        board = probe.board
        checks = [('country_value', lambda c: probe.country_value(board, c, side)),
                  ('region_score', lambda r: probe.region_score(board, Region[r], side)),
                  ('region_margin', lambda r: probe.region_margin(board, Region[r], side)),
                  ('ops_value', lambda n: probe.ops_value(obs, int(n)))]
        for field, fn in checks:
            for k, v in rec[field].items():
                if not _close(fn(k), v):
                    mismatches.append((i, field, k, fn(k), v))
                    break
        for c, v in rec['event_value']:  # in the recorded order
            got = probe.event_value(obs, c)
            if not _close(got, v):
                mismatches.append((i, 'event_value', c, got, v))
                break
        if 'placements' in rec:
            # Two passes, in the generator's order: every delta, then every
            # investment. Interleaving them warms the per-decision caches
            # differently and moves values in the last bits.
            pl = rec['placements']
            for c in pl['candidates']:
                got = [probe.delta(obs, c, own=k) for k in range(1, pl['ops'] + 1)]
                if not all(_close(a, b) for a, b in zip(got, pl['delta'][c])):
                    mismatches.append((i, 'delta', c, got, pl['delta'][c]))
                    break
            for c in pl['candidates']:
                inv = probe._investment(obs, c, pl['ops'])
                want_gain, want_points = pl['investment'][c]
                if not _close(inv[0], want_gain):
                    mismatches.append((i, 'investment value', c, list(inv), pl['investment'][c]))
                    break
                # The point count is a contract only where the choice is
                # real. `delta` is not a pure function of the board (it
                # reads per-decision caches), so equal-best gains can differ
                # by an ulp between capture and replay and flip
                # `_investment`'s strict `>`. Where the best two gains are
                # that close, either answer reproduces the same value.
                gains = pl.get('gains', {}).get(c) or []
                best = max(gains) if gains else None
                tied = best is not None and sum(1 for g in gains if abs(g - best) <= 1e-12) > 1
                if inv[1] != want_points and not tied:
                    mismatches.append((i, 'investment points', c, list(inv), pl['investment'][c], gains))
                    break
        if 'planner' in rec:
            planner = probe._planner
            assert planner is not None, (i, 'planner missing')
            bad = _replay_probes(planner, rec['planner']['probes'])
            if bad:
                mismatches.append((i, 'planner probe', bad))
            if planner.nodes != rec['planner']['nodes_after_probes'] or \
                    (planner.nodes > planner.prior.max_states) != rec['planner']['truncated']:
                mismatches.append((i, 'planner budget', planner.nodes, rec['planner']['nodes_after_probes']))
        if 'planner_limited' in rec:
            lim = rec['planner_limited']
            limited = StrategicPlayer(weights, survival_prior=SurvivalPrior(**lim['prior']))
            limited.rank_actions(obs)
            bad = _same_ranking(_ranking(limited.rank_actions(obs)), lim['ranking'])
            if bad:
                mismatches.append((i, 'limited ranking', bad))
            bad = _replay_probes(limited._planner, lim['probes'])
            if bad:
                mismatches.append((i, 'limited probe', bad))
            if limited._planner.nodes != lim['nodes_after_probes'] or \
                    (limited._planner.nodes > lim['prior']['max_states']) != lim['truncated']:
                mismatches.append((i, 'limited budget', limited._planner.nodes, lim['nodes_after_probes']))
        if 'rollout_ranking' in rec:
            rollout = RolloutPolicy(weights)
            rollout.reset()
            bad = _same_ranking(_ranking(rollout.rank_actions(obs)), rec['rollout_ranking'])
            if bad:
                mismatches.append((i, 'rollout ranking', bad))
    assert not mismatches, (len(mismatches), mismatches[:8])
