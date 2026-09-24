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
    return {'seed': seed, 'bot_side': side, 'finished': True, 'turn': 10, 'reason': 'vp', 'result': result,
            'signed_vp': 5, 'projected_vp': 0.0, 'defcon': 4, 'seconds': 1.0}


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


def _run_reserve(tmp_path, monkeypatch, results, seeds, reserve):
    """One sample with a tail reserve -- what a shard actually runs."""
    monkeypatch.setattr(benchmark, 'Pool', _fake_pool(results))
    monkeypatch.setattr(benchmark, 'summarize', lambda games, stop_turn: {'games': len(games)})
    report = tmp_path / 'shard.json'
    status = benchmark.main(['--bot', 'greedy', '--opponent', 'greedy', '--workers', '1',
                             '--seeds', seeds, '--reserve-seeds', reserve,
                             '--report', str(report)])
    return status, json.loads(report.read_text())


def test_a_lost_core_game_is_backfilled_and_the_report_reads_complete(tmp_path, monkeypatch):
    """The 255-of-256 fix: a core game never finishes, the reserve
    backfills it, and the shard delivers its full count -- exit 0 and a
    COMPLETE report, so the shard is cacheable instead of replayed for
    ever."""
    games = [_game(4000, 'US'), _game(4000, 'USSR'), _game(4001, 'US'),
             _game(5000, 'US'), _game(5000, 'USSR'), _game(5001, 'US'), _game(5001, 'USSR')]
    status, report = _run_reserve(tmp_path, monkeypatch, _Results(games),
                                  '4000-4001', '5000-5001')
    assert status is None, 'a full count delivered is not a partial shard'
    assert report['summary']['stop_reason'] is None, (
        'the report must read complete: it is what acceptance judges')
    assert report['summary']['backfilled_pairs'] == [5000]
    assert report['summary']['spare_games'] == 3
    assert sorted({g['seed'] for g in report['games']}) == [4000, 5000]
    assert report['summary']['finished_games'] == 4


def test_the_satisfied_stop_abandons_only_spare_work(tmp_path, monkeypatch):
    """Every core game in and the count met: the stop abandons spare work
    and nothing else. A spare that finished EARLY is still dropped -- the
    counted set is the core by seed order, not whatever landed."""
    games = [_game(4000, 'US'), _game(4000, 'USSR'), _game(5000, 'US'),
             _game(4001, 'US'), _game(4001, 'USSR')]
    status, report = _run_reserve(tmp_path, monkeypatch, _Results(games, stall=False),
                                  '4000-4001', '5000-5001')
    assert status is None
    assert report['summary']['stop_reason'] == 'satisfied'
    assert sorted({g['seed'] for g in report['games']}) == [4000, 4001]
    assert report['summary']['spare_games'] == 1
    assert report['summary']['backfilled_pairs'] == []


def test_without_a_reserve_a_stall_is_still_a_partial_shard(tmp_path, monkeypatch):
    """The pre-reserve behaviour, pinned: no reserve, no rescue."""
    games = [_game(4000, 'US'), _game(4000, 'USSR'), _game(4001, 'US')]
    monkeypatch.setattr(benchmark, 'Pool', _fake_pool(_Results(games)))
    monkeypatch.setattr(benchmark, 'summarize', lambda games, stop_turn: {'games': len(games)})
    report = tmp_path / 'shard.json'
    status = benchmark.main(['--bot', 'greedy', '--opponent', 'greedy', '--workers', '1',
                             '--seeds', '4000-4001', '--report', str(report)])
    assert status == 6
    assert json.loads(report.read_text())['summary']['stop_reason'] == 'stalled'


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


