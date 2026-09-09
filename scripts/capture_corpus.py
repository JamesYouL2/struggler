#!/usr/bin/env python
"""Capture the parity corpus: positions from strategic-vs-strategic games
on the gate seeds, with the current evaluator's and planner's outputs.

Each record holds the serialized engine (so the exact position, hand and
decision can be rebuilt), the side to act, and outputs: the full ranking
with safety keys, country values, region scores and margins, the Ops
scale, and the planner's whole-hand and per-card risks. Regenerate only
by an explicit, reviewed commit: this file is the reference every later
refactor and any native kernel is compared against (docs/RUST_PORT_PLAN.md).

    python scripts/capture_corpus.py --seeds 4000-4003 --out tests/corpus/positions.json.gz
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time

from struggler.engine import DecisionKind as K, Engine, Region, Side
from struggler.bots.benchmark import parse_seeds
from struggler.bots.strategic import StrategicPlayer

CAPTURE_KINDS = (K.HEADLINE_PLAY, K.ACTION_ROUND_PLAY, K.PLAY_MODE, K.OPS_TYPE, K.PLACE_INFLUENCE, K.COUP_TARGET)
CAPTURE_TURNS = (1, 3, 5, 7, 9)
CAPTURE_ROUNDS = (1, 3, 6)


def outputs(bot: StrategicPlayer, engine: Engine, side: Side) -> dict:
    obs = engine.observe(side)
    ranked = bot.rank_actions(obs)
    board = bot.board
    rec = {
        'ranking': [{'payload': a.payload, 'key': list(key)} for key, a in ranked],
        'country_value': {c: bot.country_value(board, c, side) for c in board.countries},
        'region_score': {r.name: bot.region_score(board, r, side) for r in Region},
        'region_margin': {r.name: bot.region_margin(board, r, side) for r in Region},
        'ops_value': {n: bot.ops_value(obs, n) for n in (1, 2, 3, 4)},
    }
    planner = bot._planner
    if planner is not None:
        rec['planner'] = {
            'whole_hand_risk': planner.risk(),
            'card_risk': {c: planner.risk(c) for c in obs.hand},
            'event_risk': {c: planner.event_risk(c) for c in obs.hand},
            'hazardous': {c: bool(planner.hazardous(c)) for c in obs.hand},
            'nodes': planner.nodes,
        }
    return rec


def capture(seed: int) -> list[dict]:
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    records = []
    while not engine.is_terminal:
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        side = d.actor
        want = (d.kind in CAPTURE_KINDS and engine.turn in CAPTURE_TURNS
                and (engine.action_round in CAPTURE_ROUNDS or d.kind is K.HEADLINE_PLAY)
                and not d.context.get('setup'))
        if want:
            state = engine.serialize()
            rec = outputs(bots[side], engine, side)
            records.append({'seed': seed, 'turn': engine.turn, 'action_round': engine.action_round,
                            'side': side.value, 'kind': d.kind.value, 'engine': state, **rec})
        action = bots[side].choose_action(engine.observe(side), [])
        engine.step(action)
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seeds', default='4000-4003')
    parser.add_argument('--out', default='tests/corpus/positions.json.gz')
    args = parser.parse_args(argv)
    start = time.time()
    records = []
    for seed in parse_seeds(args.seeds):
        records.extend(capture(seed))
        print(f'seed {seed}: {len(records)} records so far', file=sys.stderr)
    with gzip.open(args.out, 'wt') as f:
        json.dump({'version': 1, 'records': records}, f, sort_keys=True)
    print(f'{len(records)} positions -> {args.out} in {time.time()-start:.0f}s')


if __name__ == '__main__':
    main()
