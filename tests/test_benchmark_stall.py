"""A stalled benchmark says so, everywhere a verdict is read from.

Codex's audit F4 (docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md):
a stall terminated the pool, wrote the reports and exited 0, and the saved
reports -- rebuilt from their games alone -- carried nothing to say a game had
been abandoned. On 2026-09-12 that happened for real: two gate-ladder rungs
were judged on 255 of 256 games (seed 4006, USSR) and nothing printed a word.
`--stall-timeout 0`, documented as "wait for ever", polled once and stalled.

These drive the real `main` with only the process pool replaced, the way the
audit reproduced it, so the bookkeeping is tested where it lives.
"""
from __future__ import annotations

import json
import multiprocessing

from struggler.bots import benchmark
from test_benchmark import _report


def _game(seed, side, result=1.0):
    return dict(seed=seed, bot_side=side, finished=True, turn=10, reason='vp', result=result,
                signed_vp=5, projected_vp=0.0, defcon=4, seconds=1.0)


class _Results:
    """Hands out `games`, then stalls (or ends, with `stall=False`)."""

    def __init__(self, games, stall=True):
        self.games, self.stall, self.timeouts = list(games), stall, []

    def next(self, timeout=None):
        self.timeouts.append(timeout)
        if self.games:
            return self.games.pop(0)
        if self.stall:
            raise multiprocessing.TimeoutError
        raise StopIteration


def _fake_pool(results):
    class FakePool:
        def __init__(self, workers):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def imap_unordered(self, fn, jobs, chunksize=1):
            return results

        def terminate(self):
            pass
    return FakePool


def _run(tmp_path, monkeypatch, results, *extra):
    monkeypatch.setattr(benchmark, 'Pool', _fake_pool(results))
    # The summary's statistics are not what is under test, and a real one
    # needs every field a played game carries.
    monkeypatch.setattr(benchmark, 'summarize', lambda games, stop_turn: {'games': len(games)})
    report, held = tmp_path / 'gate.json', tmp_path / 'held.json'
    status = benchmark.main(['--bot', 'greedy', '--opponent', 'greedy', '--workers', '1',
                             '--seeds', '4000-4001', '--held-seeds', '5000-5001',
                             '--report', str(report), '--held-report', str(held), *extra])
    return status, json.loads(report.read_text()), json.loads(held.read_text())


def test_a_stall_after_some_games_exits_6_and_marks_every_saved_report(tmp_path, monkeypatch):
    """Timeout AFTER a game completed -- the case the old tests never reached,
    because a stall before the first result has nothing to write."""
    status, report, held = _run(tmp_path, monkeypatch, _Results([_game(4000, 'US')]),
                                '--stall-timeout', '5')
    assert status == 6
    summary = report['summary']
    assert summary['stop_reason'] == 'stalled'
    assert (summary['planned_games'], summary['finished_games']) == (4, 1)
    assert sorted(map(tuple, summary['unfinished'])) == [(4000, 'USSR'), (4001, 'US'), (4001, 'USSR')]
    # The held-out report finished nothing, and must say so rather than vanish.
    assert held['summary']['stop_reason'] == 'stalled'
    assert held['summary']['finished_games'] == 0 and len(held['summary']['unfinished']) == 4


def test_a_complete_run_says_it_was_complete(tmp_path, monkeypatch):
    games = [_game(s, side) for s in (4000, 4001, 5000, 5001) for side in ('US', 'USSR')]
    status, report, _ = _run(tmp_path, monkeypatch, _Results(games, stall=False))
    assert status is None
    assert report['summary']['stop_reason'] is None and report['summary']['unfinished'] == []


def test_a_stall_timeout_of_zero_waits_for_ever(tmp_path, monkeypatch):
    """`next(timeout=0)` polls; the help text promised the opposite."""
    results = _Results([_game(s, side) for s in (4000, 4001, 5000, 5001) for side in ('US', 'USSR')],
                       stall=False)
    status, _, _ = _run(tmp_path, monkeypatch, results, '--stall-timeout', '0')
    assert status is None
    assert results.timeouts and all(t is None for t in results.timeouts)


def test_acceptance_rejects_a_stalled_sample_and_not_an_early_stopped_one():
    wide, held = range(4000, 4048), range(5000, 5048)
    stalled = _report(held, 0.5)
    stalled['summary'].update(stop_reason='stalled', planned_games=98, finished_games=96,
                              unfinished=[[5048, 'US'], [5048, 'USSR']])
    ok, lines = benchmark.acceptance([('gate', _report(wide, 0.5)), ('held-out', stalled)])
    assert not ok and any('FAIL completeness' in line for line in lines), lines
    assert lines[-1] == 'REJECTED'
    # --decide stopping is a verdict the rest provably cannot change: no veto.
    decided = _report(held, 0.5)
    decided['summary']['stop_reason'] = 'decided'
    ok, lines = benchmark.acceptance([('gate', _report(wide, 0.5)), ('held-out', decided)])
    assert ok, lines