def test_a_stall_marks_only_the_sample_that_lost_games(tmp_path, monkeypatch):
    """The run stalls, but every game of the verdict sample finished first.
    Stamping the run's stop_reason on both reports failed a complete sample:
    on 2026-09-13 CI's held-out reports read "stalled after 128 of 128 games;
    unfinished []" and failed completeness, because the *other* arm hung on
    seed 4006 (run 34753464219, bases bc5ef93 and c0ccd95)."""
    games = [_game(s, side) for s in (4000, 4001) for side in ('US', 'USSR')]
    status, report, held = _run(tmp_path, monkeypatch, _Results(games), '--stall-timeout', '5')
    assert status == 6, 'the run still stalled, and says so'
    assert report['summary']['stop_reason'] is None and report['summary']['unfinished'] == []
    assert held['summary']['stop_reason'] == 'stalled' and len(held['summary']['unfinished']) == 4


def test_acceptance_does_not_fail_a_stamped_report_that_lost_nothing():
    """Reports CI already wrote carry the run-wide stamp. One whose games all
    finished is a complete sample whatever the stamp says."""
    wide, held = range(4000, 4048), range(5000, 5048)
    whole = _report(held, 0.5)
    whole['summary'].update(stop_reason='stalled', planned_games=96, finished_games=96, unfinished=[])
    ok, lines = benchmark.acceptance([('gate', _report(wide, 0.5)), ('held-out', whole)])
    assert ok and not any('FAIL completeness' in line for line in lines), lines


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


# --- the wall-clock ceiling ---------------------------------------------
#
# `--stall-timeout` measures the GAP BETWEEN FINISHES, and its floor adapts to
# `8 * slowest game so far`, so it puts no ceiling on the run at all: one
# ten-minute game lifts the floor to eighty minutes. `fit-bc-base [5/8]`
# (seeds 64640-64767) ran 1h51m on one dispatch and hit the runner's own
# 180-minute JOB timeout on the next -- and a job timeout kills the process
# before any report is written, so the shard yielded NOTHING both times where
# a stall would have yielded a partial report that still pools.
#
# `--max-seconds` is that ceiling. The tests below are about the difference
# between the two, because conflating them is what made the slice unmeasurable.

def test_the_ceiling_clamps_the_adaptive_stall_floor(tmp_path, monkeypatch):
    """THE ONE THAT MATTERS. A deadline checked only between finishes would be
    useless in the case it exists for: the run is stuck *inside* `next`,
    waiting out a floor the slowest game has already stretched past the
    deadline. A 1000-second game lifts the floor to 8000s; with 60 seconds of
    budget left the wait must be about 60, not 8000."""
    results = _Results([_game(4000, 'US')])
    results.games[0]['seconds'] = 1000.0
    _run(tmp_path, monkeypatch, results, '--stall-timeout', '1200', '--max-seconds', '60')
    assert results.timeouts[-1] is not None
    assert results.timeouts[-1] <= 60, (
        f'the wait was {results.timeouts[-1]}s with 60s of budget: the adaptive '
        f'floor (8 x 1000s) escaped the ceiling, which is the whole defect')


def test_an_expired_budget_exits_6_and_writes_the_partial_report(tmp_path, monkeypatch):
    """The point of the flag: lose the games, keep the report. A job timeout
    keeps neither."""
    status, report, held = _run(tmp_path, monkeypatch, _Results([_game(4000, 'US')]),
                                '--stall-timeout', '1200', '--max-seconds', '1')
    assert status == 6, 'an abandoned run is neither a verdict nor a crash'
    summary = report['summary']
    assert summary['stop_reason'] == 'expired'
    assert (summary['planned_games'], summary['finished_games']) == (4, 1)
    assert sorted(map(tuple, summary['unfinished'])) == [(4000, 'USSR'), (4001, 'US'), (4001, 'USSR')]
    assert held['summary']['stop_reason'] == 'expired'


