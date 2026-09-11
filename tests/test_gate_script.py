"""`scripts/gate.sh` runs for the better part of an hour, so a mistake in
its first twenty lines is found the better part of an hour late.

Two real ones, both in the same six-line helper added the same day:

- `MACHINE_AT_START=$(machine)` sat above `machine()`'s definition. Bash
  resolves functions at call time, so this is a runtime error and
  `bash -n` accepts it happily. The gate died instantly -- after the wait
  to notice.
- `pgrep -c` prints `0` *and* exits 1 when nothing matches, so the
  `|| echo 0` fallback emitted a second line and the arithmetic saw
  "0\n0". A hand-check passed because processes happened to be running at
  the time; the failing case is the quiet machine.

`--check` runs the setup, the helpers, the snapshots and the worktree,
then exits before the first game. These tests are the cheap half: they
cost a few seconds and catch anything that cannot survive the preamble.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts' / 'gate.sh'


def run_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['bash', str(GATE), '--check', *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)


def test_the_script_is_syntactically_valid():
    done = subprocess.run(['bash', '-n', str(GATE)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.skipif(not (ROOT / '.git').exists(), reason='needs the git history')
def test_the_preamble_runs_end_to_end():
    """Setup, helpers, snapshots, worktree. Anything that would die in the
    first twenty lines dies here in seconds instead of in an hour."""
    done = run_check()
    assert done.returncode == 0, f'stdout:\n{done.stdout}\nstderr:\n{done.stderr}'
    assert 'setup, helpers, snapshots and worktree all fine' in done.stdout
    # The two things the helper got wrong, asserted positively.
    assert 'command not found' not in done.stderr
    assert 'arithmetic syntax error' not in done.stderr


@pytest.mark.skipif(not (ROOT / '.git').exists(), reason='needs the git history')
def test_the_machine_line_reports_one_number_per_field():
    """The `0\\n0` bug produced a multi-line field. One line, three counts."""
    done = run_check()
    line = next(l for l in done.stdout.splitlines() if l.strip().startswith('machine:'))
    assert line.count('load') == 1 and line.count('cores') == 1, line
    import re
    counts = re.findall(r'(-?\d+) other python processes', line)
    assert len(counts) == 1, f'expected one process count, got {counts} in {line!r}'
    assert int(counts[0]) >= 0, f'negative process count: {line!r}'


@pytest.mark.skipif(not (ROOT / '.git').exists(), reason='needs the git history')
def test_the_drift_baseline_resolves():
    """v0.1.0 must still snapshot, or the drift canary silently disables
    itself -- which is how the old anchor ref sat broken and unnoticed."""
    done = run_check()
    assert 'ok=1' in done.stdout, (
        f'the drift baseline did not resolve; the canary would be off.\n{done.stdout}')
