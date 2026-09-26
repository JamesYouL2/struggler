"""Pool sharded benchmark reports into one reading per arm.

`experiments.yml` splits an arm's seeds into shards (64 seeds by default,
`scripts/shard_plan.py`) so each fits inside a hosted runner's job ceiling.
This puts the shards back together.

It deliberately reuses `benchmark.summarize`, so a pooled reading is
computed exactly the way a single run's is: the seed is the unit (both seats
of a seed share a deal), only complete seat pairs count. A pooled number
computed by a second, hand-written formula would be the "second copy of a
rule" that docs/notes/claude/bug-shapes.md warns about.

AGAINST THE PLAN, NOT AGAINST WHAT ARRIVED. Given the plan's manifest
(`--plan`, what the plan job wrote; `--selected`, the interim's wave-2
selection), every shard the run was expected to play is one of:

- `complete` -- its report is there and lost nothing;
- `partial`  -- its report is there and names games it never finished
               (a stall or an expired budget; its finished games still count);
- `missing`  -- expected, and nothing usable arrived (a crash, a killed
               runner, an artifact that never uploaded);
- `skipped`  -- a wave-2 shard the interim deliberately did not play.

Without the manifest a wholly absent artifact was invisible: the 2026-09-24
tie-break's 0.5 arm lost shard 6 to a runner shutdown and pooled as
`shards: 8, missing: []` against a plan of 9 (audit 2026-09-25, F2).

THE COUNT. An arm's reading is the first N seeds IN PLAN ORDER -- core
shards by index, then the spare shards -- that finished; N is its core size
(`shard_plan.seed_order`). A paired difference counts the first N that
finished in BOTH arms, so a loss in either is backfilled from the spares
and the pair still reads N. Core seeds that were not counted are listed as
`dropped` and spare seeds that were as `backfilled`: a backfill restores the
sample size, it does not erase the censoring, and a reading short of N is
`complete: false` whatever else it says.

THE BAR. A run with waves is a two-look sequential design; its final
interval is quoted at the final bar for the arm's information fraction
(1.678 at one half), not at the fixed-sample 1.645 (audit F5). An arm the
interim stopped is quoted at the interim bar it cleared. A run without
waves is one look at 1.645.

Usage: pool_reports.py <root> [--json out.json]
                       [--plan plan.json [--selected next.json] [--stage interim|final]]
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

from struggler.bots.benchmark import INCOMPLETE, complete_pairs, seed_scores, summarize

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import shard_plan
import wave_verdict


def load(root: pathlib.Path) -> dict[str, dict]:
    """Every shard that arrived, by arm and shard index."""
    arms: dict[str, dict] = collections.defaultdict(
        lambda: {'games': [], 'shards': {}, 'meta': None})
    for shard in sorted(root.glob('experiment-*')):
        slug, _, index = shard.name.removeprefix('experiment-').rpartition('--')
        report = shard / f'{slug}.json'
        state = 'missing'
        if report.exists():
            data = json.loads(report.read_text())
            summary = data.get('summary') or {}
            lost = summary.get('stop_reason') in INCOMPLETE or summary.get('unfinished')
            state = 'partial' if lost else 'complete'
            arms[slug]['games'] += data['games']
        arms[slug]['shards'][int(index) if index.isdigit() else index] = state
        meta = shard / 'arm.json'
        if meta.exists() and arms[slug]['meta'] is None:
            arms[slug]['meta'] = json.loads(meta.read_text())
    return arms


def expected(plan: dict, selected: list[dict] | None, stage: str) -> tuple[list[dict], list[dict]]:
    """(the shards this pool is owed, the wave-2 shards deliberately skipped).

    At the interim only wave 1 is owed. At the end, wave 2 is owed as the
    interim selected it -- and ALL of it when there is no selection, which is
    exactly what `run2` plays when the look did not succeed (fail open)."""
    shards = plan['shards']
    wave1 = [s for s in shards if s.get('wave', 1) == 1]
    wave2 = [s for s in shards if s.get('wave', 1) == 2]
    if stage == 'interim':
        return wave1, []
    if selected is None:
        return wave1 + wave2, []
    chosen = {(s['slug'], s['shard']) for s in selected}
    return (wave1 + [s for s in wave2 if (s['slug'], s['shard']) in chosen],
            [s for s in wave2 if (s['slug'], s['shard']) not in chosen])


def _first(order: list[int], have, target: int) -> list[int]:
    return [seed for seed in order if seed in have][:target]


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


def _bar(plan: dict | None, owed: list[dict], slug: str, stage: str) -> tuple[float, str]:
    """The z the arm's interval is quoted at, and what it is."""
    if plan is None or not plan.get('waves'):
        return wave_verdict.SINGLE_LOOK, 'single look'
    interim, final = wave_verdict.boundaries(shard_plan.fraction(plan['shards'], slug))
    if stage == 'interim' or not any(s['slug'] == slug and s.get('wave') == 2 for s in owed):
        return interim, 'interim'
    return final, 'final'


