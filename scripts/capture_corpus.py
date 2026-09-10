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


PLANNER_OPS = ('whole_hand', 'risk', 'event_risk', 'hazardous')


def _gains(bot, obs, cid, ops):
    """`_investment`'s candidate gains: value per Op at each affordable
    point count, in the order it considers them."""
    board = bot.board
    original = dict(board.influence[cid])
    spent, out = 0, []
    try:
        for points in range(1, ops + 1):
            spent += board.influence_cost(obs.side, cid)
            if spent > ops:
                break
            board.influence[cid].update(original)
            out.append(bot.delta(obs, cid, own=points) / spent)
            board.influence[cid][obs.side.value] += points
    finally:
        board.influence[cid].update(original)
    return out


def planner_probes(planner, hand) -> list:
    """Ordered planner queries on one instance, results in query order. The
    node budget is shared across calls, so the order is part of the
    contract; the checker replays exactly this list."""
    probes = [['whole_hand', None, planner.risk()]]
    probes += [['risk', c, planner.risk(c)] for c in hand]
    probes += [['event_risk', c, planner.event_risk(c)] for c in hand]
    probes += [['hazardous', c, bool(planner.hazardous(c))] for c in hand]
    return probes


def outputs(bot: StrategicPlayer, engine: Engine, side: Side) -> dict:
    """The production ranking from the in-game bot, then diagnostic probes
    on independent instances (Astra: the planner's node budget is shared
    across calls on one instance, so probing every card on the production
    planner could push it into conservative results; and evaluator probes
    must not prime the production policy). `production_nodes` is the
    budget the real ranking consumed; `planner.probes` is the ordered
    query list the parity test replays."""
    from dataclasses import asdict
    from struggler.bots.strategic.defcon import SurvivalPrior
    from struggler.bots.rollout import RolloutPolicy
    obs = engine.observe(side)
    d = obs.pending_decision
    ranked = bot.rank_actions(obs)
    rec = {
        'ranking': [{'payload': a.payload, 'key': list(key)} for key, a in ranked],
        'production_nodes': bot._planner.nodes if bot._planner is not None else None,
        'weights': asdict(bot.weights),
        'prior': asdict(bot.survival_prior),
        'options': [a.payload for a in d.options],
        'context': {k: v for k, v in d.context.items()
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
        # Ordered: event pricing shares the planner's budget and caches, so
        # the order the hand was priced in is part of the contract.
        'event_value': [[c, probe.event_value(obs, c)] for c in obs.hand if c != 'The_China_Card'],
    })
    # Direct placement outputs: per-point deltas and the investment choice
    # (value per Op, points) for every placeable candidate, in option order.
    if d.kind in (K.PLACE_INFLUENCE, K.OPS_TYPE):
        ctx = d.context
        ops = int(ctx.get('ops_remaining', ctx.get('remaining', ctx.get('ops', 1))))
        cands = [a.payload['country'] for a in d.options] if d.kind is K.PLACE_INFLUENCE else \
            [c for c in board.countries if board.is_reachable(side, c)]
        rec['placements'] = {'ops': ops, 'candidates': cands,
                             'delta': {c: [probe.delta(obs, c, own=k) for k in range(1, ops + 1)] for c in cands},
                             'investment': {c: list(probe._investment(obs, c, ops)) for c in cands},
                             # Per-point value-per-Op, so the checker can tell a
                             # meaningful choice of point count from a tie that
                             # `_investment`'s strict `>` decides by one ulp.
                             'gains': {c: _gains(probe, obs, c, ops) for c in cands}}
    planner = probe._planner
    if planner is not None:
        rec['planner'] = {'probes': planner_probes(planner, obs.hand), 'nodes_after_probes': planner.nodes,
                          'truncated': planner.nodes > planner.prior.max_states}
        # A deliberately budget-limited planner, same ordered queries: pins
        # the truncation path and the budget semantics.
        limited = StrategicPlayer(bot.weights, survival_prior=SurvivalPrior(max_states=200))
        limited.rank_actions(obs)
        if limited._planner is not None:
            rec['planner_limited'] = {'prior': asdict(limited.survival_prior),
                                      'ranking': [{'payload': a.payload, 'key': list(key)} for key, a in limited.rank_actions(obs)],
                                      'probes': planner_probes(limited._planner, obs.hand),
                                      'nodes_after_probes': limited._planner.nodes,
                                      'truncated': limited._planner.nodes > 200}
    # The rollout policy's own ranking (its OPS_TYPE score has a different
    # tie rule: max over (value, country) tuples).
    if d.kind in (K.OPS_TYPE, K.PLACE_INFLUENCE, K.ACTION_ROUND_PLAY):
        rollout = RolloutPolicy(bot.weights)
        rollout.reset()
        rec['rollout_ranking'] = [{'payload': a.payload, 'key': list(key)} for key, a in rollout.rank_actions(obs)]
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
    import hashlib, pathlib, subprocess
    start = time.time()
    # Provenance, captured before any game runs.
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', 'src', 'scripts/capture_corpus.py'],
                           capture_output=True, text=True).stdout.strip()
    generator_sha = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
    records = []
    for seed in parse_seeds(args.seeds):
        records.extend(capture(seed))
        print(f'seed {seed}: {len(records)} records so far', file=sys.stderr)
    with gzip.open(args.out, 'wt') as f:
        json.dump({'version': 3, 'source_revision': revision, 'dirty_paths': dirty.splitlines(),
                   'generator_sha256': generator_sha, 'python': sys.version, 'records': records}, f, sort_keys=True)
    print(f'{len(records)} positions -> {args.out} in {time.time()-start:.0f}s')


if __name__ == '__main__':
    main()
