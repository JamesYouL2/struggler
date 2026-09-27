"""Astra's 2026-09-27 audit, the cache defects F3 and F5
(docs/notes/codex/2026-09-27-correctness-rust-readiness.md)."""
from __future__ import annotations

import dataclasses
import gzip
import json
import logging

import pytest

from conftest import ROOT, bare_engine
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic import evaluator as ev
from struggler.engine import Decision, Engine, Side
from struggler.engine.types import DecisionKind as K


def _records(kinds=('place_influence', 'action_round_play', 'ops_type'), n=24):
    recs = json.loads(gzip.open(ROOT / 'tests' / 'corpus' / 'positions.json.gz').read())['records']
    return [r for r in recs if r['kind'] in kinds][:n]


def _ranking(rec):
    logging.getLogger('struggler').setLevel(logging.ERROR)
    engine = Engine.deserialize(rec['engine'])
    return [(key, repr(a.payload)) for key, a in
            StrategicPlayer().rank_actions(engine.observe(Side(rec['side'])))]


# -- F3: switching the snapshot digest off must not change a ranking ---------

def test_rankings_are_the_same_with_the_digest_off(monkeypatch):
    """`STRUGGLER_CHECK_SNAPSHOT=0` zeroes every position digest, and `delta`'s
    memo is keyed on it: different boards shared a key and a placement
    ranking changed (Italy 3.36 against 4.24 in Astra's fixture). The
    documented off switch must be a speed switch only."""
    recs = _records()
    on = [_ranking(r) for r in recs]
    monkeypatch.setattr(ev, 'DIGEST', False)
    off = [_ranking(r) for r in recs]
    assert off == on


# -- F5: the placement memo must key on who is phasing -----------------------

def _late_obs(phasing: Side):
    """Turn 10 AR7, DEFCON 2, a USSR placement of two Ops. Whether the US
    still has a reply depends on whose card this placement belongs to
    (`rules_math.next_move` reads the decision's phasing player)."""
    engine = bare_engine()
    for inf in engine.board.influence.values():
        inf.update(US=0, USSR=0)
    engine.board.influence['Angola'].update(US=0, USSR=1)
    engine.board.influence['Zaire'].update(US=1, USSR=0)
    engine.turn, engine.action_round, engine.defcon, engine.phase = 10, 7, 2, 'action_rounds'
    obs = engine.observe(Side.USSR)
    decision = Decision(1, Side.USSR, K.PLACE_INFLUENCE, (), {'phasing_player': phasing.value, 'ops_remaining': 2})
    return dataclasses.replace(obs, pending_decision=decision)


def test_the_placement_memo_keys_on_the_phasing_side():
    ussr_card, us_card = _late_obs(Side.USSR), _late_obs(Side.US)
    bot = StrategicPlayer()
    bot.prepare(ussr_card)
    bot._placement_values = {}
    bot._placement_ops_value(ussr_card, 2)
    bot.prepare(us_card)           # a fresh ranking: the per-ranking cache is cleared
    bot._placement_values = {}
    reused = bot._placement_ops_value(us_card, 2)
    fresh = StrategicPlayer()
    fresh.prepare(us_card)
    fresh._placement_values = {}
    assert reused == fresh._placement_ops_value(us_card, 2)
