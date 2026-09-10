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
import importlib.util
import collections
import itertools
import json
import logging
import math
import os
import random
import statistics
import sys
import time
from multiprocessing import Pool

from struggler.engine import Engine, Region, Side, Subregion
from struggler.engine.core import SCORING_CARD_REGION
from struggler.engine.replay import HistoryBuilder
from struggler.bots.public_cards import scoring_schedule, turns_to_final_scoring
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
    (the bots' `scoring_schedule`, with SEA_WEIGHT for Southeast Asia, plus
    the final scoring every region gets at the end of the last turn)."""
    obs = engine.observe(side)
    final = TURN_DISCOUNT ** turns_to_final_scoring(obs)
    weights = {region.value: final + sum(TURN_DISCOUNT ** t for t in scoring_schedule(obs, card))
               for card, region in SCORING_CARD_REGION.items()}
    weights['SOUTHEAST_ASIA'] = SEA_WEIGHT * sum(TURN_DISCOUNT ** t for t in scoring_schedule(obs, 'Southeast_Asia_Scoring'))
    return weights


def projection(engine, side: Side) -> dict:
    diff = region_bg_diff(engine.board, side)
    weights = scoring_weights(engine, side)
    projected = sum(diff[r] * weights[r] for r in diff)
    return dict(bg_diff=diff, weights={r: round(w, 2) for r, w in weights.items()},
                projected_vp=round(projected, 2))


def _exec_file(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


class _SnapshotFinder:
    """Resolves `struggler.bots.<name>` to a directory of snapshotted sources.

    Installed only while a baseline policy is being imported. Anything the
    snapshot does not contain -- the whole of `struggler.engine`, above all --
    falls through to normal resolution, which is the point: the engine is the
    shared arbiter both sides are measured under, and only the bot is being
    compared.
    """

    PREFIX = 'struggler.bots.'

    def __init__(self, directory: str):
        self.directory = directory

    def source_for(self, fullname: str) -> tuple[str, bool] | None:
        """The snapshot file backing `fullname`, and whether it is a package.

        A snapshotted *package* resolves to its `__init__.py`, and the spec
        below gives it `submodule_search_locations` inside the snapshot, so
        its submodules come from the snapshot too -- that is what the
        package's own `__path__` is then used for, and it is the part that
        matters. Without it a baseline `strategic/` package fell through to
        normal resolution and bound the *candidate's* `strategic`: the
        baseline would have been measured partly against its own code, the
        same contamination that twice made a gate compare a change with
        itself. Pinned by
        `test_a_snapshotted_package_binds_its_own_submodules`, which fails
        with package detection removed.

        Dotted names resolve as well, which normal parent-first importing
        makes redundant in practice; it is kept so a direct import of a
        submodule cannot find a hole.
        """
        if not fullname.startswith(self.PREFIX):
            return None
        relative = fullname[len(self.PREFIX):].split('.')
        base = os.path.join(self.directory, *relative)
        init = os.path.join(base, '__init__.py')
        if os.path.isfile(init):
            return init, True
        module = base + '.py'
        return (module, False) if os.path.isfile(module) else None

    def find_spec(self, fullname, path=None, target=None):
        # No imports in here: a finder that imports re-enters itself.
        found = self.source_for(fullname)
        if found is None:
            return None
        source, is_package = found
        return importlib.util.spec_from_file_location(
            fullname, source,
            submodule_search_locations=[os.path.dirname(source)] if is_package else None)


def load_module(path: str):
    """Import a bot module from a file: `strategic@/path/to/base/strategic.py`
    plays an earlier version of the policy against the current one.

    Every `struggler.bots` module sitting beside `path` stands in for the
    candidate's while `path` executes, so the old policy binds the modules it
    was written against. Without that, a gate whose baseline imports anything
    that changed alongside `strategic.py` runs the baseline on the candidate's
    code and reports the candidate playing itself. That is not hypothetical:
    the fix started as `evaluator.py` alone, and the very next gate compared a
    `public_cards.py` change against itself and returned 0.500 with a standard
    error of zero over 96 seeds.

    Imports are resolved lazily through a finder rather than pre-executed,
    because the snapshot's modules import each other and there is no order
    that is right in general. A baseline module that imports lazily, inside a
    function called after this returns, still gets the candidate's.
    """
    directory = os.path.dirname(os.path.abspath(path))
    target = os.path.basename(path)
    finder = _SnapshotFinder(directory)
    # Top-level modules *and* packages: a snapshot that contains
    # `strategic/__init__.py` must shadow the candidate's `strategic`
    # package, not just its `.py` files.
    snapshotted = [name[:-3] if name.endswith('.py') else name
                   for name in sorted(os.listdir(directory))
                   if name != target and not name.startswith('_')
                   and (name.endswith('.py')
                        or os.path.isfile(os.path.join(directory, name, '__init__.py')))]
    if not snapshotted:
        return _exec_file(path, 'struggler_benchmark_' + str(abs(hash(path))))
    import struggler.bots as package
    prefix = _SnapshotFinder.PREFIX
    saved_modules = {k: v for k, v in sys.modules.items() if k.startswith(prefix)}
    saved_attributes = {stem: getattr(package, stem, None) for stem in snapshotted}
    for stem in snapshotted:
        sys.modules.pop(prefix + stem, None)
        if hasattr(package, stem):
            delattr(package, stem)
    sys.meta_path.insert(0, finder)
    try:
        return _exec_file(path, 'struggler_benchmark_' + str(abs(hash(path))))
    finally:
        sys.meta_path.remove(finder)
        for key in [k for k in sys.modules if k.startswith(prefix) and k not in saved_modules]:
            del sys.modules[key]
        sys.modules.update(saved_modules)
        for stem, module in saved_attributes.items():
            if module is not None:
                setattr(package, stem, module)


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
                final_scoring=engine.final_scoring_ran, turn=engine.turn, vp=engine.vp, signed_vp=sign * engine.vp, defcon=engine.defcon,
                value=round(value, 2), seconds=round(time.time() - start, 1),
                searches=int(searches), search_seconds=round(search_seconds, 1),
                result=None if not engine.is_terminal else 0.5 if winner is None else float(winner is side))


# What a candidate has to clear before it lands. The gate used to print
# numbers and exit 0, so "the gate passed" meant "the gate ran"; these are the
# rules that make it mean something. They are deliberately permissive about
# *improvement* and strict about evidence: a change is blocked only when the
# games say it is worse, because at these sample sizes most real changes are
# not measurable either way and blocking them all would stop the project.
ACCEPTANCE = dict(
    confidence=1.645,   # one-sided 95%
    min_games=150,      # pooled, finished
    min_samples=2,      # at least one of them not the seeds the change was tuned on
    # Nuclear losses are a rate, not a count, and the rate that matters is
    # not this bot's. It loses to DEFCON 1 in 3 of the 4226 recorded gate
    # games (0.071%); WBC tournament play ends in nuclear war in 5.4% of
    # games (2024) and 11.7% (2025), so about 2.7-5.8% per player-game. The
    # bot is 38x to 82x more DEFCON-averse than a human field, which is a
    # symptom, not a virtue -- and a cap of 1 was pinning it there. A policy
    # that took human-like risk would expect 5 to 11 losses in a 192-game
    # gate and be rejected every time, which is exactly the "can reject a
    # stronger policy" failure docs/CODEX_NOTES.md warns about.
    #
    # So the cap sits where the pooled score takes over. A policy losing a
    # fraction p of its games outright gives up about p/2 of score; the
    # gate's 95% half-width is near 0.05, so the score itself detects
    # p > 10% -- 19 games in 192. Below that the count is the only evidence;
    # above it, the strength rule fails the change on its own. `warn_nuclear`
    # keeps the diagnostic: the first loss still names its seed to replay.
    max_nuclear_rate=0.10,
    min_nuclear=3,      # never fail a small gate on one or two
    warn_nuclear=1,
)


def seed_scores(games) -> dict[int, float]:
    """Each seed's mean result. Both seats of one seed play the same deal from
    the same shuffle, so they are one observation and not two; counting them
    separately understates the spread and makes every result look
    significant."""
    by_seed: dict[int, list] = {}
    for game in games:
        if game.get('finished') and game.get('result') is not None:
            by_seed.setdefault(game['seed'], []).append(game['result'])
    return {seed: statistics.fmean(results) for seed, results in by_seed.items()}


def nuclear_cap(total_games: int) -> int:
    """The most candidate nuclear losses this many games may carry.

    A rate rather than a count, because gates vary in size and a fixed
    number means something different at 76 seeds than at 96. See ACCEPTANCE
    for why the rate is where it is: above any human-plausible policy,
    at the point the pooled score becomes decisive on its own."""
    return max(ACCEPTANCE['min_nuclear'],
               int(ACCEPTANCE['max_nuclear_rate'] * total_games))


def candidate_nuclear_loss(game: dict) -> bool:
    """Whether `game` is one the *candidate* lost to DEFCON 1. A game the
    opponent blew up is the candidate's win, and counting it against the
    candidate -- which `acceptance` and `_decided` did, while `summarize`
    did not -- meant two baseline blunders would fail a gate. A report
    without a `winner` field counts, conservatively."""
    return game.get('reason') == 'defcon_1' and game.get('winner') != game.get('bot_side')


def opponent_nuclear_defeat(game: dict) -> bool:
    """The other case: the opponent lost to DEFCON 1. A diagnostic, never a
    penalty -- forcing that can be good play."""
    return game.get('reason') == 'defcon_1' and game.get('winner') == game.get('bot_side')


def verdict(scores_by_sample, nuclear: int, total_games: int) -> bool:
    """Whether the acceptance rules pass, given per-sample seed scores, the
    nuclear-loss count and the number of finished games.

    The arithmetic of the verdict lives here alone. `acceptance` adds the
    reporting and `stable_verdict` asks the same question of a resampled
    future, so a rule can never mean one thing when the gate reports it and
    another when the gate decides to stop early on it.
    """
    if nuclear > nuclear_cap(total_games):
        return False
    if len(scores_by_sample) < ACCEPTANCE['min_samples']:
        return False
    seen: set = set()
    pooled: list[float] = []
    for scores in scores_by_sample:
        if seen & scores.keys():
            return False  # samples must be over disjoint seeds
        seen |= scores.keys()
        pooled += list(scores.values())
    if total_games < ACCEPTANCE['min_games'] or len(pooled) < 2:
        return False
    mean = statistics.fmean(pooled)
    error = statistics.stdev(pooled) / math.sqrt(len(pooled))
    return mean + ACCEPTANCE['confidence'] * error >= 0.5


def stable_verdict(observed, remaining, games_per_seed: int = 2,
                   threshold: float = 0.01, trials: int = 400) -> bool:
    """Whether the seeds still unplayed could change the verdict.

    `observed` is one `(sample_index, score, nuclear_losses)` per finished
    seed. `remaining` maps a sample index to how many of its seeds are
    unplayed. Each unplayed seed is resampled from the observed seeds *of its
    own sample*, and the answer is whether the verdict survived every draw
    but `threshold` of them.

    Within its own sample, not pooled: the two samples exist because the
    tuning seeds are the ones the change was selected on, so they score
    better than held-out seeds by construction. Letting a tuning seed stand
    in for an unplayed held-out one would make this optimistic in exactly the
    way the split is there to prevent -- and since the gate exhausts the
    smaller tuning range first, every seed still unplayed at the decision
    point is a held-out one.

    Resampling covers nuclear losses as well as scores, because stopping
    early can only *miss* a failure: the games not played are exactly the
    ones that might have carried the second loss. Deterministically seeded,
    so re-running a gate stops in the same place.

    This is curtailment, not a stopping rule with its own error budget: it
    predicts the verdict of the full run rather than testing a hypothesis
    early. Its blind spot is the bootstrap's -- resampling cannot produce a
    seed score it has not already seen, so a sample with no spread predicts
    no spread with false certainty. The evidence floor in `_decided` is what
    bounds that, and `docs/STRATEGIC_AI.md` records what it was measured to
    cost.
    """
    outstanding = sum(remaining.values())
    if outstanding <= 0 or len(observed) < 2:
        return outstanding <= 0
    pools: dict[int, list] = {}
    for record in observed:
        pools.setdefault(record[0], []).append(record)
    if any(count and index not in pools for index, count in remaining.items()):
        return False  # a sample with seeds still to play and nothing to predict them from
    rng = random.Random(len(observed) * 1000 + outstanding)
    samples = sorted(set(pools) | {i for i, c in remaining.items() if c})

    def apply(records):
        by_sample = {i: {} for i in samples}
        nuclear = 0
        for n, (index, score, losses) in enumerate(records):
            by_sample[index][n] = score  # synthetic seed ids: disjoint by construction
            nuclear += losses
        return verdict([s for s in by_sample.values() if s], nuclear,
                       len(records) * games_per_seed)

    now = apply(observed)
    for _ in range(trials):
        if apply(list(observed) + draw_unplayed(pools, remaining, rng)) != now:
            return False
    return True


def draw_unplayed(pools, remaining, rng) -> list:
    """One resampled stand-in per unplayed seed, each drawn from the pool of
    its own sample. Separate from `stable_verdict` so that the property the
    two-sample split depends on -- that a tuning seed never stands in for a
    held-out one -- is something a test can check directly rather than infer
    from a verdict."""
    return [rng.choice(pools[index]) for index, count in remaining.items()
            for _ in range(count)]


def acceptance(samples) -> tuple[bool, list[str]]:
    """Whether a candidate may land, given `(label, report)` benchmark reports.

    Three rules, all required:

    1. **No more nuclear losses than chance explains.** Two is a fail, one is
       a warning naming the seed to replay, and the cap is a rate (10% of
       games, floor 3) rather than a count. It is deliberately far above
       this bot's own rate of 3 in 4226 games: WBC tournament play ends in
       nuclear war in 5.4-11.7% of games, so a policy taking human-like
       DEFCON risk would expect 5-11 losses in a 192-game gate. A cap that
       rejected those would be enforcing the bot's current 38x-to-82x
       over-caution rather than testing it. The rate sits where the pooled
       score becomes decisive on its own (p > 10% costs more than the
       gate's half-width), so below the cap the count is the only evidence
       and above it the strength rule fails the change anyway. Only the *candidate's* defeats count
       (`candidate_nuclear_loss`): a game the opponent blew up is the
       candidate's win, and is reported as a note, never a penalty.
    2. **Enough evidence, from more than the seeds it was tuned on.** At least
       two samples over disjoint seeds and 150 finished games pooled. Selecting
       change after change on one seed range is how a bot overfits its own
       benchmark.
    3. **Not measurably worse.** The pooled score's one-sided 95% upper bound
       must reach 0.500. A change that is neutral, unmeasurable, or better
       passes; only evidence of a regression blocks.

    The expert valuation check is deliberately not a rule. It is a handful of
    hand-priced rows read by eye, and its miss count moves by one or two on
    changes that are otherwise clearly fine.
    """
    lines, ok = [], True
    pooled: dict[int, float] = {}
    seen: dict[int, str] = {}
    overlap = False
    total = nuclear = 0
    nuclear_seeds: list[tuple] = []
    for label, report in samples:
        games = report.get('games', [])
        summary = report.get('summary', {})
        scores = seed_scores(games)
        total += sum(1 for g in games if g.get('finished'))
        losses = [g for g in games if candidate_nuclear_loss(g)]
        nuclear += len(losses)
        nuclear_seeds += [(g['seed'], g['bot_side'], g['turn']) for g in losses]
        forced = [g for g in games if opponent_nuclear_defeat(g)]
        if forced:
            where = ', '.join(f"seed {g['seed']} {g['bot_side']} T{g['turn']}" for g in forced)
            lines.append(f"  note {label}: opponent lost to DEFCON 1 in {len(forced)} "
                         f"game{'s' if len(forced) > 1 else ''} ({where}); not counted")
        lines.append(f"  {label}: {len(scores)} seeds, "
                     f"score {statistics.fmean(scores.values()):.3f}, "
                     f"signed VP {summary.get('mean_signed_vp')}, "
                     f"nuclear losses {summary.get('nuclear_losses', len(losses))}")
        for seed in scores:
            if seed in seen and seen[seed] != label:
                overlap = True
            seen[seed] = label
        pooled.update(scores)
    if nuclear:
        cap = nuclear_cap(total)
        where = ', '.join(f'seed {s} {side} T{t}' for s, side, t in nuclear_seeds)
        if nuclear > cap:
            ok = False
            lines.append(f'  FAIL nuclear losses: {nuclear} is past the {cap} '
                         f'this gate allows ({where})')
        else:
            lines.append(f'  WARN nuclear losses: {nuclear}, within the rate variance explains, '
                         f'but replay it ({where})')
    if len(samples) < ACCEPTANCE['min_samples'] or overlap:
        ok = False
        lines.append(f"  FAIL evidence: need {ACCEPTANCE['min_samples']} samples over disjoint "
                     f'seeds, got {len(samples)}' + (' with overlapping seeds' if overlap else ''))
    if total < ACCEPTANCE['min_games']:
        ok = False
        lines.append(f"  FAIL evidence: {total} finished games pooled, need {ACCEPTANCE['min_games']}")
    if len(pooled) < 2:
        ok = False
        lines.append('  FAIL evidence: not enough seeds to estimate a spread')
    else:
        values = list(pooled.values())
        mean = statistics.fmean(values)
        error = statistics.stdev(values) / math.sqrt(len(values))
        if error == 0 and mean == 0.5:
            # Every seed a dead heat, on both seats. Either the change cannot
            # affect play, or the two sides are not actually different: a
            # baseline snapshot missing the file that changed produces exactly
            # this, and did. Not a failure, because a refactor proven
            # behaviour-neutral is supposed to look like this.
            lines.append('  WARN identical: every game was a dead heat. Confirm the change is '
                         'meant to be a no-op, and that the baseline snapshot holds what changed')
        upper = mean + ACCEPTANCE['confidence'] * error
        label = 'ok' if upper >= 0.5 else 'FAIL'
        if upper < 0.5:
            ok = False
        lines.append(f'  {label} strength: pooled score {mean:.3f} +/- {error:.3f} over '
                     f'{len(values)} seeds, one-sided 95% upper bound {upper:.3f}, needs 0.500')
    # The lines above explain the verdict; `verdict` *is* the verdict. They
    # are computed from the same numbers, so a disagreement is a bug in one
    # of them and the gate should not quietly pick a side.
    core = verdict([seed_scores(report.get('games', [])) for _, report in samples],
                   nuclear, total)
    assert core == ok, ('acceptance and verdict disagree: %s vs %s' % (ok, core), lines)
    lines.append('ACCEPTED' if ok else 'REJECTED')
    return ok, lines


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
                   nuclear_losses=sum(candidate_nuclear_loss(g) for g in games),
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
        failures = dict(bot.sandbox_failures)
    print(f"{'card':<34}{'side':>8}{'ops':>4}{'US view':>10}{'USSR view':>11}  how", file=out)
    for cid in sorted(views[Side.US], key=lambda c: -abs(views[Side.US][c])):
        card = CARDS[cid]
        # What actually produced the number, not what was meant to: a
        # sandbox failure falls back to the estimate, and used to be reported
        # as a simulated value anyway.
        failed = failures.get(cid)
        how = ('modifier' if cid in OPS_MODIFIER_EVENTS else
               'estimate' if cid in HIDDEN_INFO_EVENTS else
               'estimate (%s)' % failed if failed else 'sandbox')
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


def _decided(games, sample_of, planned: dict[int, int]) -> bool:
    """Whether the seeds still to play can change the acceptance verdict.

    A seed counts only once both its seats are in: they share one deal and
    `seed_scores` averages them, so half a seed is not an observation.
    """
    finished: dict[int, list] = {}
    for game in games:
        if game.get('finished') and game.get('result') is not None:
            finished.setdefault(game['seed'], []).append(game)
    complete = {seed: rows for seed, rows in finished.items() if len(rows) == 2}
    observed = [(sample_of.get(seed, 0),
                 statistics.fmean(r['result'] for r in rows),
                 sum(1 for r in rows if candidate_nuclear_loss(r)))
                for seed, rows in sorted(complete.items())]
    if len(complete) * 2 < ACCEPTANCE['min_games']:
        return False  # the evidence floor is a floor, whatever the score says
    played = collections.Counter(sample_of.get(seed, 0) for seed in complete)
    remaining = {index: count - played[index] for index, count in planned.items()}
    return stable_verdict(observed, remaining)


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
    parser.add_argument('--accept', nargs='+', metavar='REPORT',
                        help='apply the acceptance rules to these --report files and exit 1 if rejected')
    parser.add_argument('--held-seeds', help='a second, disjoint seed range played in the same pool '
                                             'as --seeds; with --held-report the two are written separately')
    parser.add_argument('--held-report', help='where the --held-seeds games go')
    parser.add_argument('--decide', action='store_true',
                        help='stop once the seeds still unplayed cannot change the acceptance verdict')
    args = parser.parse_args(argv)
    if args.accept:
        samples = []
        for path in args.accept:
            with open(path) as f:
                samples.append((os.path.basename(path).removesuffix('.json'), json.load(f)))
        ok, lines = acceptance(samples)
        print('acceptance:')
        for line in lines:
            print(line)
        return 0 if ok else 1
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
    held = parse_seeds(args.held_seeds) if args.held_seeds else []
    if set(seeds) & set(held):
        parser.error('--seeds and --held-seeds must be disjoint: the acceptance rules require it')
    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
    # Both samples run in one pool. Two pools drained one after the other pay
    # the slowest game's tail twice, and a run that stops early has to have
    # played some of each sample or the verdict has nothing to be about -- so
    # the seeds alternate between the groups rather than running one first.
    order = [(0, seed) for seed in seeds]
    if held:
        order = [(index, seed)
                 for row in itertools.zip_longest(seeds, held)
                 for index, seed in enumerate(row) if seed is not None]
    jobs = [(args.bot, args.opponent, seed, side, args.simulations, args.stop_turn,
             args.log_dir, args.bot_weights)
            for _, seed in order for side in ('US', 'USSR')]
    sample_of = {seed: index for index, seed in order}
    planned = collections.Counter(index for index, _ in order)
    start = time.time()
    games = []
    stopped = None
    with Pool(args.workers) as pool:
        results = pool.imap_unordered(play, jobs, chunksize=1)
        for game in results:
            games.append(game)
            print(f"{len(games):3d}/{len(jobs)} seed {game['seed']} {game['bot_side']:<4} T{game['turn']} "
                  f"vp={game['signed_vp']:+d} proj={game['projected_vp']:+.1f} defcon={game['defcon']} "
                  f"{game['reason'] or '...'} {game['seconds']}s", file=sys.stderr, flush=True)
            if args.decide and held and _decided(games, sample_of, planned):
                stopped = len(games)
                print(f'decided after {stopped} of {len(jobs)} games; '
                      f'the rest cannot change the verdict', file=sys.stderr, flush=True)
                pool.terminate()
                break
    games.sort(key=lambda g: (g['seed'], g['bot_side']))
    reports = [(args.report, [g for g in games if sample_of.get(g['seed']) == 0])]
    if held:
        reports.append((args.held_report, [g for g in games if sample_of.get(g['seed']) == 1]))
    summary = summarize(games, args.stop_turn)
    summary['wall_seconds'] = round(time.time() - start, 1)
    summary['bot'], summary['opponent'], summary['simulations'] = args.bot, args.opponent, args.simulations
    summary['bot_weights'] = args.bot_weights
    if stopped is not None:
        summary['stopped_after'] = stopped
        summary['planned_games'] = len(jobs)
    print(json.dumps(summary))
    for path, subset in reports:
        if path:
            with open(path, 'w') as f:
                json.dump(dict(summary=summarize(subset, args.stop_turn), games=subset), f, indent=1)


if __name__ == '__main__':
    sys.exit(main())  # --accept returns 1 when the rules reject the candidate
