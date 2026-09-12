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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts' / 'gate_running.py'


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
