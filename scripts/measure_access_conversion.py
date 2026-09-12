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


def play(seed: int, stats, opened) -> None:
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {s: StrategicPlayer() for s in SIDES}
    # (side, country) -> turn it was opened; resolved at the next scoring.
    live: dict[tuple[Side, str], int] = {}
    seen_turn = -1
    steps = 0
    while not engine.is_terminal and steps < 20000:
        steps += 1
        if engine.turn != seen_turn:
            seen_turn = engine.turn
            for s in SIDES:
                for cid in opportunities(engine, s):
                    live.setdefault((s, cid), engine.turn)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='4000-4007')
    args = ap.parse_args(argv)
    stats: dict[int, list[bool]] = collections.defaultdict(list)
    opened: collections.Counter = collections.Counter()
    seeds = parse_seeds(args.seeds)
    for i, seed in enumerate(seeds, 1):
        play(seed, stats, opened)
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
        print(f'\n  implied access_redundant = 1 - p = {1 - p:.3f}   (shipped: 0.35)')
        print('  A second route into the same battleground is worth (1-p) of the')
        print('  first; the k-th is worth (1-p)^(k-1). The shipped constant is flat,')
        print('  so it over-values the third and fourth direction whatever p is.')
    print('\n  Not a strength measurement. It says how often reach becomes control,')
    print('  not whether pricing reach that way helps the bot win.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
