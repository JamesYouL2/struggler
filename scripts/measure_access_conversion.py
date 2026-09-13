#!/usr/bin/env python
"""How often does reach become control?

`access` prices a holding by the uncontrolled battlegrounds it lets a side
reach, weighted by three guessed constants (`access`, `access_redundant`,
`access_contested` -- all `guess / underdetermined` in provenance.json).
docs/notes/claude/2026-09-12-access-wants-a-conversion-probability.md argues
they collapse into ONE measurable quantity:

    p = P(we control an adjacent battleground by the time its region next
        scores | we hold a neighbour of it now)

because with `k` routes already in place the marginal route is worth
`p(1-p)^k`, so `access_redundant` -- the ratio of the second route to the
first -- is exactly `1 - p`. The shipped 0.35 asserts p ~ 0.65 and has never
been measured. This measures it.

Reach is defined as the first-hop term defines it: side `s` holds influence
in some neighbour of battleground `n`, and does not control `n`. The
opportunity is opened once per turn per (side, battleground) and resolved
when `n`'s region next scores -- the horizon the value function actually
prices against, since a battleground pays at scoring and not before.

Also measures RETENTION, the same walk with the condition flipped:
P(still control at the next scoring | control now). That is the flip
discount -- how much of a battleground's value survives to be scored -- and
`wipe_risk` is one component of it (a 3-4 Ops coup removing every point).
Measuring the whole thing directly is what lets the component go.

    python scripts/measure_access_conversion.py --seeds 4000-4007

Reports p by stability, which is the shape the formula wants: `p` should be
a function of stability and standing influence, not a constant. It is NOT a
strength measurement and says nothing about whether the access term helps.
"""
from __future__ import annotations

import argparse
import collections
import statistics
import sys

from struggler.engine import Engine, Region, Side
from struggler.engine.core import SCORING_CARD_REGION
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.benchmark import parse_seeds

SIDES = (Side.US, Side.USSR)


def held(engine, side: Side) -> set[str]:
    """Battlegrounds `side` controls right now."""
    return {cid for cid, info in engine.board.countries.items()
            if info.battleground and engine.board.control(cid) is side}


def opportunities(engine, side: Side) -> set[str]:
    """Battlegrounds `side` reaches from a holding but does not control."""
    board = engine.board
    out = set()
    for cid, info in board.countries.items():
        if not info.battleground or board.control(cid) is side:
            continue
        # `neighbors` includes the superpowers ('US'/'USSR') for home-adjacent
        # countries, which are not places anyone holds influence.
        if any(board.influence[n][side.value] > 0
               for n in board.neighbors(cid) if n in board.influence):
            out.add(cid)
    return out


def play(seed: int, stats, opened, keep) -> None:
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {s: StrategicPlayer() for s in SIDES}
    # (side, country) -> turn it was opened; resolved at the next scoring.
    live: dict[tuple[Side, str], int] = {}
    holding: dict[tuple[Side, str], int] = {}
    contested: dict[tuple[Side, str], bool] = {}
    seen_turn = -1
    steps = 0
    while not engine.is_terminal and steps < 20000:
        steps += 1
        if engine.turn != seen_turn:
            seen_turn = engine.turn
            for s in SIDES:
                for cid in opportunities(engine, s):
                    live.setdefault((s, cid), engine.turn)
                for cid in held(engine, s):
                    if (s, cid) not in holding:
                        holding[(s, cid)] = engine.turn
                        foe = Side.US if s is Side.USSR else Side.USSR
                        contested[(s, cid)] = engine.board.is_reachable(foe, cid)
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            action = d.options[0]
        else:
            action = bots[d.actor].choose_action(engine.observe(d.actor), [])
        region = SCORING_CARD_REGION.get((action.payload or {}).get('card') or '')
        engine.step(action)
        if region is None:
            continue
        # The region just scored: every live opportunity in it is decided.
        for (s, cid), turn in list(live.items()):
            if engine.board.countries[cid].region is not region:
                continue
            got = engine.board.control(cid) is s
            stab = engine.board.countries[cid].stability
            stats[stab].append(got)
            opened[stab] += 1
            del live[(s, cid)]
        for (s, cid), turn in list(holding.items()):
            if engine.board.countries[cid].region is not region:
                continue
            info = engine.board.countries[cid]
            # Split by whether the OPPONENT could reach it when we took it.
            # Stability alone cannot say why a stability-4 battleground is a
            # bad hold: the maintainer's reason for Israel is "the US takes
            # Egypt first", which is contest, not cost.
            keep[(info.stability, contested.get((s, cid), False))].append(
                engine.board.control(cid) is s)
            del holding[(s, cid)]
            contested.pop((s, cid), None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='4000-4007')
    args = ap.parse_args(argv)
    stats: dict[int, list[bool]] = collections.defaultdict(list)
    keep: dict[int, list[bool]] = collections.defaultdict(list)
    opened: collections.Counter = collections.Counter()
    seeds = parse_seeds(args.seeds)
    for i, seed in enumerate(seeds, 1):
        play(seed, stats, opened, keep)
        print(f'  seed {seed} done ({i}/{len(seeds)})', file=sys.stderr, flush=True)

    print(f'\nreach -> control, over {len(seeds)} games')
    print(f'{"stability":>10} {"n":>6} {"p":>8}')
    allv = []
    for stab in sorted(stats):
        v = stats[stab]
        allv += v
        print(f'{stab:>10} {len(v):>6} {statistics.fmean(v):>8.3f}')
    if allv:
        p = statistics.fmean(allv)
        print(f'{"all":>10} {len(allv):>6} {p:>8.3f}')
        print(f'\n  implied access_decay = 1/(1-p) = {1 / (1 - p):.3f}'
              f'   (shipped: 1.445)')
        print('  `access()` discounts the k-th route into a battleground by')
        print('  access_decay ** (1 - k), all k routes carrying the same weight.')
        print('  That is the geometric form of P(control) = 1 - (1-p)^k.')
    print(f'\nretention -> still controlled when the region next scores')
    print(f'{"stability":>10} {"contested":>11} {"n":>6} {"keep":>8}')
    allk = []
    for key in sorted(keep):
        v = keep[key]; allk += v
        stab, con = key
        print(f'{stab:>10} {con!s:>11} {len(v):>6} {statistics.fmean(v):>8.3f}')
    if allk:
        print(f'{"all":>10} {"":>11} {len(allk):>6} {statistics.fmean(allk):>8.3f}')
        print('  This is the flip discount: the share of a battleground\'s value that')
        print('  survives to be scored. wipe_risk models one component of it.')
    print('\n  Not a strength measurement. It says how often reach becomes control,')
    print('  not whether pricing reach that way helps the bot win.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
