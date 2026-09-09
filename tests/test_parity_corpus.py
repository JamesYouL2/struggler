"""The parity corpus: every position in tests/corpus/positions.json.gz was
captured from the current evaluator and planner (scripts/capture_corpus.py).
Any refactor of the evaluation path, and any native kernel, must reproduce
these outputs: exact rankings and top actions, values within tolerance,
identical planner risks in the recorded query order, identical truncation
and node counts. Regenerate the corpus only by an explicit commit
(docs/RUST_PORT_PLAN.md, Option C step 1)."""
import gzip
import json
import math
import pathlib

import pytest

from struggler.engine import Engine, Region, Side
from struggler.bots.defcon import SurvivalPrior
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
            pl = rec['placements']
            for c in pl['candidates']:
                got = [probe.delta(obs, c, own=k) for k in range(1, pl['ops'] + 1)]
                if not all(_close(a, b) for a, b in zip(got, pl['delta'][c])):
                    mismatches.append((i, 'delta', c, got, pl['delta'][c]))
                    break
                inv = probe._investment(obs, c, pl['ops'])
                if not (_close(inv[0], pl['investment'][c][0]) and inv[1] == pl['investment'][c][1]):
                    mismatches.append((i, 'investment', c, list(inv), pl['investment'][c]))
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
