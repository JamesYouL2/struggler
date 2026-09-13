"""The card-valuation harvester's held-out verdict (Codex audit F8).

`scripts/harvest_card_valuations.py` certifies a model USABLE before its
proposals for unpriced cards are worth reading. It used to average the error
over whichever held-out calls succeeded: one exact answer and eighteen
failures scored MAE 0.0 and came out USABLE, and one badly wrong card hid
inside a small mean. Every test here runs the real `main` with an injected
fake client -- no network, no key.
"""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import load_script
from struggler.bots.llm.client import LLMResponse

harvest = load_script('harvest_card_valuations')

with open(harvest.VALUATIONS) as _f:
    EXPERT = json.load(_f)
PRICED = {cid: row['ops'] for cid, row in EXPERT['cards'].items() if row.get('ops') is not None}
TOL = EXPERT['tolerance_ops']


class FakeClient:
    """Answers each request through `answer(cid, call_index)`, which returns the
    `ops` value to send or raises. Unpriced cards (the proposals) get 0.0."""
    model_name = 'fake'
    provider_name = 'fake'

    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def complete(self, request):
        content = request.messages[0].content
        cid = next(c for c in harvest.CARDS if harvest.card_text(c) in content)
        index, self.calls = self.calls, self.calls + 1
        ops = self.answer(cid, index) if cid in PRICED else 0.0
        return LLMResponse(structured={'ops': ops, 'note': 'fake'}, raw_text='')


def run(tmp_path, answer):
    out = tmp_path / 'harvest.json'
    code = harvest.main(['--out', str(out), '--limit', '1'], client=FakeClient(answer))
    assert code == 0
    with open(out) as f:
        return json.load(f)


def test_one_exact_answer_and_eighteen_failures_is_not_usable(tmp_path):
    def answer(cid, index):
        if index == 0:
            return PRICED[cid]
        raise RuntimeError('provider down')

    held = run(tmp_path, answer)['held_out']
    assert (held['n'], held['answered'], held['failed']) == (19, 1, 18)
    assert held['mae'] == 0.0 and held['misses'] == 0  # what used to certify it
    assert held['verdict'] == 'NOT USABLE'


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), float('-inf'), 'two', '1.5', True])
def test_a_non_finite_or_non_numeric_answer_is_a_failure(tmp_path, bad):
    def answer(cid, index):
        return bad if index == 0 else PRICED[cid]

    report = run(tmp_path, answer)
    held = report['held_out']
    assert (held['answered'], held['failed']) == (18, 1)
    assert held['mae'] == 0.0 and held['misses'] == 0
    assert held['verdict'] == 'NOT USABLE'
    assert 'ValueError' in report['held_out_failures'][0]['error']


def test_one_badly_wrong_row_among_exact_ones_is_not_usable(tmp_path):
    def answer(cid, index):
        return PRICED[cid] + (5.0 if index == 3 else 0.0)

    held = run(tmp_path, answer)['held_out']
    assert held['mae'] <= TOL  # the mean alone would have passed it
    assert (held['answered'], held['misses'], held['max_error']) == (19, 1, 5.0)
    assert held['verdict'] == 'NOT USABLE'


def test_every_row_answered_inside_tolerance_is_usable(tmp_path):
    def answer(cid, index):
        return PRICED[cid] + (0.9 * TOL if index % 2 else -0.9 * TOL)

    report = run(tmp_path, answer)
    held = report['held_out']
    assert (held['n'], held['answered'], held['failed'], held['misses']) == (19, 19, 0, 0)
    assert held['verdict'] == 'USABLE'
    assert len(report['held_out_rows']) == 19


def test_the_report_can_never_be_written_over_the_reference(tmp_path):
    reference = tmp_path / 'expert_valuations.json'
    shutil.copy(harvest.VALUATIONS, reference)
    before = reference.read_bytes()
    client = FakeClient(lambda cid, index: PRICED[cid])
    code = harvest.main(['--valuations', str(reference), '--out', str(reference)], client=client)
    assert code == 2
    assert client.calls == 0
    assert reference.read_bytes() == before
