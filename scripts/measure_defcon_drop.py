"""P(the opponent lowers DEFCON on their action round | they legally can).

The last-safe-window guard (`StrategicPlayer.cornered_after_drop`) prices
a play at the whole game whenever the opponent has a LEGAL battleground
Coup that would take DEFCON 3 to 2. The maintainer's ruling (2026-09-18)
is that it should be a probability instead: P(drop | legal) x P(loss |
drop) x the 40 VP game. This measures the first factor.

For every action round played at DEFCON 3, it asks the guard's own
predicate -- `DefconPlanner.opponent_can_lower_defcon`, from the other
side's observation, so the rule is not written a second time -- whether
the side about to play had a legal DEFCON-lowering battleground Coup. It
then records whether DEFCON fell during that side's round. Rates are by
seat and by whether the other side held a borrowed-Coup card (the guard's
case), with a Wilson interval.

A bot-vs-bot rate, labelled as one: these bots Coup on their own
valuation, and strong humans Coup more freely (docs/EXPERT_STRATEGY.md).

    uv run python scripts/measure_defcon_drop.py --seeds 42000-42031
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import logging
import math
import os
import sys

from struggler.engine import DecisionKind as K, Engine, Side
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.defcon import BORROWED_COUPS


def seed_range(text: str) -> list[int]:
    lo, _, hi = text.partition('-')
    return list(range(int(lo), int(hi or lo) + 1))


def play(seed: int) -> list[tuple[str, bool, bool, bool, int]]:
    """(seat, legal, dropped, other side holds a borrowed Coup, turn) per
    action round begun at DEFCON 3."""
    logging.disable(logging.CRITICAL)
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    probe = StrategicPlayer()
    # The lowest DEFCON seen since the round opened, read after every step:
    # a drop in a turn's last round is otherwise undone by the +1 at the
    # turn end before the next round opens.
    rows, open_round, low = [], None, 5
    while not engine.is_terminal and engine.pending_decision is not None:
        d = engine.pending_decision
        if d.kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY) and d.actor is not Side.CHANCE:
            if open_round is not None:
                seat, legal, holds, turn = open_round
                rows.append((seat, legal, low < 3, holds, turn))
                open_round = None
            if d.kind is K.ACTION_ROUND_PLAY and engine.defcon == 3:
                other = d.actor.opponent
                obs = engine.observe(other)
                legal = probe.planner_for(obs).opponent_can_lower_defcon()
                holds = any(c in BORROWED_COUPS and BORROWED_COUPS[c] is d.actor for c in obs.hand)
                open_round, low = (d.actor.value, legal, holds, engine.turn), engine.defcon
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
        else:
            engine.step(bots[d.actor].choose_action(engine.observe(d.actor), []))
        low = min(low, engine.defcon)
    if open_round is not None:
        seat, legal, holds, turn = open_round
        rows.append((seat, legal, low < 3, holds, turn))
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (float('nan'), float('nan'))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seeds', required=True)
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args(argv)
    with cf.ProcessPoolExecutor(args.workers) as pool:
        rows = [r for game in pool.map(play, seed_range(args.seeds)) for r in game]
    table = collections.Counter()
    for seat, legal, dropped, holds, _turn in rows:
        for key in ((seat, legal, 'all'), (seat, legal, 'guard case' if holds else 'no hazard')):
            table[(*key, 'n')] += 1
            table[(*key, 'drop')] += dropped
    print(f'{len(rows)} action rounds begun at DEFCON 3, {len(seed_range(args.seeds))} games')
    print('seat  legal drop?  subset       drops/rounds  rate   95% Wilson')
    for seat in ('US', 'USSR'):
        for legal in (True, False):
            for subset in ('all', 'guard case', 'no hazard'):
                n = table[(seat, legal, subset, 'n')]
                k = table[(seat, legal, subset, 'drop')]
                if not n:
                    continue
                lo, hi = wilson(k, n)
                print(f'{seat:5s} {legal!s:11s}  {subset:11s}  {k:5d}/{n:<6d}  {k / n:.3f}  [{lo:.3f}, {hi:.3f}]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
