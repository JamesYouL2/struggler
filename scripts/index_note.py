#!/usr/bin/env python
"""Insert a note's index line into its tree's README.md. Idempotent.

Every writer under `scripts/` that drops a note into `docs/notes/claude/`
runs this before the note's commit, so the index line lands in the same
commit. `tests/test_agent_files.py` requires every top-level note to be
indexed; eighteen generated notes predate that gate and were indexed
retroactively on 2026-09-22.

    python scripts/index_note.py docs/notes/claude/2026-09-22-foo.md --generated

The title is the note's first `# ` line (its stem if it has none) and the
date is the note's `YYYY-MM-DD` filename prefix. A note that is already
linked is left alone, so re-running after an interrupted queue is safe.
"""
from __future__ import annotations

import argparse
import pathlib
import re

DATE_PREFIX = re.compile(r'(\d{4}-\d{2}-\d{2})')


def index_note(path: pathlib.Path, generated: bool = False) -> bool:
    """Add `path`'s bullet to its README. True if inserted, False if already there."""
    path = pathlib.Path(path)
    readme = path.parent / 'README.md'
    text = readme.read_text()
    if f'({path.name})' in text:
        return False
    title = path.stem
    for line in path.read_text().splitlines():
        if line.startswith('# '):
            title = line[2:].strip()
            break
    match = DATE_PREFIX.match(path.name)
    date = f' — {match.group(1)}' if match else ''
    suffix = ' (generated)' if generated else ''
    bullet = f'- [{title}]({path.name}){date}{suffix}\n'
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith('- ['):
            lines.insert(i, bullet)
            break
    else:
        raise SystemExit(f'{readme}: no "- [" bullet found to insert before')
    readme.write_text(''.join(lines))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('note')
    ap.add_argument('--generated', action='store_true',
                    help='mark the bullet "(generated)"')
    a = ap.parse_args(argv)
    inserted = index_note(pathlib.Path(a.note), generated=a.generated)
    print(f'{a.note}: {"indexed" if inserted else "already indexed"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
