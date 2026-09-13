"""An event simulation must not re-enter itself through the helper chain.

`event_value` guards against re-entry: a card already being simulated gets
the shallow Ops estimate the second time. But the sandbox plays an event's
decisions with `_event_helper`, a separate `StrategicPlayer`, which builds its
own helper in turn -- and each of those players started with an EMPTY guard.
So Blockade's discard choice priced `hold_value`, which asked `un_card` about
every opponent card in hand, which simulated Blockade again on the next
helper down, about 65 times, until RecursionError; the event was then priced
by the generic estimate. With a different branching factor the same chain ran
for minutes instead, and hung a gate game (seed 4006).

It shipped twice: Latin American Debt Crisis first (patched by never
simulating that one card, which left the loop), then Blockade and ABM Treaty.
See docs/notes/claude/2026-09-12-the-blockade-recursion-is-a-chain-of-fresh-helpers.md.

The fixture is a real position, extracted from the self-play game that hit
it (seed 9003, turn 3, the US headline, UN Intervention and Blockade both in
hand) by `logs/blockade-fixture/extract.py`. A hand-built position did not
reproduce it: the loop runs through the safety ranking, which a bare
constructed board does not reach.
"""
from __future__ import annotations

import json
import logging

from conftest import ROOT
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Engine, Side

FIXTURE = ROOT / 'tests' / 'fixtures' / 'blockade_recursion_seed9003.json'


def test_blockade_does_not_recurse_through_the_helper_chain(caplog):
    record = json.loads(FIXTURE.read_text())
    engine = Engine.deserialize(record['engine'])
    side = Side(record['side'])
    obs = engine.observe(side)
    assert 'Blockade' in obs.hand and 'UN_Intervention' in obs.hand, 'the fixture lost its trigger'
    bot = StrategicPlayer(openings=record['books'])
    with caplog.at_level(logging.WARNING, logger='struggler'):
        bot.rank_actions(obs)
    failures = [r.getMessage() for r in caplog.records if 'failed in the sandbox' in r.getMessage()]
    assert not failures, failures
