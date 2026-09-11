#!/usr/bin/env python
"""Play every opening book against every other and report what each is worth.

A full factorial: each seed is played once in all nine (US book, USSR
book) cells, so a seed's own luck appears in every cell and cancels from
the comparison. That pairing is the whole reason this is not
`benchmark.py` -- the benchmark pits two *bots* and seats them both ways,
which here would play the same game twice, since both sides are the same
code and only the board differs.

    uv run python scripts/opening_tournament.py --seeds 4000-4023 --workers 8

What it measures, stated precisely: which opening *this bot* converts
into the most VP. That is not the same question as which opening is
strongest -- an opening whose value is in a follow-up the bot never plays
will read as weak here. Read it as evidence, weighted by how much you
trust the bot's middlegame.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import logging
import statistics
import sys
import time
from multiprocessing import Pool

from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.policy import OPENINGS
from struggler.engine import Engine, Side
from struggler.engine.replay import HistoryBuilder
from struggler.runner import play_game


def one_game(job: tuple) -> dict:
    seed, us_book, ussr_book = job
    logging.disable(logging.CRITICAL)
    books = {'US': us_book, 'USSR': ussr_book}
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    players = {side: StrategicPlayer(openings=books) for side in (Side.US, Side.USSR)}
    start = time.time()
    winner = play_game(engine, players, history_builder=HistoryBuilder())
    return {'seed': seed, 'US': us_book, 'USSR': ussr_book,
            # VP is US-positive throughout the engine, so it needs no signing.
            'vp': engine.vp, 'turn': engine.turn,
            'winner': winner.value if winner else None,
            'us_score': 0.5 if winner is None else float(winner is Side.US),
            'seconds': round(time.time() - start, 1)}


def parse_seeds(text: str) -> list[int]:
    if '-' in text:
        low, high = text.split('-')
        return list(range(int(low), int(high) + 1))
    return [int(part) for part in text.split(',')]


def report(games: list[dict]) -> None:
    by_seed: dict[int, dict] = collections.defaultdict(dict)
    for game in games:
        by_seed[game['seed']][(game['US'], game['USSR'])] = game
    complete = {seed: cells for seed, cells in by_seed.items()
                if len(cells) == len(OPENINGS['US']) * len(OPENINGS['USSR'])}
    print(f'{len(games)} games, {len(complete)} seeds complete in all nine cells')
    if not complete:
        return

    def summarise(side: str, other: str) -> None:
        print(f'\n  {side} book       mean VP (US-positive)   US win rate   n')
        for book in OPENINGS[side]:
            picked = [g for cells in complete.values() for (u, s), g in cells.items()
                      if (u if side == 'US' else s) == book]
            vp = statistics.fmean(g['vp'] for g in picked)
            win = statistics.fmean(g['us_score'] for g in picked)
            print(f'  {book:12}   {vp:+21.2f}   {win:11.3f}   {len(picked):3}')

    summarise('US', 'USSR')
    summarise('USSR', 'US')

    # Paired within seed: the same seed in every cell, so the seed's own
    # luck subtracts out. This is the comparison that carries the weight.
    print('\n  paired within seed, US books (positive favours the row):')
    books = OPENINGS['US']
    print('              ' + '  '.join(f'{b:>10}' for b in books))
    for a in books:
        row = []
        for b in books:
            if a == b:
                row.append(f'{"--":>10}')
                continue
            diffs = [statistics.fmean(g['vp'] for (u, _), g in cells.items() if u == a)
                     - statistics.fmean(g['vp'] for (u, _), g in cells.items() if u == b)
                     for cells in complete.values()]
            mean = statistics.fmean(diffs)
            se = statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else float('nan')
            row.append(f'{mean:+6.2f}+-{se:4.2f}'[:10].rjust(10))
        print(f'  {a:12}' + '  '.join(row))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seeds', default='4000-4015')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--report', help='write every game here as JSON')
    args = parser.parse_args()

    seeds = parse_seeds(args.seeds)
    jobs = [(seed, us, ussr) for seed in seeds
            for us, ussr in itertools.product(OPENINGS['US'], OPENINGS['USSR'])]
    print(f'{len(jobs)} games: {len(seeds)} seeds x {len(OPENINGS["US"])} US x '
          f'{len(OPENINGS["USSR"])} USSR books', file=sys.stderr)
    games = []
    with Pool(args.workers) as pool:
        for game in pool.imap_unordered(one_game, jobs, chunksize=1):
            games.append(game)
            print(f'{len(games):4}/{len(jobs)} seed {game["seed"]} '
                  f'{game["US"]:8}/{game["USSR"]:10} T{game["turn"]} vp={game["vp"]:+d} '
                  f'{game["seconds"]}s', file=sys.stderr, flush=True)
    report(games)
    if args.report:
        with open(args.report, 'w') as f:
            json.dump({'seeds': seeds, 'games': games}, f, indent=1)
        print(f'\n  -> {args.report}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