def pooled(arms: dict[str, dict], plan: dict | None = None,
           selected: list[dict] | None = None, stage: str = 'final') -> dict[str, dict]:
    owed, skipped = expected(plan, selected, stage) if plan else (None, [])
    slugs = sorted(set(arms) | {s['slug'] for s in owed or []})
    out = {}
    for slug in slugs:
        arm = arms.get(slug) or {'games': [], 'shards': {}, 'meta': None}
        states = dict(arm['shards'])
        if owed is not None:
            for s in owed:
                if s['slug'] == slug and s['shard'] not in states:
                    states[s['shard']] = 'missing'
        by_state = collections.defaultdict(list)
        for index, state in sorted(states.items(), key=lambda kv: (isinstance(kv[0], str), kv[0])):
            by_state[state].append(f'experiment-{slug}--{index}')
        pairs = complete_pairs(arm['games'])
        entry = {'shards': len(by_state['complete']) + len(by_state['partial']),
                 'missing': by_state['missing'], 'partial': by_state['partial'],
                 'skipped': [f'experiment-{s["slug"]}--{s["shard"]}' for s in skipped
                             if s['slug'] == slug],
                 'meta': arm['meta'] or next(
                     ({k: s[k] for k in ('slug', 'anchor', 'bot_ref', 'openings', 'compare_to')}
                      for s in owed or [] if s['slug'] == slug), None)}
        if owed is not None:
            order, target = shard_plan.seed_order(owed, slug)
            counted = _first(order, pairs, target)
            core = set(order[:target])
            entry.update(target=target, complete=len(counted) == target,
                         dropped=[s for s in order[:target] if s not in counted],
                         backfilled=[s for s in counted if s not in core],
                         fraction=shard_plan.fraction(plan['shards'], slug))
        else:
            # No manifest: what arrived is all there is to go on, and nothing
            # can say what should have. Missing directories stay invisible.
            counted = sorted(pairs)
        bar, stage_name = _bar(plan, owed or [], slug, stage)
        entry.update(bar=bar, stage=stage_name)
        paired = [g for seed in counted for g in pairs[seed]]
        if paired:
            s = summarize(paired, 0)
            se = s.get('score_se')
            half = round(bar * se, 3) if se is not None else None
            entry.update({
                'score': s.get('score'), 'halfwidth': half, 'se': se,
                'seeds': s.get('seeds'), 'games': s['games'],
                'upper': round(s['score'] + half, 3) if half is not None else None,
                'lower': round(s['score'] - half, 3) if half is not None else None,
                'seats': seat_scores(paired), 'nuclear': nuclear_split(paired),
                'mean_signed_vp': s['mean_signed_vp'], 'endings': s.get('endings'),
                'mean_end_turn': s.get('mean_end_turn'),
                'events_fired': s.get('events_fired'), 'blind_picks': s.get('blind_picks'),
                'event_choices': s.get('event_choices'),
            })
        out[slug] = entry
    return out


