#!/usr/bin/env python
"""Is a named process actually running?

Not `pgrep -f <pattern>`, which matches the asking process whenever its own
command line mentions the pattern -- four recurrences, shape 9 in
docs/notes/claude/bug-shapes.md, including a guard written specifically to
prevent it (`[g]ate.sh` still matched, because the same command line also
contained `bash -n scripts/gate.sh` in plain text). Bracketing protects the
pattern from itself and does nothing about the rest of your command line.

Walk /proc instead, and exclude the whole ancestor chain explicitly.

    python scripts/gate_running.py                     # is a gate running?
    python scripts/gate_running.py --match overnight.sh
Exit status is the answer: 0 if something matched, 1 if nothing did, so it
reads naturally in a shell `while` loop.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys


def ancestors(pid: int) -> set[int]:
    """Every process from `pid` up to init. Excluding only our own PID is not
    enough: the shell that launched us has the same command line."""
    seen: set[int] = set()
    while pid and pid not in seen:
        seen.add(pid)
        try:
            status = pathlib.Path(f'/proc/{pid}/status').read_text()
        except OSError:
            break
        pid = next((int(l.split()[1]) for l in status.splitlines()
                    if l.startswith('PPid:')), 0)
    return seen


def pids_matching(substring: str, interpreter: str | None = 'bash') -> list[tuple[int, str]]:
    """Processes whose argv contains `substring`, excluding our own ancestry.

    `interpreter` requires argv[0] to end with it, which is what separates a
    script that is *running* from one merely named on a command line -- the
    `bash -n scripts/gate.sh` case. Pass None to match any argv[0].
    """
    mine = ancestors(os.getpid())
    found = []
    for entry in pathlib.Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) in mine:
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        parts = [a.decode('utf-8', 'replace') for a in argv if a]
        if not parts or substring not in ' '.join(parts):
            continue
        if interpreter and not parts[0].endswith(interpreter):
            continue
        if '-n' in parts[1:2]:       # `bash -n` is a syntax check, not a run
            continue
        found.append((int(entry.name), ' '.join(parts)))
    return found


def gate_pids() -> list[tuple[int, str]]:
    """The gate specifically. Kept as a name because callers and
    tests/test_process_checks.py use it."""
    return pids_matching('scripts/gate.sh')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--match', default='scripts/gate.sh')
    ap.add_argument('--any-interpreter', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)
    found = pids_matching(a.match, None if a.any_interpreter else 'bash')
    if not a.quiet:
        for pid, cmd in found:
            print(f'{pid}: {cmd[:100]}')
        print('RUNNING' if found else 'not running')
    return 0 if found else 1


if __name__ == '__main__':
    sys.exit(main())
