#!/usr/bin/env python
"""Self-play one revision over many seeds, keeping every sandbox failure's stack.

Two questions from docs/notes/claude/2026-09-13-handoff-for-codex.md, one run:

1. Section 2: are games lasting longer since the stability route decay
   (7a1ac6c)? The parity corpus's turn distribution moved, but the corpus is
   self-play on four seeds. This plays the same shape over as many seeds as
   asked, for any revision, and `--compare` pairs two runs by seed -- same
   deal, same opening books -- so the difference is the bot's and not the
   deal's.

2. Section 4c: where does Blockade's RecursionError come from? `event_value`
   catches the exception, logs "event X failed in the sandbox (...)" and
   falls back to the generic estimate, so by the time anyone reads the log
   the stack is gone. A logging handler runs INSIDE that except block, where
   `sys.exc_info()` still holds the traceback, so it can keep it. No policy
   code is touched to do this.

Games are played by `benchmark.play`, not a copy of it (shape 4: two
implementations of one rule). One seat per seed: both seats run the same
bot with no RNG, and the books derive from the seed alone, so the USSR-seat
game would be the US-seat game again.

    python scripts/selfplay_trace.py --seeds 9000-9191 --out logs/x/head
    python scripts/selfplay_trace.py --bot strategic@<snap>/strategic/policy.py \\
        --seeds 9000-9191 --out logs/x/base
    python scripts/selfplay_trace.py --compare logs/x/base.json logs/x/head.json

Measures only. It does not say whether a longer game is a better one.
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import math
import multiprocessing
import statistics
import sys
import traceback

from struggler.bots import benchmark

CYCLE_MIN = 10   # a frame seen this often in one stack is part of a loop


class _WarningsOnly:
    """`benchmark.play` calls `logging.disable(CRITICAL)` when it has no log
    directory, which would silence the very warning this script exists to
    catch. Stand in for the `logging` module inside `benchmark` and lower
    that to INFO: the game's chatter stays off (so games cost what they
    always cost) and warnings survive."""

    def __getattr__(self, name):
        return getattr(logging, name)

    @staticmethod
    def disable(level=logging.CRITICAL):
        logging.disable(min(level, logging.INFO))


def _frame(f) -> str:
    path = f.filename.replace('\\', '/')
    short = path.split('/src/struggler/')[-1] if '/src/struggler/' in path else path.rsplit('/', 1)[-1]
    return f'{short}:{f.name}:{f.lineno}'


class _Catch(logging.Handler):
    records: list[dict] = []

    def emit(self, record):
        if record.levelno < logging.WARNING:
            return
        exc = sys.exc_info()
        entry = dict(logger=record.name, template=str(record.msg),
                     card=str(record.args[0]) if record.args else '',
                     message=record.getMessage()[:300])
        if exc[2] is not None:
            frames = [_frame(f) for f in traceback.extract_tb(exc[2])]
            counts = collections.Counter(frames)
            entry.update(
                exc_type=exc[0].__name__, depth=len(frames),
                head=frames[:15], tail=frames[-8:],
                cycle=sorted(((fr, n) for fr, n in counts.items() if n >= CYCLE_MIN),
                             key=lambda x: -x[1]))
        _Catch.records.append(entry)


def _init():
    benchmark.logging = _WarningsOnly()
    root = logging.getLogger('struggler')
    root.addHandler(_Catch())
    root.setLevel(logging.WARNING)


def _play(job):
    _Catch.records = []
    game = benchmark.play(job)
    return game, list(_Catch.records)


def run(args) -> int:
    seeds = benchmark.parse_seeds(args.seeds)
    jobs = [(args.bot, args.bot, seed, 'US', 24, 0, None, None, True) for seed in seeds]
    games, failures, stalled = [], [], False
    with multiprocessing.Pool(args.workers, initializer=_init) as pool:
        it = pool.imap_unordered(_play, jobs, chunksize=1)
        for i in range(len(jobs)):
            try:
                game, records = it.next(timeout=args.stall_timeout)
            except multiprocessing.TimeoutError:
                # The gap between finishes, not one game's length: the same
                # rule as benchmark.py's --stall-timeout, and for the same
                # reason -- an ablation once hung one game for four hours.
                print(f'STALLED: nothing finished in {args.stall_timeout}s; '
                      f'reporting the {len(games)} games that did', file=sys.stderr)
                stalled = True
                pool.terminate()
                break
            games.append(game)
            for r in records:
                failures.append(dict(r, seed=game['seed']))
            print(f'{i + 1:4d}/{len(jobs)} seed {game["seed"]} T{game["turn"]} {game["reason"]}'
                  f'{"  (" + str(len(records)) + " warnings)" if records else ""}',
                  file=sys.stderr, flush=True)
    games.sort(key=lambda g: g['seed'])
    summary = benchmark.summarize(games, 0) if games else {}
    summary.update(bot=args.bot, stalled=stalled, planned=len(jobs))
    with open(args.out + '.json', 'w') as f:
        json.dump(dict(summary=summary, games=games), f)

    grouped: dict[tuple, dict] = {}
    for r in failures:
        key = (r['card'], r.get('exc_type', ''), tuple(fr for fr, _ in r.get('cycle', [])))
        g = grouped.setdefault(key, dict(card=r['card'], exc_type=r.get('exc_type'),
                                         template=r['template'], count=0, seeds=[],
                                         example=r))
        g['count'] += 1
        if r['seed'] not in g['seeds']:
            g['seeds'].append(r['seed'])
    with open(args.out + '.failures.json', 'w') as f:
        json.dump(sorted(grouped.values(), key=lambda g: -g['count']), f, indent=1)

    print(f'{len(games)} of {len(jobs)} games, bot {args.bot}{"  STALLED" if stalled else ""}')
    if games:
        print(f'mean end turn {summary.get("mean_end_turn")}, reached T8+ {summary.get("reached_late_war")}')
        print(f'endings {summary.get("endings")}')
    print(f'\n{len(failures)} warnings in {len({r["seed"] for r in failures})} games, '
          f'{len(grouped)} distinct shapes')
    for g in sorted(grouped.values(), key=lambda g: -g['count']):
        ex = g['example']
        print(f'\n  {g["count"]:4d}x  {g["card"] or ex["message"][:60]}  {g["exc_type"] or ""}'
              f'  in {len(g["seeds"])} games (first seeds {g["seeds"][:6]})')
        if ex.get('depth'):
            print(f'        depth {ex["depth"]}; frames repeating >= {CYCLE_MIN}x:')
            for fr, n in ex['cycle'][:12]:
                print(f'          {n:4d}  {fr}')
            print('        entered via:')
            for fr in ex['head'][:8]:
                print(f'                {fr}')
    return 3 if stalled else 0


def compare(a_path: str, b_path: str) -> int:
    def load(path):
        with open(path) as f:
            return json.load(f)
    a, b = load(a_path), load(b_path)
    ga = {g['seed']: g for g in a['games'] if g.get('finished')}
    gb = {g['seed']: g for g in b['games'] if g.get('finished')}
    both = sorted(ga.keys() & gb.keys())
    print(f'A = {a["summary"].get("bot")}  ({a_path})')
    print(f'B = {b["summary"].get("bot")}  ({b_path})')
    print(f'{len(both)} seeds finished in both (A {len(ga)}, B {len(gb)})\n')
    print(f'{"":14}{"A":>8}{"B":>8}')
    for label, fn in (('mean end turn', lambda g: g['turn']),
                      ('reached T8+', lambda g: g['turn'] >= 8),
                      ('final scoring', lambda g: bool(g.get('final_scoring')))):
        print(f'{label:14}{statistics.fmean(fn(ga[s]) for s in both):8.3f}'
              f'{statistics.fmean(fn(gb[s]) for s in both):8.3f}')
    print('\nend turn    ' + ''.join(f'{t:>5}' for t in range(1, 11)))
    for name, g in (('A', ga), ('B', gb)):
        c = collections.Counter(g[s]['turn'] for s in both)
        print(f'  {name}        ' + ''.join(f'{c.get(t, 0):>5}' for t in range(1, 11)))
    print('\nendings')
    reasons = sorted({g[s]['reason'] or 'none' for g in (ga, gb) for s in both})
    for r in reasons:
        print(f'  {r:16}{sum((ga[s]["reason"] or "none") == r for s in both):>6}'
              f'{sum((gb[s]["reason"] or "none") == r for s in both):>6}')
    diff = [gb[s]['turn'] - ga[s]['turn'] for s in both]
    if len(diff) > 1:
        se = statistics.stdev(diff) / math.sqrt(len(diff))
        print(f'\npaired end-turn difference B - A: {statistics.fmean(diff):+.3f} '
              f'+/-{1.96 * se:.3f} (95%), over {len(diff)} seeds')
    print(f'  B longer {sum(d > 0 for d in diff)}, same {sum(d == 0 for d in diff)}, '
          f'shorter {sum(d < 0 for d in diff)}')
    same = sum(ga[s]['turn'] == gb[s]['turn'] and ga[s]['vp'] == gb[s]['vp']
               and ga[s]['reason'] == gb[s]['reason'] for s in both)
    print(f'  identical ending (turn, VP, reason) on {same} seeds')
    moved = collections.Counter((ga[s]['reason'] or 'none', gb[s]['reason'] or 'none')
                                for s in both if ga[s]['reason'] != gb[s]['reason'])
    if moved:
        print('  ending changed, A -> B: ' + ', '.join(f'{x}->{y} x{n}' for (x, y), n in moved.most_common()))
    print('\nMeasured, not interpreted. Self-play: both seats are the same bot, so this')
    print('says how long that bot\'s games against itself last, not how strong it is.')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--bot', default='strategic', help='as benchmark.py --bot; plays both seats')
    ap.add_argument('--seeds', default='9000-9015')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--stall-timeout', type=int, default=1200)
    ap.add_argument('--out', help='writes <out>.json (benchmark-shaped) and <out>.failures.json')
    ap.add_argument('--compare', nargs=2, metavar=('A', 'B'))
    args = ap.parse_args(argv)
    if args.compare:
        return compare(*args.compare)
    if not args.out:
        ap.error('--out is required unless --compare')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
