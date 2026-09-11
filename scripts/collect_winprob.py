"""Training data for a win-probability estimator.

The maintainer's proposed first shape: win% as a function of the VP
difference plus the board position expressed in VP, the board part weighted
by turn. Two things make it worth fitting rather than guessing.

**It is the answer to four separate questions** -- the whole Late War
table, Wargames, Terrorism, and what the game-swing constant should be --
and it appears nowhere in `src/`. Each of those is currently a constant
where the truth is a function.

**And it must be clipped, not merely fitted.** The maintainer puts the real
ceiling at 0.75 to 0.90 at the start of a turn even from a dominant board,
because you cannot force a win; an estimator that reports 0.99 inverts the
term it feeds, since the point of knowing you are behind is to start taking
DEFCON and Europe Control shots. A model fitted to outcomes alone will
saturate, so the ceiling is a constraint on the output, not something the
data will teach.

One row per turn start per seat, with the eventual result. Also recorded:
`to_twenty`, the distance to the auto-victory that ends the game the
instant it is reached -- the maintainer's "getting to exactly 20 VP"
tension, and a discontinuity a plain logistic on VP will not find by
itself.

    uv run python scripts/collect_winprob.py --seeds 4000-4039 --out winprob.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from struggler.bots.strategic import StrategicPlayer
from struggler.engine import Engine, Side


def parse_seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def play(seed: int) -> list[dict]:
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    rows: list[dict] = []
    seen: set[tuple[int, str]] = set()
    while not engine.is_terminal:
        decision = engine.pending_decision
        if decision.actor is Side.CHANCE:
            engine.step(decision.options[0])
            continue
        side = decision.actor
        key = (engine.turn, side.value)
        if key not in seen and engine.action_round >= 1:
            seen.add(key)
            obs = engine.observe(side)
            bot = bots[side]
            try:
                bot.rank_actions(obs)
                vp_price = bot.vp_value(obs) or 1.0
                # The board expressed in VP, from this seat: what the
                # position is worth beyond what is already banked.
                board_vp = bot.evaluate(obs) / vp_price
            except Exception:            # a probe must never change the game
                continue
            signed = engine.vp if side is Side.US else -engine.vp
            rows.append({
                'seed': seed, 'turn': engine.turn, 'side': side.value,
                'vp': signed,                      # banked, from this seat
                'board_vp': board_vp,              # unbanked, from this seat
                'to_twenty': 20 - signed,          # distance to auto-victory
                'defcon': engine.defcon,
                'milops': engine.military_ops[side.value],
                'space': engine.space_race[side.value],
            })
        engine.step(bots[side].choose_action(engine.observe(side), list(decision.options)))
    # Label every row with the result from its own seat.
    final = engine.vp
    for row in rows:
        seat_vp = final if row['side'] == 'US' else -final
        row['won'] = int(seat_vp > 0)
        row['final_vp'] = seat_vp
        row['end_turn'] = engine.turn
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seeds', default='4000-4039')
    ap.add_argument('--out', default='models/winprob-samples.json')
    args = ap.parse_args(argv)
    start = time.time()
    rows: list[dict] = []
    for seed in parse_seeds(args.seeds):
        rows.extend(play(seed))
        print(f'seed {seed}: {len(rows)} rows so far', file=sys.stderr, flush=True)
    with open(args.out, 'w') as handle:
        json.dump({'version': 1, 'rows': rows}, handle)
    print(f'{len(rows)} rows -> {args.out} in {time.time()-start:.0f}s')


if __name__ == '__main__':
    sys.exit(main())
