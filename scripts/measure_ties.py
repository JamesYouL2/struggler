"""Count ties in LIVE rankings: where the sort has nothing left to say.

Every option ranking is `sorted(..., reverse=True)` over a key tuple and
the sort is STABLE, so an exact tie is resolved by `legal_actions()`
order -- the ENGINE's listing, not a rule of the bot's
(docs/notes/pi/2026-09-24-ties-and-what-breaks-them.md catalogues the
sites). This measures which of them actually fire, how often, in live
play, and for EVENT_CHOICE separates the unhandled shape (the scorer had
no opinion on any option) from options that were priced and happen to
tie.

LIVE ONLY. The first version patched `rank_actions` onto the class, and
the event helpers that price an option are StrategicPlayers too, so it
counted every SIMULATED decision as a live one -- one headline ranking
recorded seven EVENT_INFLUENCE rankings with no action applied. Its
counts were also cumulative across the games a worker played, and its
"without the planner's preference" slice kept the preference (Codex audit
2026-09-25, F3). This reads each live decision's own ranking from
`StrategicPlayer.last_ranking`, in the game loop, once per engine step,
with fresh counts per game.

Each live decision is one of (`benchmark.event_choice_kind`):

    single      one legal option -- no choice was made
    unpriced    the scorer had no opinion on any option; first legal won
    all_equal   every option priced, all the same
    top_tie     the best options tied; engine order split them
    decided     the key separated the winner

The bots play the shipped weights, where the planner is off, so the sort
key is the safety key alone.

    uv run python scripts/measure_ties.py --seeds 42000-42003
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import logging
import os
import sys

from struggler.bots.benchmark import event_choice_kind
from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Engine, Side


def play(seed: int) -> dict:
    """One self-play game; the counts of its live decisions only."""
    logging.getLogger('struggler').setLevel(logging.ERROR)
    stat: dict = {}
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {s: StrategicPlayer() for s in (Side.US, Side.USSR)}
    while not engine.is_terminal and engine.pending_decision is not None:
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        bot = bots[d.actor]
        action = bot.choose_action(engine.observe(d.actor), [])
        how = event_choice_kind(d.options, bot.last_ranking)
        row = stat.setdefault(d.kind.name, collections.Counter())
        row['decisions'] += 1
        row['options'] += len(d.options)
        row[how] += 1
        if d.kind.name == 'EVENT_CHOICE' and how in ('unpriced', 'all_equal', 'top_tie'):
            event = (d.context or {}).get('event', '?')
            stat.setdefault(f'EVENT|{how}', collections.Counter())[event] += 1
        engine.step(action)
    return stat


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seeds', default='42000-42003')
    ap.add_argument('--out', help='write the raw counts here as JSON')
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition('-')
    seeds = list(range(int(lo), int(hi or lo) + 1))
    merged: dict = {}
    with cf.ProcessPoolExecutor(max_workers=min(4, len(seeds))) as pool:
        for stat in pool.map(play, seeds):
            for key, row in stat.items():
                merged.setdefault(key, collections.Counter()).update(row)
    print(f'{len(seeds)} seeds played; live decisions only\n')
    kinds = {k: v for k, v in merged.items() if not k.startswith('EVENT|')}
    for kind, row in sorted(kinds.items(), key=lambda kv: -kv[1]['decisions']):
        n = row['decisions']
        choices = n - row['single']
        tied = row['unpriced'] + row['all_equal'] + row['top_tie']
        share = f'{100 * tied / choices:4.1f}% of {choices} real choices' if choices else 'no real choices'
        print(f'{kind:22} decisions {n:5d}  single {row["single"]:5d}  unpriced {row["unpriced"]:4d}  '
              f'all_equal {row["all_equal"]:4d}  top_tie {row["top_tie"]:4d}  '
              f'decided {row["decided"]:5d}  -> engine order {share}')
    for how in ('unpriced', 'all_equal', 'top_tie'):
        events = merged.get(f'EVENT|{how}')
        if events:
            print(f'\nEVENT_CHOICE {how}:')
            for event, n in events.most_common():
                print(f'  {n:4d}  {event}')
    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w') as f:
            json.dump({k: dict(v) for k, v in merged.items()}, f, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