def test_the_reason_distinguishes_the_ceiling_from_a_stall(tmp_path, monkeypatch):
    """Both abandon the run; they diagnose different things. A stall says one
    game hangs, an expiry says the whole slice is slow, and reading the second
    as the first is how the floor got raised instead of capped."""
    _, slow_game, _ = _run(tmp_path, monkeypatch, _Results([_game(4000, 'US')]),
                           '--stall-timeout', '5', '--max-seconds', '600')
    assert slow_game['summary']['stop_reason'] == 'stalled', (
        'budget to spare and nothing finishing is a stall')
    _, out_of_time, _ = _run(tmp_path, monkeypatch, _Results([_game(4000, 'US')]),
                             '--stall-timeout', '600', '--max-seconds', '1')
    assert out_of_time['summary']['stop_reason'] == 'expired', (
        'the wait was cut short by the ceiling, so nothing was shown about the floor')


def test_no_ceiling_by_default_so_nothing_that_does_not_ask_changes(tmp_path, monkeypatch):
    results = _Results([_game(s, side) for s in (4000, 4001, 5000, 5001)
                        for side in ('US', 'USSR')], stall=False)
    status, report, _ = _run(tmp_path, monkeypatch, results, '--stall-timeout', '1200')
    assert status is None
    assert report['summary']['stop_reason'] is None
    assert all(t == 1200 for t in results.timeouts), (
        'an unset --max-seconds must leave the stall floor exactly as it was')


def test_a_run_inside_its_budget_is_judged_by_the_stall_floor(tmp_path, monkeypatch):
    results = _Results([_game(s, side) for s in (4000, 4001, 5000, 5001)
                        for side in ('US', 'USSR')], stall=False)
    status, report, _ = _run(tmp_path, monkeypatch, results, '--stall-timeout', '30',
                             '--max-seconds', '100000')
    assert status is None and report['summary']['stop_reason'] is None
    assert all(t == 30 for t in results.timeouts), (
        'a budget far from expiry must not shorten the stall floor')


def test_acceptance_rejects_an_expired_sample_exactly_as_a_stalled_one():
    """`INCOMPLETE` is one tuple for one reason: an expired budget censors the
    sample the same way a stall does -- how long a game runs depends on the
    candidate and the position, so the abandoned games are the ones most
    likely to have differed."""
    wide, held = range(4000, 4048), range(5000, 5048)
    expired = _report(held, 0.5)
    expired['summary'].update(stop_reason='expired', planned_games=98, finished_games=96,
                              unfinished=[[5047, 'US'], [5047, 'USSR']])
    ok, lines = benchmark.acceptance([('gate', _report(wide, 0.5)), ('held-out', expired)])
    assert not ok
    assert any('FAIL completeness' in line and 'expired' in line for line in lines), lines


def test_an_expired_report_that_lost_nothing_is_not_stamped(tmp_path, monkeypatch):
    """The per-sample rule from the stall case applies here too: a sample whose
    games all finished is complete, whatever the other arm did."""
    games = [_game(s, side) for s in (4000, 4001) for side in ('US', 'USSR')]
    status, report, held = _run(tmp_path, monkeypatch, _Results(games),
                                '--stall-timeout', '600', '--max-seconds', '1')
    assert status == 6
    assert report['summary']['stop_reason'] is None and report['summary']['unfinished'] == []
    assert held['summary']['stop_reason'] == 'expired'


def test_the_abandoned_seeds_are_named_on_stderr_not_only_in_the_report(tmp_path, monkeypatch, capsys):
    """A report has to be downloaded and an artifact is not always reachable;
    the log is. Which seeds a slice hangs on is the whole diagnosis -- finding
    the game inside `fit-bc-base [5/8]` would otherwise mean dispatching a
    bisect."""
    _run(tmp_path, monkeypatch, _Results([_game(4000, 'US')]),
         '--stall-timeout', '600', '--max-seconds', '1')
    err = capsys.readouterr().err
    assert 'EXPIRED: 7 game(s) never finished' in err, err
    for named in ('4000/USSR', '4001/US', '5000/US', '5001/USSR'):
        assert named in err, f'{named} was abandoned and not named:\n{err}'


def test_a_negative_ceiling_is_refused(tmp_path, monkeypatch):
    import pytest
    with pytest.raises(SystemExit):
        _run(tmp_path, monkeypatch, _Results([]), '--max-seconds', '-1')
