"""The first decision after which the hand had no exit (v3 plan, step 4).

The survival planner prices a hand at its chance of being forced into a
losing play. This asks a different question, the one the audit's G1 rests
on: *when* does a hand stop having an exit, and what was the play before
it? A hand that is already cornered cannot be saved by better play at the
cornered decision -- the mistake, if there is one, is the play before.

For every action round the bot plays, this records the whole-hand risk
before and after its own play. The first round in a game where the risk
reaches `--cornered` (1.0 by default: every line loses) is that game's
closing decision, and the play that preceded it is recorded with it. Games
that never reach it are counted too: the denominator is what says whether
this matters at all.

Reads the planner directly rather than the log, because the planner is the
thing whose number the plan asks about, and `StrategicPlayer.planner_for`
is the same construction the bot uses (one statement of the rule).

    uv run python scripts/measure_last_exit.py --seeds 42000-42031
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


def seed_range(text: str) -> list[int]:
    lo, _, hi = text.partition('-')
    return list(range(int(lo), int(hi or lo) + 1))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (float('nan'), float('nan'))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def play(args: tuple[int, float]) -> list[dict]:
    """One game. A row per seat: whether it was ever cornered, and where."""
    seed, cornered_at = args
    logging.disable(logging.CRITICAL)
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    probe = StrategicPlayer()
    # Per seat: the first cornered round, the play that closed it, and how
    # many rounds were played at all.
    seats = {s: {'seed': seed, 'side': s.value, 'rounds': 0, 'cornered': None,
                 'closing_play': None, 'closing_turn': None, 'defcon_1': False,
                 'max_risk': 0.0} for s in (Side.US, Side.USSR)}
    # What each side played last, so a corner can name the play before it.
    last_play = {Side.US: None, Side.USSR: None}
    while not engine.is_terminal and engine.pending_decision is not None:
        d = engine.pending_decision
        if d.kind is K.ACTION_ROUND_PLAY and d.actor is not Side.CHANCE:
            row = seats[d.actor]
            row['rounds'] += 1
            obs = engine.observe(d.actor)
            risk = probe.planner_for(obs).risk()
            if row['cornered'] is None and risk >= cornered_at:
                row['cornered'] = row['rounds']
                row['closing_play'] = last_play[d.actor]
                row['closing_turn'] = engine.turn
            row['max_risk'] = max(row['max_risk'], risk)
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        action = bots[d.actor].choose_action(engine.observe(d.actor), [])
        if d.kind in (K.ACTION_ROUND_PLAY, K.PLAY_MODE):
            card = action.payload.get('card') or action.payload.get('mode')
            if card:
                last_play[d.actor] = f'{d.kind.name.lower()}:{card}'
        engine.step(action)
    for side, row in seats.items():
        row['defcon_1'] = engine.defcon <= 1
        row['end_turn'] = engine.turn
    return list(seats.values())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seeds', required=True)
    parser.add_argument('--cornered', type=float, default=1.0,
                        help='whole-hand risk that counts as no exit (default 1.0, certain)')
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args(argv)
    seeds = seed_range(args.seeds)
    with cf.ProcessPoolExecutor(args.workers) as pool:
        rows = [r for game in pool.map(play, [(s, args.cornered) for s in seeds]) for r in game]

    print(f'{len(rows)} seat-games over {len(seeds)} seeds, cornered = whole-hand risk >= {args.cornered}')
    print()
    print('seat  cornered/seat-games  rate   95% Wilson        median round  median turn')
    for side in ('US', 'USSR'):
        mine = [r for r in rows if r['side'] == side]
        hit = [r for r in mine if r['cornered'] is not None]
        lo, hi = wilson(len(hit), len(mine))
        rounds = sorted(r['cornered'] for r in hit)
        turns = sorted(r['closing_turn'] for r in hit)
        med_r = rounds[len(rounds) // 2] if rounds else float('nan')
        med_t = turns[len(turns) // 2] if turns else float('nan')
        print(f'{side:5s} {len(hit):5d}/{len(mine):<12d} {len(hit) / len(mine):.3f}  '
              f'[{lo:.3f}, {hi:.3f}]  {med_r:12.0f}  {med_t:11.0f}')

    print()
    print('Does being cornered cost the game? (DEFCON 1 loss rate by seat)')
    for side in ('US', 'USSR'):
        for label, subset in (('cornered   ', [r for r in rows if r['side'] == side and r['cornered'] is not None]),
                              ('never       ', [r for r in rows if r['side'] == side and r['cornered'] is None])):
            if not subset:
                continue
            k = sum(r['defcon_1'] for r in subset)
            lo, hi = wilson(k, len(subset))
            print(f'{side:5s} {label} {k:4d}/{len(subset):<5d}  {k / len(subset):.3f}  [{lo:.3f}, {hi:.3f}]')

    print()
    print('How close does a hand get? (highest whole-hand risk in the game)')
    print('seat   >=0.25  >=0.50  >=0.75  >=0.90  ==1.00   median max')
    for side in ('US', 'USSR'):
        mine = [r for r in rows if r['side'] == side]
        cuts = [sum(r['max_risk'] >= c for r in mine) / len(mine) for c in (0.25, 0.5, 0.75, 0.9)]
        certain = sum(r['max_risk'] >= 1.0 for r in mine) / len(mine)
        med = sorted(r['max_risk'] for r in mine)[len(mine) // 2]
        print(f'{side:5s}  ' + '  '.join(f'{c:6.3f}' for c in cuts) + f'  {certain:6.3f}   {med:10.3f}')

    print()
    print('The play before the corner closed (top 12):')
    closing = collections.Counter(r['closing_play'] for r in rows if r['cornered'] is not None)
    for play_name, n in closing.most_common(12):
        print(f'  {n:4d}  {play_name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
