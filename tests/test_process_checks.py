"""Shape 9: a process check that matches the process doing the checking.

`pgrep -f <pattern>` matches full command lines, and the asking process has
one. Four recurrences, all the same bug in different clothes -- a `pkill`
that killed its own shell, a `pgrep -f gate.sh` that reported a gate when
none ran, six `until ! pgrep -f 'pytest -q'` loops that span for hours
because the loop's own `eval` string contained the pattern, and finally a
guard written specifically to avoid this, bracketed as `[g]ate.sh`, which
still matched because the same compound command also contained
`bash -n scripts/gate.sh` in plain text.

That last one is why the bracket trick does not count as a fix: it protects
the pattern from itself and does nothing about the rest of your command
line. `scripts/gate_running.py` is the replacement -- walk /proc, exclude
the whole ancestor chain, match on argv.

These tests reconstruct the defect and require the checker not to fall for
it, in the manner of `test_base_cache_discipline.py`.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import gate_lock_free

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts' / 'gate_running.py'


def test_the_matcher_still_finds_a_real_gate():
    """The other half, and the more dangerous one to get wrong.

    A checker that is too STRICT is worse than one that is too loose: every
    `while gate_running.py; do sleep; done` in the queue scripts would fall
    through instantly, and two gates would run at once on a machine that
    cannot afford it. So the positive cases are pinned beside the negative
    ones rather than trusted.
    """
    sys.path.insert(0, str(CHECKER.parent))
    from gate_running import _names_script  # noqa: PLC0415

    assert _names_script(['bash', 'scripts/gate.sh', '91f26d1'], 'scripts/gate.sh')
    assert _names_script(['bash', 'scripts/gate.sh', '91f26d1'], 'gate.sh')
    assert _names_script(['/bin/bash', 'scripts/morning.sh'], 'morning.sh')
    assert not _names_script(
        ['/bin/bash', '-c', 'until ! python scripts/gate_running.py --match gate.sh; do :; done'],
        'gate.sh')
    assert not _names_script(
        ['/bin/bash', '-c', 'bash -n scripts/gate.sh && echo ok'], 'gate.sh')


def test_a_monitoring_loop_is_not_a_gate():
    """The fifth way into shape 9, and the one that fooled the guard.

    `pids_matching` required argv[0] to be the interpreter, on the theory
    that this separates a script RUNNING from one merely named. It does not.
    A poll loop is

        /bin/bash -c '... gate_running.py --match gate.sh ...'

    whose argv[0] is bash and whose -c body mentions the script, so it passed
    both the interpreter test and the substring test. On 2026-09-12 that
    reported a finished gate as running for a whole session -- to the agent
    that had just written the guard, while reading the log that said the gate
    had finished.

    A `-c` body is program text, not a path, and is never evidence that a
    script is running.
    """
    sys.path.insert(0, str(CHECKER.parent))
    from gate_running import pids_matching  # noqa: PLC0415

    body = ("cd /repo && until ! .venv/bin/python scripts/gate_running.py "
            "--match gate.sh --quiet; do sleep 60; done; tail logs/gate.log")
    # `sleep 30` alone would be EXEC-optimised: bash replaces itself with a
    # single trailing command, the cmdline becomes `sleep 30`, and the test
    # silently stops testing anything. Two commands keep bash alive with
    # its -c body intact, which is the shape being reproduced.
    proc = subprocess.Popen(['/bin/bash', '-c', f': {body}; sleep 30'])
    try:
        # Give the kernel a moment to publish /proc/<pid>/cmdline.
        for _ in range(50):
            if Path(f'/proc/{proc.pid}/cmdline').read_bytes():
                break
            time.sleep(0.02)
        hits = [pid for pid, _ in pids_matching('gate.sh')]
        assert proc.pid not in hits, (
            'a monitoring loop that merely names the gate was reported as one')
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.skipif(not gate_lock_free(),
                    reason='a real gate is running, so "not running" is the wrong answer')
def test_the_checker_does_not_see_itself():
    """The exact failure: a command line that mentions the script."""
    script = (
        f'import sys; sys.path.insert(0, {str(CHECKER.parent)!r});\n'
        'from gate_running import gate_pids;\n'
        'print("RUNNING" if gate_pids() else "not running")'
    )
    # The marker sits in argv, which is what /proc/<pid>/cmdline reports --
    # so a naive pgrep-style check would match this very process.
    done = subprocess.run(
        [sys.executable, '-c', script, 'scripts/gate.sh', 'bash scripts/gate.sh'],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == 'not running', (
        f'the checker matched its own command line: {done.stdout!r}')


def test_pgrep_would_have_been_fooled():
    """The negative control. Without this the test above could pass because
    nothing matched at all, rather than because the exclusion works."""
    marker = 'scripts/gate.sh'
    done = subprocess.run(
        [sys.executable, '-c',
         f'import subprocess,sys;'
         f'r=subprocess.run(["pgrep","-f","{marker}"],capture_output=True,text=True);'
         f'print(len([l for l in r.stdout.split() if l]))',
         marker],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert done.returncode == 0, done.stderr
    assert int(done.stdout.strip()) >= 1, (
        'pgrep -f found nothing, so this control proves nothing -- the '
        'self-match it is meant to demonstrate did not occur')


def test_the_bracket_trick_is_not_a_fix():
    """`[g]ate.sh` is the folk remedy. It fails whenever the command line
    contains the plain string somewhere else, which is how the fourth
    recurrence happened."""
    done = subprocess.run(
        [sys.executable, '-c',
         'import subprocess,sys;'
         'r=subprocess.run(["pgrep","-f","[g]ate.sh"],capture_output=True,text=True);'
         'print(len([l for l in r.stdout.split() if l]))',
         'bash -n scripts/gate.sh'],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert done.returncode == 0, done.stderr
    assert int(done.stdout.strip()) >= 1, (
        'the bracketed pattern matched nothing here; if this ever becomes '
        'true the demonstration is stale, but it does not make the trick safe')
