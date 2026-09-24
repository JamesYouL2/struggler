"""Count ties in live rankings: where the sort has nothing left to say.

Every option ranking is `sorted(..., reverse=True)` over a key tuple and
the sort is STABLE, so an exact tie is resolved by `legal_actions()`
order -- the ENGINE's listing, not a rule of the bot's
(docs/notes/pi/2026-09-24-ties-and-what-breaks-them.md catalogues the
sites). This measures which of them actually fire, how often, in live
play. For EVENT_CHOICE it answers the sharper question too: how many
decisions are ALL-options-tie -- the unhandled-event shape, where the
policy has no opinion (every option prices 0.0) and the first legal
option wins.

The instrument wraps `rank_actions` and re-derives each option's sort
key -- `(k0, _plan_pref) + k[1:]`, the same tuple the sort uses -- then
records how the top was decided:

    engine order   the top key tied; `legal_actions()` order picked
    plan_pref      keys tied without the planner's preference
    key            the risk/score key separated them

Per decision kind, and per event name for the all-tie EVENT_CHOICEs.
The bots play the shipped weights: this is what the bot does today.

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

from struggler.engine import Engine, Side
from struggler.bots.strategic import StrategicPlayer

_Rank = StrategicPlayer.rank_actions
_Key = StrategicPlayer.safety_key


def _sort_key(player, obs, action, k):
    return (k[0], player._plan_pref(obs, action)) + k[1:]


def _rank_actions(self, observation):
    self._tie_buf = []
    out = _Rank(self, observation)
    buf = self._tie_buf
    if buf:
        _record(observation, self, buf, out)
    return out


def _safety_key(self, obs, action):
    k = _Key(self, obs, action)
    self._tie_buf.append(k)
    return k


# Install the wrappers (the buffer rides on the instance, so both bots in
# a game keep their own counts).
StrategicPlayer.rank_actions = _rank_actions
StrategicPlayer.safety_key = _safety_key


def _record(observation, player, keys, out):
    d = observation.pending_decision
    if d is None:
        return
    kind = d.kind.name
    full = [_sort_key(player, observation, a, k) for a, k in zip(d.options, keys)]
    top = out[0][0]
    winner_key = _sort_key(player, observation, out[0][1], top)
    group = sum(1 for k in full if k == winner_key)
    no_pref = [(k[0],) + k[1:] for k in full]
    winner_no_pref = (winner_key[0],) + winner_key[2:]
    if group > 1:
        how = 'engine order'
    else:
        how = 'plan_pref' if sum(1 for k in no_pref if k == winner_no_pref) > 1 else 'key'
    row = STAT.setdefault(kind, collections.Counter())
    row['rankings'] += 1
    row['options'] += len(full)
    row[how] += 1
    if group > 1:
        row['top_group'] += group
    if kind == 'K.EVENT_CHOICE' or kind == 'EVENT_CHOICE':
        if len(set(full)) == 1:
            event = (d.context or {}).get('event', '?')
            row = STAT.setdefault('UNTIED_EVENTS', collections.Counter())
            row[event] += 1


STAT: dict = {}


def play(seed: int) -> dict:
    logging.getLogger('struggler').setLevel(logging.ERROR)
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {s: StrategicPlayer() for s in (Side.US, Side.USSR)}
    for bot in bots.values():
        bot._tie_buf = []
    while not engine.is_terminal and engine.pending_decision is not None:
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        action = bots[d.actor].choose_action(engine.observe(d.actor), [])
        engine.step(action)
    return STAT


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
    print(f'{len(seeds)} seeds played\n')
    for kind, row in sorted(merged.items(), key=lambda kv: -kv[1]['rankings']):
        if kind == 'UNTIED_EVENTS':
            continue
        n = row['rankings']
        if not n:
            continue
        print(f'{kind:22} rankings {n:5d}  mean options {row["options"] / n:4.1f}  '
              f'decided by: key {row["key"]:5d}  plan_pref {row["plan_pref"]:4d}  '
              f'ENGINE ORDER {row["engine order"]:5d} '
              f'({100 * row["engine order"] / n:4.1f}%)')
    untied = merged.get('UNTIED_EVENTS')
    if untied:
        print('\nEVENT_CHOICEs where EVERY option tied (unhandled -- first legal option won):')
        for event, n in untied.most_common():
            print(f'  {n:4d}  {event}')
    else:
        print('\nno all-tied EVENT_CHOICEs in this sample')
    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        json.dump({k: dict(v) for k, v in merged.items()}, open(args.out, 'w'), indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
