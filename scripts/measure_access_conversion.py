#!/usr/bin/env python
"""How often does reach become control?

FIXED 2026-09-12, audit F1 (docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md):
until then an opportunity resolved when a scoring card was CHOSEN, not when
its region scored, so a cancelled headline or a discarded card resolved
samples from a scoring that never happened and Final Scoring resolved
nothing. It now resolves inside the engine's own scoring (see `Tracker`),
gated by tests/test_access_conversion.py. Every figure printed BEFORE the
fix -- including the ones behind CONVERSION_P and the route decay -- came
from the biased collector.

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
discount -- how much of a battleground's value survives to be scored. The
evaluator's `wipe_risk` modelled one component of it (a 3-4 Ops coup removing
every point); measuring the whole thing directly is what let that component
go, and it was deleted 2026-09-13.

HORIZONS. `--horizons 1,2` resolves the same opportunities at the region's
next scoring AND at the one after, in one pass over the same games. Horizon 1
is the measurement above, unchanged. Horizon 2 is the question in section 4d
of docs/notes/claude/2026-09-13-handoff-for-codex.md: the turn discount asks
about one scoring further out, and `p` at two scorings is that question
asked of the games rather than of a constant. Only scoring CARDS resolve an
opportunity, at every horizon, exactly as before; Final Scoring does not, so
an opportunity still waiting when the game ends is CENSORED and counted,
never silently dropped. Censoring grows with the horizon and is not random --
it is heaviest in the games that end early -- so read `p` beside it.

    python scripts/measure_access_conversion.py --seeds 4000-4007
    python scripts/measure_access_conversion.py --seeds 4000-4095 --horizons 1,2 --workers 8

Reports p by stability, which is the shape the formula wants: `p` should be
a function of stability and standing influence, not a constant. It is NOT a
strength measurement and says nothing about whether the access term helps.
"""
from __future__ import annotations

import argparse
import collections
import functools
import multiprocessing
import statistics
import sys

from struggler.engine import Engine, Side
from struggler.engine.core import Subregion
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


class Tracker:
    """Opportunities and holdings on one engine, resolved when a region
    ACTUALLY scores.

    Resolution hooks the engine's own scoring -- `_score_region_net`, which
    every scoring card except Southeast Asia and all of Final Scoring go
    through, and `_score_southeast_asia` -- on this one instance. That is the
    fix for audit F1: the old collector resolved when an action NAMED a
    scoring card, so a headline Defectors cancelled resolved samples from a
    scoring that never happened, a higher-Ops headline that moved control
    first was not seen, and Final Scoring resolved nothing. The bots' sandbox
    engines are separate instances and are not hooked.

    Samples are taken at the instant of scoring, before the scorer runs;
    scoring moves VP, never influence, so control is what gets scored.
    Southeast Asia scoring resolves Southeast Asia's countries only, because
    that is all it scores.
    """

    def __init__(self, engine, horizons: tuple[int, ...] = (1,)):
        self.engine, self.horizons = engine, horizons
        # (horizon, side, country) -> scorings of its region still to wait for.
        self.live: dict[tuple[int, Side, str], int] = {}
        self.holding: dict[tuple[int, Side, str], int] = {}
        self.contested: dict[tuple[int, Side, str], bool] = {}
        self.reach: dict[tuple[int, int], list[bool]] = collections.defaultdict(list)
        self.keep: dict[tuple[int, int, bool], list[bool]] = collections.defaultdict(list)
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
        """Open this turn's opportunities and holdings."""
        engine = self.engine
        for s in SIDES:
            opps, holds = opportunities(engine, s), held(engine, s)
            foe = Side.US if s is Side.USSR else Side.USSR
            for h in self.horizons:
                for cid in opps:
                    self.live.setdefault((h, s, cid), h)
                for cid in holds:
                    if (h, s, cid) not in self.holding:
                        self.holding[(h, s, cid)] = h
                        self.contested[(h, s, cid)] = engine.board.is_reachable(foe, cid)

    def _resolve(self, in_scope) -> None:
        # A scoring is happening now: everything in it moves one scoring
        # closer, and whatever has none left is decided.
        board = self.engine.board
        for key, left in list(self.live.items()):
            h, s, cid = key
            if not in_scope(cid):
                continue
            if left > 1:
                self.live[key] = left - 1
                continue
            self.reach[(h, board.countries[cid].stability)].append(board.control(cid) is s)
            del self.live[key]
        for key, left in list(self.holding.items()):
            h, s, cid = key
            if not in_scope(cid):
                continue
            if left > 1:
                self.holding[key] = left - 1
                continue
            # Split by whether the OPPONENT could reach it when we took it.
            # Stability alone cannot say why a stability-4 battleground is a
            # bad hold: the maintainer's reason for Israel is "the US takes
            # Egypt first", which is contest, not cost.
            self.keep[(h, board.countries[cid].stability, self.contested.get(key, False))].append(
                board.control(cid) is s)
            del self.holding[key]
            self.contested.pop(key, None)

    def result(self) -> dict:
        stab = self.engine.board.countries
        return dict(
            reach=dict(self.reach), keep=dict(self.keep),
            censored_reach=dict(collections.Counter((h, stab[c].stability) for h, _, c in self.live)),
            censored_keep=dict(collections.Counter((h, stab[c].stability) for h, _, c in self.holding)))


