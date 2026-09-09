"""The parity corpus: every position in tests/corpus/positions.json.gz was
captured from the current evaluator and planner (scripts/capture_corpus.py).
Any refactor of the evaluation path, and any native kernel, must reproduce
these outputs: exact rankings and top actions, values within tolerance,
identical planner risks. Regenerate the corpus only by an explicit commit
(docs/RUST_PORT_PLAN.md, Option C step 1)."""
import gzip
import json
import math
import pathlib

import pytest

from struggler.engine import Engine, Region, Side
from struggler.bots.strategic import StrategicPlayer

CORPUS = pathlib.Path(__file__).parent / 'corpus' / 'positions.json.gz'
ABS, REL = 1e-9, 1e-9


def _records():
    with gzip.open(CORPUS, 'rt') as f:
        return json.load(f)['records']


def _close(a, b):
    return math.isclose(a, b, rel_tol=REL, abs_tol=ABS)


@pytest.fixture(scope='module')
def records():
    return _records()


def test_corpus_is_present_and_varied(records):
    assert len(records) > 200
    assert {r['side'] for r in records} == {'US', 'USSR'}
    assert len({r['kind'] for r in records}) >= 4
    assert len({r['turn'] for r in records}) >= 3


def test_evaluator_and_planner_reproduce_the_corpus(records):
    mismatches = []
    for i, rec in enumerate(records):
        engine = Engine.deserialize(rec['engine'])
        side = Side(rec['side'])
        obs = engine.observe(side)
        bot = StrategicPlayer()
        ranked = bot.rank_actions(obs)
        got = [{'payload': a.payload, 'key': list(key)} for key, a in ranked]
        want = rec['ranking']
        if [g['payload'] for g in got] != [w['payload'] for w in want]:
            mismatches.append((i, 'ranking order'))
            continue
        for g, w in zip(got, want):
            if not all(_close(x, y) for x, y in zip(g['key'], w['key'])):
                mismatches.append((i, 'safety key', g['payload'], g['key'], w['key']))
                break
        board = bot.board
        for c, v in rec['country_value'].items():
            if not _close(bot.country_value(board, c, side), v):
                mismatches.append((i, 'country_value', c))
                break
        for r, v in rec['region_score'].items():
            if not _close(bot.region_score(board, Region[r], side), v):
                mismatches.append((i, 'region_score', r))
                break
        for r, v in rec['region_margin'].items():
            if not _close(bot.region_margin(board, Region[r], side), v):
                mismatches.append((i, 'region_margin', r))
                break
        for n, v in rec['ops_value'].items():
            if not _close(bot.ops_value(obs, int(n)), v):
                mismatches.append((i, 'ops_value', n))
                break
        planner = bot._planner
        if 'planner' in rec:
            assert planner is not None, (i, 'planner missing')
            p = rec['planner']
            if not _close(planner.risk(), p['whole_hand_risk']):
                mismatches.append((i, 'whole_hand_risk'))
            for c, v in p['card_risk'].items():
                if not _close(planner.risk(c), v):
                    mismatches.append((i, 'card_risk', c))
                    break
            for c, v in p['hazardous'].items():
                if bool(planner.hazardous(c)) != v:
                    mismatches.append((i, 'hazardous', c))
                    break
    assert not mismatches, mismatches[:10]
