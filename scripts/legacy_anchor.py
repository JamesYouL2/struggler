#!/usr/bin/env python
"""Play the current bot against a strategic bot from before the package split.

The gate and the drift canary snapshot `bots/strategic/policy.py`, which only
exists from 136a8c6 (2026-09-10 07:07). Before that the strategic bot was a
flat `bots/strategic.py`, and it cannot go through `benchmark.load_module`:
the loader substitutes the snapshot's modules only while the baseline file
imports, and undoes every substitution afterwards -- on purpose, pinned by
two tests, because a leak once let a gate compare a change against itself.
The old bot imports `struggler.bots.public_cards` *inside a function*, after
that undo, and today's package has no such module (it moved under
`strategic/`), so it died mid-game with ModuleNotFoundError. Leaving the old
modules registered fixed that and broke the contract, and was reverted.

This leaves the loader alone and moves the old bot instead. The revision's
`bots/` is extracted as its own package, `legacy_<sha>`, and every
`struggler.bots` reference in it is rewritten to that name. The old bot then
resolves all of its own modules, lazily or not, without ever touching
`struggler.bots`; it still plays through today's engine, which a one-seed
smoke on 372609e and a84593a showed it can. A tiny entry file exposes its
`StrategicPlayer`, and the ordinary benchmark plays it with the snapshot on
PYTHONPATH.

An anchor this old predates the opening books, so each side plays its own
default opening. That is a confound, stated in every reading.

    python scripts/legacy_anchor.py 372609e --seeds 6000-6127 --workers 8 --out logs/legacy
"""
from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile

BOTS = re.compile(r'\bstruggler\.bots\b')
FROM_BOTS = re.compile(r'\bfrom struggler import bots\b')


def build(rev: str, out: pathlib.Path) -> tuple[str, pathlib.Path]:
    """Extract `rev`'s bots as package `legacy_<sha>` under `out`; return the
    package name and the entry file `benchmark` should load."""
    sha = subprocess.run(['git', 'rev-parse', '--short=7', rev], capture_output=True,
                         text=True, check=True).stdout.strip()
    pkg = f'legacy_{sha}'
    root = out / pkg
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True)
    archive = subprocess.run(['git', 'archive', rev, 'src/struggler/bots'],
                             capture_output=True, check=True).stdout
    prefix = 'src/struggler/bots/'
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if not member.name.startswith(prefix) or member.name == prefix:
                continue
            member.name = member.name[len(prefix):]
            tar.extract(member, root, filter='data')
    return pkg, rewrite(root, pkg)


def _substitute(text: str, pkg: str) -> str:
    return FROM_BOTS.sub(f'import {pkg} as bots', BOTS.sub(pkg, text))


def rewrite(root: pathlib.Path, pkg: str) -> pathlib.Path:
    """Point every `struggler.bots` reference in the snapshot at `pkg`, and
    refuse to hand back a snapshot that still names the real package: a
    reference the substitution missed would bind today's module, and the
    anchor would quietly play part of the candidate."""
    for path in root.rglob('*.py'):
        text = path.read_text()
        new = _substitute(text, pkg)
        if new != text:
            path.write_text(new)
    leftover = [str(p) for p in root.rglob('*.py')
                if BOTS.search(p.read_text()) or FROM_BOTS.search(p.read_text())]
    if leftover:
        raise RuntimeError(f'struggler.bots still referenced in {leftover}')
    if (root / 'strategic' / 'policy.py').exists():
        module = f'{pkg}.strategic.policy'
    elif (root / 'strategic.py').exists():
        module = f'{pkg}.strategic'
    else:
        raise RuntimeError(f'{root} holds no strategic bot')
    entry = root.parent / f'{pkg}_entry.py'
    entry.write_text(f'from {module} import StrategicPlayer  # noqa: F401\n')
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('rev')
    ap.add_argument('--seeds', default='6000-6127')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--out', default='logs/legacy')
    args = ap.parse_args(argv)
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pkg, entry = build(args.rev, out)
    report = out / f'{pkg}.json'
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(
        p for p in (str(out), os.environ.get('PYTHONPATH', '')) if p))
    status = subprocess.run(
        [sys.executable, '-m', 'struggler.bots.benchmark', '--bot', 'strategic',
         '--opponent', f'strategic@{entry}', '--seeds', args.seeds, '--workers', str(args.workers),
         '--stall-timeout', '1200', '--report', str(report)],
        env=env, stdout=subprocess.DEVNULL, stderr=open(out / f'{pkg}.err', 'w')).returncode
    if not report.exists():
        print(f'{args.rev}: no report (benchmark exit {status}); see {out / (pkg + ".err")}')
        return 3
    s = json.load(open(report))['summary']
    score, half = s.get('score'), s.get('score_halfwidth')
    print(f'{args.rev} ({pkg}): HEAD scores {score} +/-{half} over {s.get("seeds")} seeds, '
          f'{s.get("games")} games, {s.get("nuclear_losses")} nuclear losses; '
          f'stop_reason {s.get("stop_reason")}')
    if score is not None and half is not None:
        print(f'  one-sided 95% upper bound {score + half:.3f}; below 0.500 would mean the anchor '
              f'is measurably stronger than HEAD')
    print(f'  mean end turn {s.get("mean_end_turn")}, endings {s.get("endings")}')
    print('  openings: HEAD plays iran/austria, the anchor its own pre-book default (a confound)')
    return 6 if status == 6 else 0


if __name__ == '__main__':
    raise SystemExit(main())