def play(seed: int, horizons: tuple[int, ...] = (1,)) -> dict:
    """One self-play game. Returns plain counts keyed by horizon, so games
    can run in separate processes and merge."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    tracker = Tracker(engine, horizons)
    bots = {s: StrategicPlayer() for s in SIDES}
    seen_turn = -1
    steps = 0
    while not engine.is_terminal and steps < 20000:
        steps += 1
        if engine.turn != seen_turn:
            seen_turn = engine.turn
            tracker.open()
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            action = d.options[0]
        else:
            action = bots[d.actor].choose_action(engine.observe(d.actor), [])
        engine.step(action)
    return tracker.result()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='4000-4007')
    ap.add_argument('--horizons', default='1',
                    help='comma-separated: 1 is the next scoring of the region, 2 the one after')
    ap.add_argument('--workers', type=int, default=1)
    args = ap.parse_args(argv)
    horizons = tuple(sorted({int(h) for h in args.horizons.split(',')}))
    if not horizons or horizons[0] < 1:
        ap.error('horizons are 1 or more')
    reach: dict[tuple[int, int], list[bool]] = collections.defaultdict(list)
    keep: dict[tuple[int, int, bool], list[bool]] = collections.defaultdict(list)
    censored_reach: collections.Counter = collections.Counter()
    censored_keep: collections.Counter = collections.Counter()
    seeds = parse_seeds(args.seeds)
    job = functools.partial(play, horizons=horizons)
    with multiprocessing.Pool(args.workers) as pool:
        for i, (seed, out) in enumerate(zip(seeds, pool.imap(job, seeds), strict=True), 1):
            for k, v in out['reach'].items():
                reach[k] += v
            for k, v in out['keep'].items():
                keep[k] += v
            censored_reach.update(out['censored_reach'])
            censored_keep.update(out['censored_keep'])
            print(f'  seed {seed} done ({i}/{len(seeds)})', file=sys.stderr, flush=True)

    p_first: dict[int, float] = {}
    for h in horizons:
        if len(horizons) > 1:
            print(f'\n== horizon {h}: resolved at scoring {h} of the region after opening')
        print(f'\nreach -> control, over {len(seeds)} games')
        print(f'{"stability":>10} {"n":>6} {"p":>8}' + (f' {"p/p_1":>8}' if h > 1 else ''))
        allv = []
        for stab in sorted(s for hh, s in reach if hh == h):
            v = reach[(h, stab)]
            allv += v
            p = statistics.fmean(v)
            if h == 1:
                p_first[stab] = p
            ratio = (f' {p / p_first[stab]:>8.3f}' if h > 1 and p_first.get(stab) else '')
            print(f'{stab:>10} {len(v):>6} {p:>8.3f}{ratio}')
        if allv:
            p = statistics.fmean(allv)
            if h == 1:
                p_first[0] = p
            ratio = f' {p / p_first[0]:>8.3f}' if h > 1 and p_first.get(0) else ''
            print(f'{"all":>10} {len(allv):>6} {p:>8.3f}{ratio}')
            if h == 1:
                print(f'\n  implied access_decay = 1/(1-p) = {1 / (1 - p):.3f}'
                      f'   (shipped: 1.445)')
                print('  `access()` discounts the k-th route into a battleground by')
                print('  access_decay ** (1 - k), all k routes carrying the same weight.')
                print('  That is the geometric form of P(control) = 1 - (1-p)^k.')
        cens = {s: n for (hh, s), n in sorted(censored_reach.items()) if hh == h}
        print(f'  censored (still waiting at game end), by stability: {cens}')
        print('\nretention -> still controlled when the region next scores')
        print(f'{"stability":>10} {"contested":>11} {"n":>6} {"keep":>8}')
        allk = []
        for key in sorted(k for k in keep if k[0] == h):
            v = keep[key]; allk += v
            _, stab, con = key
            print(f'{stab:>10} {con!s:>11} {len(v):>6} {statistics.fmean(v):>8.3f}')
        if allk:
            print(f'{"all":>10} {"":>11} {len(allk):>6} {statistics.fmean(allk):>8.3f}')
            print('  This is the flip discount: the share of a battleground\'s value that')
            print('  survives to be scored, measured whole rather than modelled in parts.')
        cens = {s: n for (hh, s), n in sorted(censored_keep.items()) if hh == h}
        print(f'  censored (still waiting at game end), by stability: {cens}')
    print('\n  Not a strength measurement. It says how often reach becomes control,')
    print('  not whether pricing reach that way helps the bot win.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
