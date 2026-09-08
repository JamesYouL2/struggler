"""Paired-seat benchmark of one bot kind against another, with checkpoints.

Every seed is played twice, once per seating. A full game reports the win
rate; a checkpoint (`--stop-turn N`) stops at the end of turn N and reports
the position instead: VP, DEFCON and the strategic board value, signed for
the benchmarked seat. Checkpoints after turn 1 (opening), turn 3 (end of
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

from struggler.engine import Engine, Side
from struggler.engine.replay import HistoryBuilder
from struggler.bots.strategic import StrategicPlayer


def build(kind: str, seed: int, simulations: int):
    if kind == 'strategic':
        return StrategicPlayer()
    if kind == 'mcts':
        from struggler.bots.mcts import MCTSPlayer
        return MCTSPlayer(seed=seed, simulations=simulations)
    if kind == 'greedy':
        from struggler.bots.greedy import GreedyPlayer
        return GreedyPlayer()
    raise ValueError(f'unknown bot kind {kind!r}')


def play(job: tuple) -> dict:
    bot, opponent, seed, side_value, simulations, stop_turn = job
    logging.disable(logging.CRITICAL)
    side = Side(side_value)
    players = {side: build(bot, seed, simulations), side.opponent: build(opponent, seed, simulations)}
    engine = Engine.new_game(seed=seed)
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
    return dict(seed=seed, bot_side=side_value, finished=engine.is_terminal,
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
                   mean_value=round(statistics.fmean(g['value'] for g in games), 2),
                   mean_defcon=round(statistics.fmean(g['defcon'] for g in games), 2),
                   mean_game_seconds=round(statistics.fmean(g['seconds'] for g in games), 1))
    if finished:
        summary['score'] = round(statistics.fmean(g['result'] for g in finished), 3)
    total = sum(g['searches'] for g in games)
    if total:
        summary['mean_search_seconds'] = round(sum(g['search_seconds'] for g in games) / total, 2)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bot', default='mcts', choices=['mcts', 'strategic', 'greedy'])
    parser.add_argument('--opponent', default='strategic', choices=['mcts', 'strategic', 'greedy'])
    parser.add_argument('--seeds', default='4000-4015', help='e.g. 4000-4015 or 1,2,3')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--simulations', type=int, default=24)
    parser.add_argument('--stop-turn', type=int, default=0, help='0 plays the whole game')
    parser.add_argument('--report', help='write per-game records and the summary here')
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    jobs = [(args.bot, args.opponent, seed, side, args.simulations, args.stop_turn)
            for seed in seeds for side in ('US', 'USSR')]
    start = time.time()
    games = []
    with Pool(args.workers) as pool:
        for game in pool.imap_unordered(play, jobs, chunksize=1):
            games.append(game)
            print(f"{len(games):3d}/{len(jobs)} seed {game['seed']} {game['bot_side']:<4} T{game['turn']} "
                  f"vp={game['signed_vp']:+d} defcon={game['defcon']} value={game['value']:+.1f} "
                  f"{game['reason'] or '...'} {game['seconds']}s", file=sys.stderr, flush=True)
    games.sort(key=lambda g: (g['seed'], g['bot_side']))
    summary = summarize(games, args.stop_turn)
    summary['wall_seconds'] = round(time.time() - start, 1)
    summary['bot'], summary['opponent'], summary['simulations'] = args.bot, args.opponent, args.simulations
    print(json.dumps(summary))
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(dict(summary=summary, games=games), f, indent=1)


if __name__ == '__main__':
    main()
