#!/usr/bin/env python
"""Is a gate actually running? Not `pgrep -f gate.sh`, which matches the
asking process whenever its own command line mentions the script -- four
times, in four disguises -- shape 9 in docs/notes/claude/bug-shapes.md. Walk /proc, and exclude our own
ancestry explicitly."""
import os, pathlib

def ancestors(pid):
    seen = set()
    while pid and pid not in seen:
        seen.add(pid)
        try:
            stat = pathlib.Path(f'/proc/{pid}/status').read_text()
        except OSError:
            break
        ppid = next((int(l.split()[1]) for l in stat.splitlines()
                     if l.startswith('PPid:')), 0)
        pid = ppid
    return seen

def gate_pids():
    mine = ancestors(os.getpid())
    out = []
    for entry in pathlib.Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in mine:
            continue
        try:
            cmd = (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
        except OSError:
            continue
        # the gate runs as `bash scripts/gate.sh ...`
        if 'scripts/gate.sh' in cmd and cmd.split()[0].endswith('bash') \
           and '-n' not in cmd.split()[:2]:
            out.append((pid, cmd.strip()))
    return out

if __name__ == '__main__':
    found = gate_pids()
    for pid, cmd in found:
        print(f'{pid}: {cmd[:90]}')
    print('RUNNING' if found else 'not running')
