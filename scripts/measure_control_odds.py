#!/usr/bin/env python
"""Who controls a country when its region actually scores, with the features
a fitted control-odds formula would read.

The maintainer's battleground formula, 2026-09-13:

    value of a scoring  x  flip ability ** turns  x  P(scoring)
                        x  (a / Ops for you to control + b / Ops for them to control)

with the constants to be fitted and the division in doubt. Flip ability and
the two Ops counts describe the same thing -- whether the country is ours when
it scores -- so this measures that probability directly, per row, and
`scripts/fit_control_odds.py` fits candidate forms to it. Overprotection
(influence beyond what control needs) is recorded as its own feature, on the
maintainer's point that it moves the odds of keeping control and not only the
Ops a break costs.

A ROW is one side's view of one country at the start of one turn:

    c_me, c_opp       exact Ops for that side / the other to take control,
                      paying the doubling rule point by point (0 if held)
    over_me, over_opp influence beyond the stability margin
    reach_me/_opp     whether each side may place there at all
    controller        'me', 'them' or 'none' now
    horizon           resolve at the region's next scoring (1) or the one after (2)
    outcome           'me', 'them' or 'none' at that scoring; None if the game
                      ended first (CENSORED -- counted, never silently dropped)

Rows open every turn, so rows from one game are correlated: the fitter scores
every form on seeds it was not fitted on, and that split is the honest error.

Resolution hooks the engine's own scoring exactly as
`scripts/measure_access_conversion.py` does since audit F1 -- a cancelled
headline resolves nothing, Final Scoring resolves everything, Southeast Asia
scoring resolves only Southeast Asia.

    python scripts/measure_control_odds.py --seeds 7000-7007
    python scripts/measure_control_odds.py --seeds 7000-7191 --horizons 1,2 --workers 8

Not a strength measurement.
"""
from __future__ import annotations

import argparse
import collections
import functools
import gzip
import json
import multiprocessing
import sys
from pathlib import Path

from struggler.engine import Engine, Side
from struggler.engine.core import Subregion
from struggler.bots.rules_math import ops_to_control
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.benchmark import parse_seeds

SIDES = (Side.US, Side.USSR)


def overprotection(mine: int, theirs: int, stability: int) -> int:
    """Influence beyond what control needs; 0 when not in control."""
    return max(0, mine - theirs - stability)


def features(engine, side: Side, cid: str) -> dict:
    board = engine.board
    info = board.countries[cid]
    foe = side.opponent
    mine, theirs = board.influence[cid][side.value], board.influence[cid][foe.value]
    holder = board.control(cid)
    return {
        'country': cid, 'region': info.region.name, 'battleground': info.battleground,
        'stability': info.stability, 'mine': mine, 'theirs': theirs,
        'controller': 'me' if holder is side else 'them' if holder is foe else 'none',
        'c_me': ops_to_control(mine, theirs, info.stability),
        'c_opp': ops_to_control(theirs, mine, info.stability),
        'over_me': overprotection(mine, theirs, info.stability),
        'over_opp': overprotection(theirs, mine, info.stability),
        'reach_me': board.is_reachable(side, cid), 'reach_opp': board.is_reachable(foe, cid),
        'turn': engine.turn, 'defcon': engine.defcon, 'side': side.value,
    }


