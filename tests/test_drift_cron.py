"""`scripts/drift_cron.sh` decides whether the drift canary runs at all.

The canary was taken out of `gate.sh` because it spent ~17% of every gate on
a reading with no authority over the verdict. That trade is only sound if the
out-of-band check actually happens -- an unrun canary produces the
*appearance* of coverage, which is worse than the cost it saved.

This machine is WSL2 and stops when Windows sleeps, so a plain `0 3 * * *`
fires only if the box is awake at 3am and says nothing when it is not. The
wrapper therefore decides for itself from a staleness stamp, and these tests
pin the decision, because "does it fire?" cannot be checked by reading it.

`--dry-run` with DRIFT_CRON_NOW / DRIFT_CRON_HOUR is the seam.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CRON = ROOT / 'scripts' / 'drift_cron.sh'
STAMP = ROOT / 'logs' / 'drift' / 'LAST_RUN'
NOW = 1_760_000_000          # a fixed epoch; the tests never read the clock
HOUR = 3600


@pytest.fixture
def stamp():
    """Restore whatever the real stamp was -- these tests share a path with a
    live scheduler, and clobbering it would skip or force a real 30-minute run."""
    before = STAMP.read_text() if STAMP.exists() else None
    yield STAMP
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    if before is None:
        STAMP.unlink(missing_ok=True)
    else:
        STAMP.write_text(before)


def decide(stamp_path, age_hours: float | None, hour: int) -> str:
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    if age_hours is None:
        stamp_path.unlink(missing_ok=True)
    else:
        stamp_path.write_text(str(int(NOW - age_hours * HOUR)))
    done = subprocess.run(
        ['bash', str(CRON), '--dry-run'], cwd=ROOT, capture_output=True, text=True,
        timeout=60, env={'PATH': '/usr/bin:/bin', 'HOME': str(Path.home()),
                         'DRIFT_CRON_NOW': str(NOW), 'DRIFT_CRON_HOUR': str(hour)})
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_the_script_is_syntactically_valid():
    done = subprocess.run(['bash', '-n', str(CRON)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize('age_hours,hour,should_run,why', [
    (None, 22, True,  'never run before: must not wait for a 3am that may not come'),
    (0,     4, False, 'just ran: the window must not trigger a second run'),
    (21,   22, False, 'stale but outside the window: wait for 3am rather than '
                      'drifting the run time earlier every day'),
    (21,    4, True,  'the normal path -- in the window, a day since the last'),
    (27,   22, True,  'the catch-up: the machine was asleep at 3am'),
    (19,    4, False, 'in the window but under 20h, so a long-running check '
                      'that finished at 05:30 does not re-fire at 03:00'),
])
def test_the_staleness_decision(stamp, age_hours, hour, should_run, why):
    out = decide(stamp, age_hours, hour)
    ran = out.startswith('would run')
    assert ran is should_run, f'{why}\n  age={age_hours}h hour={hour} -> {out!r}'


def test_a_corrupt_stamp_does_not_wedge_the_scheduler(stamp):
    """A truncated or garbage stamp must read as "never run", not crash or
    parse as a future date -- either would silently stop the canary."""
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text('not-a-number')
    done = subprocess.run(
        ['bash', str(CRON), '--dry-run'], cwd=ROOT, capture_output=True, text=True,
        timeout=60, env={'PATH': '/usr/bin:/bin', 'HOME': str(Path.home()),
                         'DRIFT_CRON_NOW': str(NOW), 'DRIFT_CRON_HOUR': '22'})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith('would run'), done.stdout


def test_it_stays_silent_when_there_is_nothing_to_do(stamp):
    """Hourly cron means 24 invocations a day. If the quiet path printed
    anything, the one line that matters would be buried in noise."""
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(str(NOW))
    done = subprocess.run(
        ['bash', str(CRON)], cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={'PATH': '/usr/bin:/bin', 'HOME': str(Path.home()),
             'DRIFT_CRON_NOW': str(NOW), 'DRIFT_CRON_HOUR': '4'})
    assert done.returncode == 0
    assert done.stdout == '' and done.stderr == '', (done.stdout, done.stderr)
