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
LIB = ROOT / 'scripts' / 'lib' / 'gate_common.sh'


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
    # And the third, found by --check on 2026-09-11: `load` is a gawk builtin,
    # so `awk -v load=` aborted the contention verdict with a fatal error.
    assert 'gawk' not in done.stderr, done.stderr


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
def test_the_check_run_reports_a_contention_verdict():
    """--check must exercise sample_machine and contention_verdict, or the
    dry run stops covering the helpers it exists to cover."""
    done = run_check()
    line = next((l for l in done.stdout.splitlines()
                 if l.strip().startswith('contention:')), None)
    assert line is not None, f'no contention line in --check output:\n{done.stdout}'
    assert 'clean' in line or 'CONTENDED' in line, line


def test_the_contention_verdict_decides_on_load_not_process_count():
    """The verdict must not fire on idle editor python.

    Measured on the maintainer's machine, VS Code alone sits at 4-5 python
    processes (pylance, the env server) that consume no cores. The first
    version of this flagged `foreign > 0`, which would have marked every
    single run contended -- and a flag that is always on is a flag nobody
    reads. Load is what moves the clock; process count is context.
    """
    def verdict(peak_load, foreign, workers=8):
        script = (f'set -euo pipefail\n. {LIB}\n'
                  f'PEAK_LOAD={peak_load}\nPEAK_OTHER={foreign}\n'
                  f'contention_verdict {workers}\n')
        done = subprocess.run(['bash', '-c', script], capture_output=True,
                              text=True, cwd=ROOT)
        assert done.returncode == 0, done.stderr
        assert 'gawk' not in done.stderr, f'awk rejected a variable: {done.stderr}'
        return done.stdout

    assert verdict('0.40', 5).startswith('clean'), 'idle editor python is not contention'
    assert verdict('8.50', 0).startswith('clean'), 'a gate at its own 8 workers is not contended'
    assert verdict('14.0', 0).startswith('CONTENDED'), 'load far above the workers is'
    assert verdict('14.0', 3).startswith('CONTENDED')


def test_sample_machine_survives_a_quiet_machine():
    """`[ cond ] && assign` returns 1 when the condition is false, and under
    `set -e` that kills the caller. The condition is false exactly when
    nothing else is running -- so without the trailing `return 0` this aborts
    on a QUIET machine and passes every hand check on a busy one. That is the
    same shape as the `pgrep -c` bug this file already gates, and it was
    verified to abort before the `return 0` was added.
    """
    script = (f'set -euo pipefail\n. {LIB}\n'
              'PEAK_OTHER=999999\n'   # force the comparison false
              'sample_machine\n'
              'echo survived\n')
    done = subprocess.run(['bash', '-c', script], capture_output=True,
                          text=True, cwd=ROOT)
    assert 'survived' in done.stdout, (
        f'sample_machine aborted under set -e on a quiet machine.\n{done.stderr}')


def test_the_gate_does_not_redefine_what_the_library_owns():
    """One copy of `snapshot`. It has three hard-won details in it (the
    `rm -rf`, `--strip-components`, the pre-split check) and a second copy
    would be shape 4 -- two implementations of one rule, four recurrences."""
    gate = GATE.read_text()
    for name in ('snapshot', 'machine', 'sample_machine', 'contention_verdict'):
        assert f'\n{name}() {{' not in gate, (
            f'{name}() is defined in gate.sh as well as scripts/lib/gate_common.sh')
    assert 'scripts/lib/gate_common.sh' in gate, 'gate.sh must source the library'


def test_the_drift_canary_is_no_longer_in_the_gate():
    """It moved to scripts/drift_check.sh on 2026-09-11. It never decided
    anything -- acceptance runs against HEAD~1 and never saw it -- and it cost
    the verdict 16 seeds, which left early stopping only 5 seeds of headroom."""
    gate = GATE.read_text()
    assert 'GATE_ANCHOR' not in gate and '3c. drift' not in gate, (
        'the drift canary is back in gate.sh')
    assert 'HELD=${4:-5000-5063}' in gate, (
        'the 16 seeds the canary cost the verdict were not given back')
    assert (ROOT / 'scripts' / 'drift_check.sh').exists()