class Tracker:
    """Rows on one engine, resolved when a region ACTUALLY scores. See
    `measure_access_conversion.Tracker` for why the hooks and not the cards."""

    def __init__(self, engine, horizons: tuple[int, ...] = (1,), *,
                 all_countries: bool = False, seed: int = 0):
        self.engine, self.horizons = engine, horizons
        self.all_countries, self.seed = all_countries, seed
        self.pending: list[list] = []   # [scorings still to wait for, row]
        self.rows: list[dict] = []
        score_region, score_sea = engine._score_region_net, engine._score_southeast_asia
        countries = engine.board.countries

        def region_net(region):
            self._resolve(lambda cid: countries[cid].region is region)
            return score_region(region)

        def southeast_asia():
            self._resolve(lambda cid: Subregion.SOUTHEAST_ASIA in countries[cid].subregions)
            return score_sea()

        engine._score_region_net = region_net
        engine._score_southeast_asia = southeast_asia

    def open(self) -> None:
        """One row per side, country and horizon for this turn."""
        for cid, info in self.engine.board.countries.items():
            if not (info.battleground or self.all_countries):
                continue
            for side in SIDES:
                row = features(self.engine, side, cid)
                for h in self.horizons:
                    self.pending.append([h, dict(row, horizon=h, seed=self.seed)])

    def _resolve(self, in_scope) -> None:
        # Scoring moves VP, never influence, so control now is what is scored.
        board, still = self.engine.board, []
        for item in self.pending:
            left, row = item
            if not in_scope(row['country']):
                still.append(item)
                continue
            if left > 1:
                item[0] = left - 1
                still.append(item)
                continue
            side = Side(row['side'])
            holder = board.control(row['country'])
            row['outcome'] = 'me' if holder is side else 'them' if holder is side.opponent else 'none'
            row['resolved_turn'] = self.engine.turn
            self.rows.append(row)
        self.pending = still

    def result(self) -> list[dict]:
        return self.rows + [dict(row, outcome=None) for _, row in self.pending]


def play(seed: int, horizons: tuple[int, ...] = (1,), all_countries: bool = False) -> list[dict]:
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    tracker = Tracker(engine, horizons, all_countries=all_countries, seed=seed)
    bots = {s: StrategicPlayer() for s in SIDES}
    seen_turn, steps = -1, 0
    while not engine.is_terminal and steps < 20000:
        steps += 1
        if engine.turn != seen_turn:
            seen_turn = engine.turn
            tracker.open()
        d = engine.pending_decision
        action = (d.options[0] if d.actor is Side.CHANCE
                  else bots[d.actor].choose_action(engine.observe(d.actor), []))
        engine.step(action)
    return tracker.result()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7007')
    ap.add_argument('--horizons', default='1,2')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--all-countries', action='store_true', help='not only battlegrounds')
    ap.add_argument('--out', default='logs/control-odds/rows.jsonl.gz')
    args = ap.parse_args(argv)
    horizons = tuple(sorted({int(h) for h in args.horizons.split(',')}))
    if not horizons or horizons[0] < 1:
        ap.error('horizons are 1 or more')
    seeds = parse_seeds(args.seeds)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # (horizon, controller, stability) -> [resolved, outcome == 'me']; horizon -> censored
    table: dict[tuple, list[int]] = collections.defaultdict(lambda: [0, 0])
    censored: collections.Counter = collections.Counter()
    job = functools.partial(play, horizons=horizons, all_countries=args.all_countries)
    with multiprocessing.Pool(args.workers) as pool, gzip.open(out, 'wt') as f:
        for i, rows in enumerate(pool.imap_unordered(job, seeds), 1):
            for row in rows:
                f.write(json.dumps(row) + '\n')
                if row['outcome'] is None:
                    censored[row['horizon']] += 1
                    continue
                cell = table[(row['horizon'], row['controller'], row['stability'])]
                cell[0] += 1
                cell[1] += row['outcome'] == 'me'
            print(f'  {i}/{len(seeds)} games', file=sys.stderr, flush=True)
    print(f'rows written to {out}, {len(seeds)} games')
    for h in horizons:
        print(f'\n== horizon {h}: P(controlled by the row\'s side at scoring {h})')
        print(f'{"controller now":>15} {"stability":>10} {"n":>7} {"P(me)":>7}')
        for (hh, controller, stab), (n, me) in sorted(table.items()):
            if hh == h:
                print(f'{controller:>15} {stab:>10} {n:>7} {me / n:>7.3f}')
        print(f'  censored (game ended first): {censored[h]}')
    print('\n  Not a strength measurement. Fit forms with scripts/fit_control_odds.py.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
