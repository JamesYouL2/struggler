"""The event-exposure table: which countries each card's event moves.

`scripts/probe_event_exposure.py` derives it by firing every event on
random boards, and `src/struggler/bots/strategic/event_exposure.json` is
its output. The table must be COMPLETE -- the maintainer's condition for
pricing it (2026-09-26) -- and must be what the probe produces from the
engine as it is now, or an event rewritten in `engine/events.py` would keep
its old targets in the bot.
"""
from __future__ import annotations

import json
import sys

from conftest import ROOT
from struggler.engine.cards import load_cards
from struggler.engine.events import EVENTS

TABLE = ROOT / 'src' / 'struggler' / 'bots' / 'strategic' / 'event_exposure.json'
sys.path.insert(0, str(ROOT / 'scripts'))
import probe_event_exposure  # noqa: E402


def _table():
    return json.loads(TABLE.read_text())


def test_every_card_with_an_event_is_in_the_table_and_fired():
    cards = load_cards()
    table = _table()['cards']
    expected = {cid for cid, c in cards.items() if not c.scoring and cid in EVENTS}
    assert set(table) == expected
    never = sorted(cid for cid, row in table.items() if row['fired'] == 0)
    assert not never, f'never fired on any probe board, so their targets are unknown: {never}'


def test_the_table_is_what_the_probe_derives_from_the_engine_now():
    data = _table()
    assert probe_event_exposure.probe(data['trials'], data['seed']) == data['cards'], (
        'event_exposure.json is stale: re-run scripts/probe_event_exposure.py --out '
        'src/struggler/bots/strategic/event_exposure.json')


def test_the_maintainers_examples_are_fixed_targets():
    """Vietnam less than Laos (Vietnam Revolts), South Korea less than North
    Korea (Korean War), Egypt less than Libya (Nasser)."""
    table = _table()['cards']
    assert table['Vietnam_Revolts']['exposure'] == {'Vietnam': 1.0}
    assert table['Korean_War']['exposure'] == {'South_Korea': 1.0}
    assert table['Nasser']['exposure'] == {'Egypt': 1.0}
    for card in ('Vietnam_Revolts', 'Korean_War', 'Nasser'):
        assert not {'Laos_Cambodia', 'North_Korea', 'Libya'} & set(table[card]['exposure'])