def paired(arms: dict[str, dict], result: dict[str, dict],
           plan: dict | None = None, selected: list[dict] | None = None,
           stage: str = 'final') -> list[dict]:
    """Seed-by-seed differences for arms that name a `compare_to` arm.

    Two arms that play the same seeds against the same opponent share every
    deal, so most of each arm's variance is the deal and cancels in the
    difference. Comparing their two intervals instead throws that away and
    needs roughly twice the seeds to see the same effect.

    With a plan, the difference counts the first N seeds in the arm's plan
    order that finished in BOTH arms -- the spares backfill a loss on either
    side -- and says whether it reached N.
    """
    owed = expected(plan, selected, stage)[0] if plan else None
    out = []
    for slug, entry in result.items():
        other = (entry.get('meta') or {}).get('compare_to')
        if not other or other not in arms or slug not in arms:
            continue
        a, b = seed_scores(arms[slug]['games']), seed_scores(arms[other]['games'])
        both = set(a) & set(b)
        if owed is not None:
            order, target = shard_plan.seed_order(owed, slug)
            shared = _first(order, both, target)
            extra = {'target': target, 'complete': len(shared) == target,
                     'dropped': [s for s in order[:target] if s not in shared]}
        else:
            shared, extra = sorted(both), {}
        if len(shared) < 2:
            continue
        bar = entry.get('bar', wave_verdict.SINGLE_LOOK)
        diffs = [a[s] - b[s] for s in shared]
        se = statistics.stdev(diffs) / len(diffs) ** 0.5
        half = bar * se
        mean = statistics.fmean(diffs)
        # `diff` and the bounds are rounded because they are read; `se` and
        # `diff_exact` are not, because they are COMPUTED ON -- an interim
        # wave verdict divides one by the other, and three decimals of a
        # halfwidth is not enough to recover a z to two.
        out.append({'arm': slug, 'minus': other, 'seeds': len(shared), 'diff': round(mean, 3),
                    'halfwidth': round(half, 3), 'lower': round(mean - half, 3),
                    'upper': round(mean + half, 3), 'diff_exact': mean, 'se': se,
                    'bar': bar, **extra})
    return out


def _shards_cell(e: dict) -> str:
    cell = f'{e["shards"]} ok'
    for key, word in (('partial', 'partial'), ('missing', 'MISSING'), ('skipped', 'skipped')):
        if e.get(key):
            cell += f', {len(e[key])} {word}'
    return cell


def _count_cell(e: dict) -> str:
    if 'target' not in e:
        return str(e.get('seeds') or 0)
    cell = f'{e.get("seeds") or 0}/{e["target"]}'
    if e.get('backfilled'):
        cell += f' ({len(e["backfilled"])} backfilled)'
    if not e['complete']:
        cell += ' **SHORT**'
    return cell


