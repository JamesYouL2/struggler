"""The annotated positions: the maintainer's move, asked of the shipped bot.

docs/EXPERT_ASKS.md, "The other thing, which is not a price": the mirror
gate plays the bot against itself, so a mistake both seats make scores a
dead heat, and it needs ~96 seeds to see a six-point swing. A position the
maintainer has marked sees both, in a second.

Each fixture entry is a real position from the bot's own self-play (an
engine serialized mid-decision), the moves the maintainer accepts, and one
line of why. The test asks the current bot for its move and checks it is
among them. A miss the bot is known to make is a strict xfail naming the
missing idea, so fixing it flips the test and removing the xfail is part of
the fix -- the same shape as the value-sign and recurring-defect gates.

Fixtures: tests/fixtures/positions/annotated-*.json (made by hand from
scripts/position_pack.py's picks; see
docs/notes/claude/2026-09-26-the-first-annotated-positions.md).
"""
from __future__ import annotations

import json
import logging

import pytest

from conftest import ROOT
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Engine, Side

FIXTURES = sorted((ROOT / 'tests' / 'fixtures' / 'positions').glob('annotated-*.json'))

# Known misses, each with the idea the bot lacks. Strict: a fix must remove it.
KNOWN_MISSES = {
    'p1-card': 'spends the China Card on a non-Asia coup; a 2-Op card does the job',
    'p1-coup': 'couped Angola, not Nigeria (the maintainer paired Nigeria with the right card)',
    'p3-place': 'places into Vietnam with Vietnam Revolts still in the deck; opponent events aimed at a country are unpriced',
    'p4-coup': 'coups Angola where its own Portuguese Empire Crumbles already reaches; own-hand event overlap is unpriced',
}


def _positions():
    for path in FIXTURES:
        for pos in json.loads(path.read_text())['positions']:
            marks = ([pytest.mark.xfail(strict=True, reason=KNOWN_MISSES[pos['id']])]
                     if pos['id'] in KNOWN_MISSES else [])
            yield pytest.param(pos, id=pos['id'], marks=marks)


def test_the_fixtures_exist():
    assert FIXTURES, 'no annotated position fixtures found'


@pytest.mark.parametrize('pos', list(_positions()))
def test_the_bot_plays_a_move_the_maintainer_accepts(pos):
    logging.getLogger('struggler').setLevel(logging.ERROR)
    engine = Engine.deserialize(pos['engine'])
    decision = engine.pending_decision
    assert decision is not None and decision.actor is Side(pos['side'])
    assert decision.kind.name.lower() == pos['kind'], 'the fixture no longer lands on its decision'
    action = StrategicPlayer().choose_action(engine.observe(Side(pos['side'])), [])
    assert action.payload in pos['accept'], (
        f"{pos['id']}: bot plays {action.payload}; the maintainer accepts {pos['accept']} -- {pos['why']}")
