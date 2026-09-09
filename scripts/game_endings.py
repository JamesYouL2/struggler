"""How games actually end, from benchmark reports.

The evaluator prices a country by how much its region will still score, which
depends on how much game is left. That is not `10 - turn`: most games end
before final scoring, on the 20 VP auto-victory. This reads the per-game
`reason` and `turn` the engine already records and prints the calibration
table `bots.public_cards.FINAL_SCORING_ODDS` is taken from.

    python scripts/game_endings.py logs/game-check/gate-*/full-vs-*.json

Bot-vs-bot games are a proxy, and a generous one: strong human players push
for the 20 VP win harder than this bot does, so the real odds of reaching
final scoring are lower than what this prints.
"""
from __future__ import annotations

import collections
import json
import sys

LAST_TURN = 10


def load(paths) -> list[dict]:
    games = []
    for path in paths:
        with open(path) as f:
            games.extend(g for g in json.load(f)['games'] if g.get('finished'))
    return games


def report(games, out=sys.stdout) -> list[float]:
    total = len(games)
    if not total:
        raise SystemExit('no finished games in those reports')
    print(f'{total} finished games', file=out)
    print('\nhow they ended:', file=out)
    for reason, count in collections.Counter(g.get('reason') for g in games).most_common():
        print(f'  {str(reason):16s}{count:5d}{100 * count / total:7.1f}%', file=out)
    print('\nturn | alive | P(final scoring | alive) | per-turn survival', file=out)
    odds = []
    for turn in range(1, LAST_TURN + 1):
        alive = [g for g in games if g['turn'] >= turn]
        final = sum(1 for g in alive if g.get('reason') == 'final_vp')
        nxt = sum(1 for g in games if g['turn'] >= turn + 1)
        odds.append(final / len(alive))
        survival = f'{nxt / len(alive):.3f}' if turn < LAST_TURN else '-'
        print(f'  {turn:2d} | {len(alive):5d} | {odds[-1]:23.3f} | {survival:>17}', file=out)
    print('\nFINAL_SCORING_ODDS = (' + ', '.join(f'{p:.2f}' for p in odds) + ')', file=out)
    return odds


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    report(load(sys.argv[1:]))
