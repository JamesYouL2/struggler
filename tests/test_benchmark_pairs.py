"""Early stopping and acceptance judge the same games.

Codex's audit F3 (docs/notes/codex/2026-09-13-full-audit-since-v0-1-0.md):
`_decided` counted a seed once any two of its games were in, while
`seed_scores` and `acceptance` averaged every finished game, singletons
included. Its reproduction -- 75 complete tied seeds plus 10 one-seat losses,
50 planned per sample -- had `_decided` predicting ACCEPT and the saved
reports then rejected (pooled 0.441). And two samples of 150 US-only wins
passed acceptance, which never checked that a seed was a pair at all.
`complete_pairs` is now the one definition all of them use.
"""
from __future__ import annotations

from struggler.bots.benchmark import _decided, acceptance, complete_pairs, counted_pairs, seed_scores


def _game(seed, side, result):
    return {'seed': seed, 'bot_side': side, 'finished': True, 'turn': 10, 'reason': 'vp', 'result': result}


def _audit_reproduction():
    """75 complete seeds, one win and one loss each, alternating between two
    samples; then 10 one-seat losses on other seeds."""
    games, sample_of = [], {}
    for n, seed in enumerate(range(1000, 1075)):
        sample_of[seed] = n % 2
        games += [_game(seed, 'US', 1.0), _game(seed, 'USSR', 0.0)]
    for n, seed in enumerate(range(2000, 2010)):
        sample_of[seed] = n % 2
        games.append(_game(seed, 'US', 0.0))
    return games, sample_of


def _as_reports(games, sample_of):
    return [(f'sample{i}', {'summary': {}, 'games': [g for g in games if sample_of[g['seed']] == i]})
            for i in (0, 1)]


def test_counted_pairs_reads_the_first_target_in_seed_order():
    """The tail reserve's counting rule (scripts/shard_plan.py). Seed order,
    not completion order: the counted set is a function of what finished,
    or two dispatches of one shard read different samples and the shard
    cache's reproducibility warrant dies."""
    games = [_game(5000, 'US', 1.0), _game(4001, 'USSR', 1.0), _game(4000, 'US', 1.0),
             _game(5000, 'USSR', 1.0), _game(4000, 'USSR', 1.0), _game(4001, 'US', 1.0)]
    counted = counted_pairs(games, 2)
    assert sorted(counted) == [4000, 4001]
    # A function of the set, not of arrival order.
    assert sorted(counted_pairs(list(reversed(games)), 2)) == [4000, 4001]


def test_a_reserve_pair_enters_only_when_a_core_pair_is_lost():
    games = [_game(4000, 'US', 1.0), _game(4000, 'USSR', 1.0),
             _game(5000, 'US', 1.0), _game(5000, 'USSR', 1.0)]
    assert sorted(counted_pairs(games, 1)) == [4000]
    # Core seed 4000 loses its USSR seat: the reserve backfills, one lost
    # game costs a backfill and not a sample.
    games = [g for g in games if not (g['seed'] == 4000 and g['bot_side'] == 'USSR')]
    assert sorted(counted_pairs(games, 1)) == [5000]


def test_counted_pairs_never_counts_more_than_the_target():
    games = [_game(seed, side, 1.0) for seed in (4000, 4001, 5000) for side in ('US', 'USSR')]
    assert sorted(counted_pairs(games, 2)) == [4000, 4001]  # the spare is dropped
    assert sorted(counted_pairs(games, 3)) == [4000, 4001, 5000]  # and counted only on demand


def test_stopping_and_acceptance_agree_on_the_audit_reproduction():
    games, sample_of = _audit_reproduction()
    stop = _decided(games, sample_of, {0: 50, 1: 50})
    ok, lines = acceptance(_as_reports(games, sample_of))
    # Both now see 75 tied pairs and nothing else: 0.500 exactly.
    assert set(seed_scores(games).values()) == {0.5}
    assert ok, lines
    assert any('outside a complete US+USSR pair excluded' in line for line in lines), lines
    # The contradiction the audit found was stop=True with the reports
    # rejected; stopping may still decline, but never the other way round.
    assert not (stop and not ok)


def test_one_seat_games_are_not_evidence():
    """150 US-only wins over two disjoint samples: no seed is a pair, so
    there is nothing to judge, and acceptance must say so."""
    games = [_game(seed, 'US', 1.0) for seed in range(3000, 3150)]
    sample_of = {seed: seed % 2 for seed in range(3000, 3150)}
    ok, lines = acceptance(_as_reports(games, sample_of))
    assert not ok
    assert any('FAIL evidence' in line for line in lines), lines


def test_a_seed_with_two_games_in_one_seat_is_not_a_pair():
    games = [_game(4000, 'US', 1.0), _game(4000, 'US', 1.0),
             _game(4001, 'US', 1.0), _game(4001, 'USSR', 0.0)]
    assert list(complete_pairs(games)) == [4001]
    assert seed_scores(games) == {4001: 0.5}
