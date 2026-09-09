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
    """The production ranking from the in-game bot, then diagnostic probes
    on an independent instance (Astra: the planner's node budget is shared
    across calls on one instance, so probing every card on the production
    planner could push it into conservative results; and evaluator probes
    must not prime the production policy). `production_nodes` is the
    budget the real ranking consumed; `probe_order` is the sequence the
    probes were asked in, which the parity test replays."""
    from dataclasses import asdict
    obs = engine.observe(side)
    ranked = bot.rank_actions(obs)
    rec = {
        'ranking': [{'payload': a.payload, 'key': list(key)} for key, a in ranked],
        'production_nodes': bot._planner.nodes if bot._planner is not None else None,
        'prior': asdict(bot.survival_prior),
        'options': [a.payload for a in obs.pending_decision.options],
        'context': {k: v for k, v in obs.pending_decision.context.items()
                    if isinstance(v, (int, float, str, bool, list, tuple, type(None)))},
    }
    probe = StrategicPlayer(bot.weights, survival_prior=bot.survival_prior)
    probe.rank_actions(obs)
    board = probe.board
    rec.update({
        'country_value': {c: probe.country_value(board, c, side) for c in board.countries},
        'region_score': {r.name: probe.region_score(board, r, side) for r in Region},
        'region_margin': {r.name: probe.region_margin(board, r, side) for r in Region},
        'ops_value': {n: probe.ops_value(obs, n) for n in (1, 2, 3, 4)},
    })
    planner = probe._planner
    if planner is not None:
        order = ['whole_hand'] + [f'risk:{c}' for c in obs.hand] + [f'event_risk:{c}' for c in obs.hand] \
            + [f'hazardous:{c}' for c in obs.hand]
        rec['planner'] = {
            'probe_order': order,
            'whole_hand_risk': planner.risk(),
            'card_risk': {c: planner.risk(c) for c in obs.hand},
            'event_risk': {c: planner.event_risk(c) for c in obs.hand},
            'hazardous': {c: bool(planner.hazardous(c)) for c in obs.hand},
            'nodes_after_probes': planner.nodes,
            'truncated': planner.nodes > planner.prior.max_states,
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
    import subprocess
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', 'src'], capture_output=True, text=True).stdout.strip())
    with gzip.open(args.out, 'wt') as f:
        json.dump({'version': 2, 'source_revision': revision, 'dirty': dirty,
                   'python': sys.version, 'records': records}, f, sort_keys=True)
    print(f'{len(records)} positions -> {args.out} in {time.time()-start:.0f}s')


if __name__ == '__main__':
    main()
