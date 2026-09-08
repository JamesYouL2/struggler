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
from struggler.engine.cards import entry_turn
from struggler.engine.core import SCORING_CARD_REGION
from struggler.engine.replay import HistoryBuilder
from struggler.bots.public_cards import CARDS, card_state
from struggler.bots.strategic import StrategicPlayer

# Checkpoint projection: how many more times each region is expected to
# score, and how soon. A scoring card still to come this deck cycle counts
# once now and once more after the reshuffle; one already in the discard
# only after the reshuffle; a Mid War region's card only from the turn its
# period enters. Southeast Asia scores once, and is removed. Each turn of
# distance discounts the scoring by TURN_DISCOUNT.
TURN_DISCOUNT = 0.8
SEA_WEIGHT = 0.8
CARDS_PER_TURN = 14  # both hands' draws, Early War


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
    """Expected, turn-discounted number of further scorings per region."""
    obs = engine.observe(side)
    reshuffle_in = max(1, -(-obs.draw_pile_size // CARDS_PER_TURN))  # turns until the deck runs out
    weights = {}
    for card, region in SCORING_CARD_REGION.items():
        state = card_state(obs, card)
        if state == 'future':
            weights[region.value] = TURN_DISCOUNT ** (entry_turn(CARDS[card]) - obs.turn)
        elif state == 'discard':
            weights[region.value] = TURN_DISCOUNT ** reshuffle_in
        else:  # in a hand or the draw pile: this cycle and the next one
            weights[region.value] = 1.0 + TURN_DISCOUNT ** reshuffle_in
    state = card_state(obs, 'Southeast_Asia_Scoring')
    weights['SOUTHEAST_ASIA'] = 0.0 if state in ('discard', 'removed') else SEA_WEIGHT
    return weights


def projection(engine, side: Side) -> dict:
    diff = region_bg_diff(engine.board, side)
    weights = scoring_weights(engine, side)
    projected = sum(diff[r] * weights[r] for r in diff)
    return dict(bg_diff=diff, weights={r: round(w, 2) for r, w in weights.items()},
                projected_vp=round(projected, 2))


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
    bot, opponent, seed, side_value, simulations, stop_turn, log_dir = job
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bot', default='mcts', choices=['mcts', 'strategic', 'greedy'])
    parser.add_argument('--opponent', default='strategic', choices=['mcts', 'strategic', 'greedy'])
    parser.add_argument('--seeds', default='4000-4015', help='e.g. 4000-4015 or 1,2,3')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--simulations', type=int, default=24)
    parser.add_argument('--stop-turn', type=int, default=0, help='0 plays the whole game')
    parser.add_argument('--report', help='write per-game records and the summary here')
    parser.add_argument('--log-dir', help='write each game\'s INFO log here as <seed>-<side>.info.log')
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
    jobs = [(args.bot, args.opponent, seed, side, args.simulations, args.stop_turn, args.log_dir)
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
    print(json.dumps(summary))
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(dict(summary=summary, games=games), f, indent=1)


if __name__ == '__main__':
    main()