def markdown(result: dict[str, dict], pairs: list[dict] | None = None) -> str:
    lines = ['| arm | vs | score | interval | seeds | US seat | USSR seat | signed VP | bot nuked (US/USSR) | shards |',
             '| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for slug, e in result.items():
        meta = e.get('meta') or {}
        vs = meta.get('anchor') or 'HEAD defaults'
        if meta.get('bot_ref'):
            vs = f"{meta['bot_ref']} vs {vs}"
        if 'score' not in e:
            lines.append(f'| `{slug}` | {vs} | -- | no finished pairs | {_count_cell(e)} | | | | | {_shards_cell(e)} |')
            continue
        band = (f'[{e["lower"]:.3f}, {e["upper"]:.3f}] (z {e["bar"]:.3f}, {e["stage"]})'
                if e['upper'] is not None else '--')
        nk = e['nuclear']
        lines.append(
            f'| `{slug}` | {vs} | {e["score"]:.3f} | {band} | {_count_cell(e)} | '
            f'{e["seats"].get("US", float("nan")):.3f} | {e["seats"].get("USSR", float("nan")):.3f} | '
            f'{e["mean_signed_vp"]:+.2f} | {nk.get("bot_as_US", 0)}/{nk.get("bot_as_USSR", 0)} | '
            f'{_shards_cell(e)} |')
    if pairs:
        lines += ['', '**Paired differences** (same seeds, same opponent; seed by seed):', '',
                  '| arm | minus | diff | interval | shared seeds |',
                  '| --- | --- | ---: | --- | ---: |']
        for p in pairs:
            count = f'{p["seeds"]}/{p["target"]}' if 'target' in p else str(p['seeds'])
            if p.get('complete') is False:
                count += ' **SHORT**'
            lines.append(f'| `{p["arm"]}` | `{p["minus"]}` | {p["diff"]:+.3f} | '
                         f'[{p["lower"]:+.3f}, {p["upper"]:+.3f}] | {count} |')
    # EVENT MEASUREMENT: what fired, and how the candidate's live event
    # choices were made (benchmark.event_choice_kind) -- `blind` is the
    # unpriced share, where the scorer had no opinion and the first legal
    # option won. Exposure only; what a blind pick costs is a separate
    # counterfactual.
    ev_rows = [(slug, e) for slug, e in result.items() if e.get('events_fired') or e.get('event_choices')]
    if ev_rows:
        lines += ['', '**Event measurement** (the candidate\'s live event choices; blind = unpriced, '
                  'the first legal option won):', '',
                  '| arm | events fired | top events | event choices | blind | blind events | unmeasured |',
                  '| --- | ---: | --- | ---: | ---: | --- | ---: |']
        for slug, e in ev_rows:
            ev = e.get('events_fired') or {}
            bl = e.get('blind_picks') or {}
            ch = e.get('event_choices') or {}
            top = ', '.join(f'{k} {v}' for k, v in list(ev.items())[:3]) or '--'
            btop = ', '.join(f'{k} {v}' for k, v in list(bl.items())[:3]) or '--'
            unmeasured = sum(v for k, v in ch.items() if k.endswith('|unmeasured'))
            lines.append(f'| `{slug}` | {sum(ev.values())} | {top} | {sum(ch.values())} | '
                         f'{sum(bl.values())} | {btop} | {unmeasured} |')
    dropped = {slug: e['dropped'] for slug, e in result.items() if e.get('dropped')}
    if dropped:
        lines += ['', '**Core seeds not counted** (censored; a backfill restores the size, not the seeds):', '']
        lines += [f'- `{slug}`: {len(seeds)} -- {", ".join(map(str, seeds[:12]))}'
                  f'{" ..." if len(seeds) > 12 else ""}' for slug, seeds in dropped.items()]
    lines += ['',
              '_Each interval is score +/- z x SE, seed as the unit, at the z named beside it: '
              '1.645 for a single look, the O\'Brien-Fleming final bar (1.678 at half the '
              'information) for an arm that played both waves, the interim bar for one the look '
              'stopped. An upper bound below 0.500 is a measurable loss; a lower bound above 0.500 '
              'a measurable gain. Arms that share a seed block and an opponent are paired: compare '
              'them seed by seed, not by their intervals._',
              '',
              '_A score is not a verdict. This says what was measured, not what it means._']
    return '\n'.join(lines)


def _read_json(path: pathlib.Path | None):
    """A manifest file, or None when it was not given or did not arrive --
    the `interim` artifact is absent whenever the look did not run."""
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('root', type=pathlib.Path)
    ap.add_argument('--json', type=pathlib.Path)
    ap.add_argument('--plan', type=pathlib.Path,
                    help="the plan job's manifest: {'waves': bool, 'shards': [...]}")
    ap.add_argument('--selected', type=pathlib.Path,
                    help="the interim's wave-2 selection (next.json); absent = all of wave 2")
    ap.add_argument('--stage', choices=('interim', 'final'), default='final')
    args = ap.parse_args(argv)
    plan = _read_json(args.plan)
    if args.plan is not None and plan is None:
        print(f'--plan {args.plan} is unreadable; pooling without a manifest, so an absent '
              f'shard cannot be seen', file=sys.stderr)
    selected = _read_json(args.selected)
    arms = load(args.root)
    result = pooled(arms, plan, selected, args.stage)
    if not result:
        print('no shard reports found under', args.root, file=sys.stderr)
        return 2
    pairs = paired(arms, result, plan, selected, args.stage)
    print(markdown(result, pairs))
    if args.json:
        args.json.write_text(json.dumps({'arms': result, 'paired': pairs}, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
