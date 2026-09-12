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


def _names_script(parts: list[str], substring: str) -> bool:
    """Whether `substring` appears as an ARGUMENT, not merely in the text.

    This is the whole difference between a script running and a command line
    that talks about one. `substring in ' '.join(parts)` cannot tell them
    apart, and requiring argv[0] to be an interpreter does not help: a
    monitoring loop is

        /bin/bash -c '... gate_running.py --match gate.sh ...'

    whose argv[0] IS bash and whose -c body mentions the script. That reported
    a finished gate as running for a whole session on 2026-09-12, including to
    the agent that wrote the guard. Shape 9, and the fifth way in.

    So: match whole argv elements, and never look inside a `-c` body, which is
    a program text rather than a path.
    """
    skip = -1
    for idx, part in enumerate(parts):
        if idx == skip:
            continue
        if part == '-c':
            skip = idx + 1          # the next element is source, not a path
            continue
        if part == substring or part.endswith('/' + substring):
            return True
        if os.path.basename(part) == substring:
            return True
    return False


def pids_matching(substring: str, interpreter: str | None = 'bash') -> list[tuple[int, str]]:
    """Processes running `substring` as a script, excluding our own ancestry.

    `interpreter` requires argv[0] to end with it; `_names_script` requires
    the script to be an argument rather than text anywhere on the line. Both
    are needed -- argv[0] alone admits `bash -c` wrappers, and the element
    check alone would admit `bash -n scripts/gate.sh`. Pass None to match any
    argv[0].
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
        if not parts or not _names_script(parts, substring):
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
