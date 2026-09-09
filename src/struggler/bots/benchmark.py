"""Paired-seat benchmark of one bot kind against another, with checkpoints.

Every seed is played twice, once per seating. A full game reports the win
rate; a checkpoint (`--stop-turn N`) stops at the end of turn N and reports
the position instead, signed for the benchmarked seat: VP scored, DEFCON,
the strategic board value, and a projection of the VP still to come from
battleground control (per region, weighted by how many more times and how
soon that region is expected to score; see `scoring_weights`). Checkpoints after turn 1 (opening), turn 3 (end of
the Early War) and turn 7 (end of the Mid War) are cheap, low-variance
proxies; the full game remains the final check, since a checkpoint score
can be farmed at the late game's expense.

    python -m struggler.bots.benchmark --bot mcts --opponent strategic \
        --seeds 4000-4015 --workers 8 --stop-turn 1 --report out.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
from multiprocessing import Pool

from struggler.engine import Engine, Region, Side, Subregion
from struggler.engine.core import SCORING_CARD_REGION
from struggler.engine.replay import HistoryBuilder
from struggler.bots.public_cards import scoring_schedule
from struggler.bots.strategic import StrategicPlayer

# Checkpoint projection: how many more times each region is expected to
# score, and how soon (bots.public_cards.scoring_schedule). Each turn of
# distance discounts the scoring by TURN_DISCOUNT.
TURN_DISCOUNT = 0.8
SEA_WEIGHT = 0.8


def region_bg_diff(board, side: Side) -> dict[str, int]:
    """Battleground control difference per region (and Southeast Asia), for `side`."""
    diff = {r.value: 0 for r in Region}
    diff['SOUTHEAST_ASIA'] = 0
    for cid, info in board.countries.items():
        if not info.battleground:
            continue
        controller = board.control(cid)
        sign = 1 if controller is side else -1 if controller is side.opponent else 0
        diff[info.region.value] += sign
        if Subregion.SOUTHEAST_ASIA in info.subregions:
            diff['SOUTHEAST_ASIA'] += sign
    return diff


def scoring_weights(engine, side: Side) -> dict[str, float]:
    """Expected, turn-discounted number of further scorings per region
    (the bots' `scoring_schedule`, with SEA_WEIGHT for Southeast Asia)."""
    obs = engine.observe(side)
    weights = {region.value: sum(TURN_DISCOUNT ** t for t in scoring_schedule(obs, card))
               for card, region in SCORING_CARD_REGION.items()}
    weights['SOUTHEAST_ASIA'] = SEA_WEIGHT * sum(TURN_DISCOUNT ** t for t in scoring_schedule(obs, 'Southeast_Asia_Scoring'))
    return weights


def projection(engine, side: Side) -> dict:
    diff = region_bg_diff(engine.board, side)
    weights = scoring_weights(engine, side)
    projected = sum(diff[r] * weights[r] for r in diff)
    return dict(bg_diff=diff, weights={r: round(w, 2) for r, w in weights.items()},
                projected_vp=round(projected, 2))


def load_module(path: str):
    """Import a bot module from a file: `strategic@/path/to/old_strategic.py`
    plays an earlier version of the policy against the current one."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('struggler_benchmark_' + str(abs(hash(path))), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def build(kind: str, seed: int, simulations: int, model: str | None = None):
    """`kind` is mcts | strategic | greedy, optionally `strategic@<file.py>` to
    load that version of the policy; `model` is a strategic weights JSON."""
    kind, _, path = kind.partition('@')
    weights = None
    if model:
        from struggler.bots.strategic import StrategicWeights
        weights = StrategicWeights.load(model)
    if kind == 'strategic':
        cls = load_module(path).StrategicPlayer if path else StrategicPlayer
        return cls(weights)
    if kind == 'mcts':
        from struggler.bots.mcts import MCTSPlayer
        # STRUGGLER_ROLLOUT_OPTIONS='{"full_planner": true}' switches RolloutPolicy ablations.
        options = json.loads(os.environ.get('STRUGGLER_ROLLOUT_OPTIONS', '{}'))
        return MCTSPlayer(weights, seed=seed, simulations=simulations, rollout_options=options,
                          search_all=os.environ.get('STRUGGLER_MCTS_SEARCH_ALL') == '1')
    if kind == 'greedy':
        from struggler.bots.greedy import GreedyPlayer
        return GreedyPlayer()
    raise ValueError(f'unknown bot kind {kind!r}')


def play(job: tuple) -> dict:
    bot, opponent, seed, side_value, simulations, stop_turn, log_dir, model = job
    if log_dir:
        # One INFO log per game so any benchmark game can be reviewed as played.
        root = logging.getLogger('struggler')
        root.handlers.clear()
        handler = logging.FileHandler(os.path.join(log_dir, f'{seed}-{side_value}.info.log'), mode='w')
        handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    else:
        logging.disable(logging.CRITICAL)
    side = Side(side_value)
    players = {side: build(bot, seed, simulations, model), side.opponent: build(opponent, seed, simulations)}
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    history = HistoryBuilder()
    start = time.time()
    searches = search_seconds = 0.
    while not engine.is_terminal and not (stop_turn and engine.turn > stop_turn):
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            action = d.options[0]
        else:
            player = players[d.actor]
            action = player.choose_action(engine.observe(d.actor), history.history)
            last = getattr(player, 'last_search', None)
            if player is players[side] and last:
                searches += 1
                search_seconds += last['seconds']
                player.last_search = None
        engine.step(action)
        history.record(d, action, engine)
    sign = 1 if side is Side.US else -1
    winner = engine.winner
    value = StrategicPlayer().value(engine.board, side)
    outlook = projection(engine, side)
    return dict(seed=seed, bot_side=side_value, finished=engine.is_terminal, **outlook,
                total=round(sign * engine.vp + outlook['projected_vp'], 2),
                winner=None if winner is None else winner.value, reason=engine.game_over_reason,
                turn=engine.turn, vp=engine.vp, signed_vp=sign * engine.vp, defcon=engine.defcon,
                value=round(value, 2), seconds=round(time.time() - start, 1),
                searches=int(searches), search_seconds=round(search_seconds, 1),
                result=None if not engine.is_terminal else 0.5 if winner is None else float(winner is side))


def parse_seeds(spec: str) -> list[int]:
    seeds = []
    for part in spec.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def summarize(games: list[dict], stop_turn: int) -> dict:
    finished = [g for g in games if g['finished']]
    summary = dict(games=len(games), stop_turn=stop_turn, finished=len(finished),
                   nuclear_losses=sum(g['reason'] == 'defcon_1' and g['winner'] != g['bot_side'] for g in games),
                   mean_signed_vp=round(statistics.fmean(g['signed_vp'] for g in games), 2),
                   mean_projected_vp=round(statistics.fmean(g['projected_vp'] for g in games), 2),
                   mean_total=round(statistics.fmean(g['total'] for g in games), 2),
                   mean_bg_diff={r: round(statistics.fmean(g['bg_diff'][r] for g in games), 2)
                                 for r in games[0]['bg_diff']},
                   mean_value=round(statistics.fmean(g['value'] for g in games), 2),
                   mean_defcon=round(statistics.fmean(g['defcon'] for g in games), 2),
                   mean_game_seconds=round(statistics.fmean(g['seconds'] for g in games), 1))
    if finished:
        summary['score'] = round(statistics.fmean(g['result'] for g in finished), 3)
    total = sum(g['searches'] for g in games)
    if total:
        summary['mean_search_seconds'] = round(sum(g['search_seconds'] for g in games) / total, 2)
    return summary


def opening_board(seed: int, book=None):
    """The board after the opening book, before the headline."""
    from struggler.bots.strategic import StrategicPlayer
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bot = book or StrategicPlayer()
    placed = []
    while engine.pending_decision.context.get('setup'):
        d = engine.pending_decision
        action = bot.choose_action(engine.observe(d.actor), [])
        placed.append((d.actor.value, action.payload['country']))
        engine.step(action)
    return engine, placed


def event_table(seed: int, weights=None, out=sys.stdout) -> None:
    """Every Early War event's value on the opening board, from each seat,
    with the Ops scale beside it: the review table. Read it against your
    own judgement; every row that disagrees is a value-function gap."""
    from struggler.engine.cards import entry_turn
    from struggler.bots.public_cards import CARDS
    from struggler.bots.strategic import (HIDDEN_INFO_EVENTS, OPS_MODIFIER_EVENTS, StrategicPlayer)
    engine, placed = opening_board(seed)
    print(f'seed {seed} opening: ' + ', '.join(f'{s} {c}' for s, c in placed), file=out)
    views, ops = {}, {}
    for side in (Side.US, Side.USSR):
        obs = engine.observe(side)
        bot = StrategicPlayer(weights)
        bot.rank_actions(obs)
        views[side] = {c.id: bot.event_value(obs, c.id) for c in CARDS.values()
                       if not c.scoring and entry_turn(c) <= 1 and c.id != 'The_China_Card'}
        ops[side] = {n: bot.ops_value(obs, n) for n in (1, 2, 3, 4)}
    print(f"{'card':<34}{'side':>8}{'ops':>4}{'US view':>10}{'USSR view':>11}  how", file=out)
    for cid in sorted(views[Side.US], key=lambda c: -abs(views[Side.US][c])):
        card = CARDS[cid]
        how = ('modifier' if cid in OPS_MODIFIER_EVENTS else 'estimate' if cid in HIDDEN_INFO_EVENTS else 'sandbox')
        print(f"{cid:<34}{card.side.value:>8}{card.ops:>4}{views[Side.US][cid]:>10.1f}{views[Side.USSR][cid]:>11.1f}  {how}", file=out)
    for side in (Side.US, Side.USSR):
        print(f"{side.value} Ops worth: " + ', '.join(f'{n} Ops = {v:.1f}' for n, v in ops[side].items()), file=out)


def to_ops(value: float, scale: dict[int, float]) -> float:
    """Convert a bot value to Ops on the bot's own (concave) Ops scale by
    piecewise-linear interpolation, extrapolating past the last point."""
    sign = -1 if value < 0 else 1
    v = abs(value)
    points = [(0, 0.)] + sorted(scale.items())
    for (n0, v0), (n1, v1) in zip(points, points[1:]):
        if v <= v1:
            return sign * (n0 + (v-v0) / (v1-v0) if v1 > v0 else n0)
    (n0, v0), (n1, v1) = points[-2], points[-1]
    return sign * (n1 + (v-v1) / (v1-v0)) if v1 > v0 else sign * n1


def expert_check(path: str, seed: int, weights=None, out=sys.stdout) -> int:
    """Diff the bot's turn-1 valuations against the expert's, in US Ops.
    Prints every priced row with the difference, the unfilled rows as a
    to-do list, and the ordering constraints; returns the number of
    misses (differences over the file's tolerance, plus broken orders)."""
    from struggler.bots.strategic import StrategicPlayer
    from struggler.bots.public_cards import CARDS
    expert = json.load(open(path))
    engine, _ = opening_board(seed)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer(weights)
    bot.rank_actions(obs)
    scale = {n: bot.ops_value(obs, n) for n in (1, 2, 3, 4)}
    tol = expert.get('tolerance_ops', 0.5)
    got: dict[str, float] = {}
    for cid, row in expert['cards'].items():
        if cid not in CARDS:
            raise ValueError(f'expert_valuations: unknown card {cid}')
        got[cid] = to_ops(bot.event_value(obs, cid), scale)
    for cid, row in expert.get('footholds', {}).items():
        if cid.startswith('_'):
            continue
        got['foothold:' + cid] = to_ops(bot.country_value(bot.board, cid, Side.US), scale)
    # First-Op placements, ranked: the expert's order per seat against the bot's.
    placements = expert.get('placement_rank', {})
    for seat, order in placements.items():
        if seat.startswith('_') or not order:
            continue
        side = Side[seat]
        sobs = engine.observe(side)
        sbot = StrategicPlayer(weights)
        sbot.rank_actions(sobs)
        values = {c: sbot.influence(sobs, c, 1) for c in order}
        got['placement:' + seat] = values
    misses, todo = 0, []
    print(f"expert check on {expert['board']} (US Ops; 1 Op = {scale[1]:.1f}, tolerance {tol})", file=out)
    print(f"{'row':<40}{'expert':>8}{'bot':>8}{'diff':>8}  note", file=out)
    rows = [(k, v) for k, v in expert['cards'].items()] + \
           [('foothold:' + k, v) for k, v in expert.get('footholds', {}).items() if not k.startswith('_')]
    for key, row in rows:
        want = row.get('ops')
        if want is None:
            todo.append(key)
            continue
        diff = got[key] - want
        flag = ' <-- ' if abs(diff) > tol else '     '
        misses += abs(diff) > tol
        print(f"{key:<40}{want:>8.2f}{got[key]:>8.2f}{diff:>+8.2f}{flag}{row.get('note', '')}", file=out)
    for a, rel, b in expert.get('order', []):
        ok = got[a] > got[b] if rel == 'better_for_us_than' else got[a] < got[b]
        misses += not ok
        print(f"{'ORDER ok ' if ok else 'ORDER BROKEN'} {a} {rel} {b}: {got[a]:+.2f} vs {got[b]:+.2f}", file=out)
    for seat, order in placements.items():
        if seat.startswith('_') or not order:
            continue
        values = got['placement:' + seat]
        inversions = [(a, b) for i, a in enumerate(order) for b in order[i+1:] if values[a] < values[b]]
        misses += len(inversions)
        bot_order = sorted(order, key=lambda c: -values[c])
        print(f"PLACEMENT {seat}: {len(inversions)} inversions in {len(order)} ranked; bot order: {' > '.join(bot_order)}", file=out)
        for a, b in inversions:
            print(f"  {a} should beat {b}: {values[a]:.1f} vs {values[b]:.1f}", file=out)
    if todo:
        print('unpriced (fill in models/expert_valuations.json):', file=out)
        for key in todo:
            print(f"  {key:<38} bot says {got[key]:+.2f} Ops", file=out)
    print(f'{misses} misses', file=out)
    return misses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bot', default='mcts', help='mcts | strategic | greedy; strategic@<file.py> loads that version')
    parser.add_argument('--opponent', default='strategic', help='as --bot')
    parser.add_argument('--seeds', default='4000-4015', help='e.g. 4000-4015 or 1,2,3')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--simulations', type=int, default=24)
    parser.add_argument('--stop-turn', type=int, default=0, help='0 plays the whole game')
    parser.add_argument('--report', help='write per-game records and the summary here')
    parser.add_argument('--log-dir', help='write each game\'s INFO log here as <seed>-<side>.info.log')
    parser.add_argument('--bot-weights', help='strategic weights JSON for --bot only (the opponent keeps defaults)')
    parser.add_argument('--table', action='store_true',
                        help='print the turn-1 event-value review table for the first seed and exit')
    parser.add_argument('--expert', metavar='JSON',
                        help='diff the turn-1 valuations against this expert file, in US Ops, and exit')
    args = parser.parse_args(argv)
    if args.table or args.expert:
        weights = None
        if args.bot_weights:
            from struggler.bots.strategic import StrategicWeights
            weights = StrategicWeights.load(args.bot_weights)
        if args.table:
            event_table(parse_seeds(args.seeds)[0], weights)
        if args.expert:
            expert_check(args.expert, parse_seeds(args.seeds)[0], weights)
        return
    seeds = parse_seeds(args.seeds)
    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
    jobs = [(args.bot, args.opponent, seed, side, args.simulations, args.stop_turn, args.log_dir, args.bot_weights)
            for seed in seeds for side in ('US', 'USSR')]
    start = time.time()
    games = []
    with Pool(args.workers) as pool:
        for game in pool.imap_unordered(play, jobs, chunksize=1):
            games.append(game)
            print(f"{len(games):3d}/{len(jobs)} seed {game['seed']} {game['bot_side']:<4} T{game['turn']} "
                  f"vp={game['signed_vp']:+d} proj={game['projected_vp']:+.1f} defcon={game['defcon']} "
                  f"{game['reason'] or '...'} {game['seconds']}s", file=sys.stderr, flush=True)
    games.sort(key=lambda g: (g['seed'], g['bot_side']))
    summary = summarize(games, args.stop_turn)
    summary['wall_seconds'] = round(time.time() - start, 1)
    summary['bot'], summary['opponent'], summary['simulations'] = args.bot, args.opponent, args.simulations
    summary['bot_weights'] = args.bot_weights
    print(json.dumps(summary))
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(dict(summary=summary, games=games), f, indent=1)


if __name__ == '__main__':
    main()
