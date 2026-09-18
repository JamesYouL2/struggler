"""Pool sharded benchmark reports into one reading per arm.

`experiments.yml` splits an arm's seeds into shards of ~128 so each fits
inside a hosted runner's job ceiling (one 128-seed shard is 30-65 minutes on
4 vCPU; 1024 seeds in one job would be 4-9 hours against a 6-hour limit).
This puts the shards back together.

It deliberately reuses `benchmark.summarize`, so a pooled reading is
computed exactly the way a single run's is: the seed is the unit (both seats
of a seed share a deal), only complete seat pairs count, and the interval is
the one-sided 95% the gate decides on. A pooled number computed by a second,
hand-written formula would be the "second copy of a rule" that
docs/notes/claude/bug-shapes.md warns about.

Usage: pool_reports.py <root> [--json out.json]
  <root> holds one directory per shard, named `experiment-<slug>--<shard>`,
  each with `<slug>.json` inside (what `gh run download` or
  `actions/download-artifact` produces).
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
import sys

from struggler.bots.benchmark import ACCEPTANCE, complete_pairs, seed_scores, summarize


def load(root: pathlib.Path) -> dict[str, dict]:
    arms: dict[str, dict] = collections.defaultdict(lambda: {'games': [], 'shards': 0, 'meta': None})
    for shard in sorted(root.glob('experiment-*')):
        slug = shard.name.removeprefix('experiment-').rsplit('--', 1)[0]
        report = shard / f'{slug}.json'
        if not report.exists():
            # A shard that crashed or timed out uploads nothing useful. Count
            # it as missing rather than pooling around it silently.
            arms[slug].setdefault('missing', []).append(shard.name)
            continue
        arms[slug]['games'] += json.loads(report.read_text())['games']
        arms[slug]['shards'] += 1
        meta = shard / 'arm.json'
        if meta.exists() and arms[slug]['meta'] is None:
            arms[slug]['meta'] = json.loads(meta.read_text())
    return arms


def seat_scores(games: list[dict]) -> dict[str, float]:
    out = {}
    for side in ('US', 'USSR'):
        rows = [g['result'] for g in games if g['bot_side'] == side]
        if rows:
            out[side] = round(statistics.fmean(rows), 3)
    return out


def nuclear_split(games: list[dict]) -> dict[str, int]:
    """DEFCON-1 endings by who lost them, by the candidate's seat."""
    out = collections.Counter()
    for g in games:
        if g['reason'] == 'defcon_1' and g['winner']:
            who = 'bot' if g['winner'] != g['bot_side'] else 'opponent'
            out[f'{who}_as_{g["bot_side"]}'] += 1
    return dict(out)


def pooled(arms: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for slug, arm in sorted(arms.items()):
        paired = [g for rows in complete_pairs(arm['games']).values() for g in rows]
        entry = {'shards': arm['shards'], 'missing': arm.get('missing', []), 'meta': arm['meta']}
        if paired:
            s = summarize(paired, 0)
            half = s.get('score_halfwidth')
            entry.update({
                'score': s.get('score'), 'halfwidth': half, 'se': s.get('score_se'),
                'seeds': s.get('seeds'), 'games': s['games'],
                'upper': round(s['score'] + half, 3) if half is not None else None,
                'lower': round(s['score'] - half, 3) if half is not None else None,
                'seats': seat_scores(paired), 'nuclear': nuclear_split(paired),
                'mean_signed_vp': s['mean_signed_vp'], 'endings': s.get('endings'),
                'mean_end_turn': s.get('mean_end_turn'),
            })
        out[slug] = entry
    return out


def paired(arms: dict[str, dict], result: dict[str, dict]) -> list[dict]:
    """Seed-by-seed differences for arms that name a `compare_to` arm.

    Two arms that play the same seeds against the same opponent share every
    deal, so most of each arm's variance is the deal and cancels in the
    difference. Comparing their two intervals instead throws that away and
    needs roughly twice the seeds to see the same effect.
    """
    out = []
    for slug, entry in result.items():
        other = (entry.get('meta') or {}).get('compare_to')
        if not other or other not in arms:
            continue
        a, b = seed_scores(arms[slug]['games']), seed_scores(arms[other]['games'])
        shared = sorted(set(a) & set(b))
        if len(shared) < 2:
            continue
        diffs = [a[s] - b[s] for s in shared]
        se = statistics.stdev(diffs) / len(diffs) ** 0.5
        half = ACCEPTANCE['confidence'] * se
        mean = statistics.fmean(diffs)
        out.append({'arm': slug, 'minus': other, 'seeds': len(shared), 'diff': round(mean, 3),
                    'halfwidth': round(half, 3), 'lower': round(mean - half, 3),
                    'upper': round(mean + half, 3)})
    return out


def markdown(result: dict[str, dict], pairs: list[dict] | None = None) -> str:
    lines = ['| arm | vs | score | one-sided 95% | seeds | US seat | USSR seat | signed VP | bot nuked (US/USSR) | shards |',
             '| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for slug, e in result.items():
        meta = e.get('meta') or {}
        vs = meta.get('anchor') or 'HEAD defaults'
        if meta.get('bot_ref'):
            vs = f"{meta['bot_ref']} vs {vs}"
        if 'score' not in e:
            lines.append(f'| `{slug}` | {vs} | -- | no finished pairs | 0 | | | | | {e["shards"]} ok, {len(e["missing"])} missing |')
            continue
        band = f'[{e["lower"]:.3f}, {e["upper"]:.3f}]' if e['upper'] is not None else '--'
        nk = e['nuclear']
        lines.append(
            f'| `{slug}` | {vs} | {e["score"]:.3f} | {band} | {e["seeds"]} | '
            f'{e["seats"].get("US", float("nan")):.3f} | {e["seats"].get("USSR", float("nan")):.3f} | '
            f'{e["mean_signed_vp"]:+.2f} | {nk.get("bot_as_US", 0)}/{nk.get("bot_as_USSR", 0)} | '
            f'{e["shards"]} ok{", " + str(len(e["missing"])) + " MISSING" if e["missing"] else ""} |')
    if pairs:
        lines += ['', '**Paired differences** (same seeds, same opponent; seed by seed):', '',
                  '| arm | minus | diff | one-sided 95% | shared seeds |',
                  '| --- | --- | ---: | --- | ---: |']
        for p in pairs:
            lines.append(f'| `{p["arm"]}` | `{p["minus"]}` | {p["diff"]:+.3f} | '
                         f'[{p["lower"]:+.3f}, {p["upper"]:+.3f}] | {p["seeds"]} |')
    lines += ['',
              '_Interval is one-sided 95% each way (score +/- 1.645 SE, seed as the unit), '
              'the convention the gate decides on. An upper bound below 0.500 is a measurable '
              'loss; a lower bound above 0.500 a measurable gain. Arms that share a seed block '
              'and an opponent are paired: compare them seed by seed, not by their intervals._',
              '',
              '_A score is not a verdict. This says what was measured, not what it means._']
    return '\n'.join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('root', type=pathlib.Path)
    ap.add_argument('--json', type=pathlib.Path)
    args = ap.parse_args(argv)
    arms = load(args.root)
    result = pooled(arms)
    if not result:
        print('no shard reports found under', args.root, file=sys.stderr)
        return 2
    pairs = paired(arms, result)
    print(markdown(result, pairs))
    if args.json:
        args.json.write_text(json.dumps({'arms': result, 'paired': pairs}, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
