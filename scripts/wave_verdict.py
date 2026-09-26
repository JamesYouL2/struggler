"""Whether an arm's second wave is worth playing, decided on its first.

`experiments.yml` cuts each arm's seeds into shards and plays all of them.
Most arms do not need all of them: an arm that is decisively better (or
decisively worse) at 512 seeds is decisive at 1024 too, and the second 512
buy a third decimal place nobody reads. The arms that DO need them are the
ones sitting near the boundary -- which is exactly where this repo keeps
finding itself, and exactly where the seeds are worth spending.

So: play half, look, and play the rest only where looking did not settle it.

THE LOOK IS NOT FREE, and pretending otherwise is how sequential designs go
wrong. Stopping when the data happens to look good inflates the false
positive rate, because two chances to clear a bar are easier than one. The
repo has already measured its own version of this: `validate_early_stopping.py`
found the gate's predictive stop accepts 9.7% of gates it should reject at
0.03-0.06 below the line, "the optimism inherent to stopping when the data
looks decisive, not a defect in the code".

The fix is to pay for the look up front, with a pre-declared boundary rather
than a judgement call. `obrien_fleming` spends almost no alpha at the
interim (the bar is 2.373 instead of 1.645) and so leaves the final bar
nearly where it was (1.678 instead of 1.645):

    one-sided 95%  |  interim bar  |  final bar  |  cost
    ---------------+---------------+-------------+-----------------------
    no look        |      --       |    1.645    |  --
    two waves      |     2.373     |    1.678    |  2.0% wider interval

**Two per cent of resolution, for half the seeds on every arm that was never
close.** That is the whole trade, and it is why the boundary is O'Brien-
Fleming and not Pocock: Pocock's bar is 1.875 at BOTH looks, which stops
more arms early and leaves a final bar 14% above 1.645 instead of 2%. This
repo quotes its final intervals in notes; it does not want them 14% wider.

Both directions count. An arm measured decisively WORSE is a result, not a
failure, so the rule is on |z|, not on z.

FAIL OPEN. Every path that cannot produce a verdict -- a missing shard, an
arm with no finished pairs, a partner arm that did not report, a key this
file does not understand -- returns CONTINUE. A broken interim must cost a
wave of runner time, never half an experiment's seeds reported as a whole
one.

PAIRED ARMS MOVE TOGETHER. `compare_to` resolves seed by seed over the
seeds both arms played, so an arm whose partner continues must continue
too; stopping one of a pair would leave the paired difference reading on
512 seeds while its own arm read 1024.

    python scripts/wave_verdict.py pooled.json --wave2 wave2.json --out next.json
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import sys
from pathlib import Path


def _phi(x: float) -> float:
    """The standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def alpha_spent(interim: float, final: float, points: int = 2001,
                fraction: float = 0.5) -> float:
    """Two-sided type-I error of a two-look design, the interim taken at
    information `fraction`.

    The two statistics are `Z1` and `Z2 = sqrt(t) * Z1 + sqrt(1 - t) * W`
    for an independent standard normal `W` (at t = 1/2 that is
    `(Z1 + W) / sqrt(2)`), so the total is `P(|Z1| >= interim)` plus the
    mass that survives the interim and then crosses at the end. The second
    term is a one-dimensional integral over `Z1`, taken by Simpson's rule --
    the integrand is smooth and bounded, and the answer is already identical
    to ten decimal places at 501 points, so 2001 is not a number to tune.
    """
    a = interim
    root_t, root_rest = math.sqrt(fraction), math.sqrt(1.0 - fraction)
    # P(survive the interim, then cross): integrate phi(z) * P(|Z2| >= final | Z1 = z).
    step = 2.0 * a / (points - 1)
    total = 0.0
    for k in range(points):
        z = -a + k * step
        tail = ((1.0 - _phi((final - root_t * z) / root_rest))
                + _phi((-final - root_t * z) / root_rest))
        density = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        weight = 1 if k in (0, points - 1) else (4 if k % 2 else 2)
        total += weight * density * tail
    crossed_late = total * step / 3.0
    return 2.0 * (1.0 - _phi(a)) + crossed_late


def obrien_fleming(alpha: float = 0.10, tolerance: float = 1e-9,
                   fraction: float = 0.5) -> tuple[float, float]:
    """The two-look O'Brien-Fleming boundary as `(interim, final)`.

    `alpha` is TWO-SIDED, so the repo's one-sided 95% convention is 0.10 and
    the pair comes out at (2.373, 1.678) against the 1.645 a single look
    would use. The shape is `c / sqrt(information)`, which at information
    `fraction` is `c / sqrt(fraction)` -- `c * sqrt(2)` at one half; this
    solves for `c` by bisection on the error the pair actually spends,
    rather than quoting a table.
    """
    lo, hi = 0.5, 6.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if alpha_spent(mid / math.sqrt(fraction), mid, fraction=fraction) > alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo < tolerance:
            break
    c = (lo + hi) / 2.0
    return c / math.sqrt(fraction), c


@functools.lru_cache(maxsize=64)
def boundaries(fraction: float = 0.5) -> tuple[float, float]:
    """`(interim, final)` at the repo's two-sided 0.10 for an interim taken
    at `fraction`. An arm whose core cuts into an odd number of shards looks
    at more than half its information, and the 0.5 pair would spend alpha
    it was not given (audit 2026-09-25, F5). Rounded so float noise in a
    fraction does not defeat the cache."""
    if not 0.0 < fraction < 1.0:
        return float('inf'), SINGLE_LOOK
    return obrien_fleming(0.10, fraction=round(fraction, 6))


# The repo's convention is a one-sided 95% bound (`ACCEPTANCE['confidence']`
# is 1.645), which is a two-sided 0.10 for a rule that counts both
# directions. Computed, not quoted, so a change to the convention moves it.
INTERIM_BOUNDARY, FINAL_BOUNDARY = obrien_fleming(0.10)
# One look, no wave: the fixed-sample bar (`ACCEPTANCE['confidence']`).
SINGLE_LOOK = 1.645

# The field of `pool_reports.py --json` holding the seed-by-seed differences.
PAIRED_KEY = 'paired'


def _incomplete(entry: dict) -> str | None:
    """Why a pooled arm (or paired difference) is not the sample it was
    planned as, or None. `complete` is `pool_reports.py`'s verdict against
    the plan's manifest; an entry without it predates the manifest and is
    judged on `missing` alone."""
    if entry.get('missing'):
        return f'{len(entry["missing"])} wave-1 shard(s) missing'
    if entry.get('complete') is False:
        return (f'incomplete: {entry.get("seeds") or 0} of {entry.get("target")} '
                f'planned seeds counted')
    return None


def _level(slug: str, pooled: dict) -> tuple[float, float] | None:
    """`(score - 0.500, standard error)` for an arm read on its own, or None
    if it cannot be read."""
    entry = pooled.get(slug)
    if not entry or _incomplete(entry):
        return None
    if entry.get('score') is None or not entry.get('se'):
        return None
    return entry['score'] - 0.5, entry['se']


def _verdict(reading, boundary: float, unreadable: str) -> dict:
    if reading is None:
        return {'proceed': True, 'z': None, 'why': unreadable}
    estimate, se = reading
    z = estimate / se
    if abs(z) >= boundary:
        return {'proceed': False, 'z': z,
                'why': f'decisive at the interim: |z| {abs(z):.2f} >= {boundary:.3f}'}
    return {'proceed': True, 'z': z,
            'why': f'not decisive: |z| {abs(z):.2f} < {boundary:.3f}'}


def decide(pooled_json: dict, boundary: float | None = None) -> dict[str, dict]:
    """Per-arm: stop here, or play the second wave.

    Returns `{slug: {'proceed': bool, 'why': str, 'z': float | None}}`.
    `boundary` overrides the interim bar; by default each arm is judged at
    the bar for ITS information fraction (`fraction` in its pooled entry,
    one half if absent).

    AN ARM IN A `compare_to` PAIR IS JUDGED ON THE PAIR, not on itself. The
    paired difference is the number the dispatch exists to produce, and the
    two arms' own levels are not it: `fit-bc-base` can sit anywhere against
    its anchor while the difference it is the base of is decisive, or the
    reverse.

    AND A CONNECTED GROUP MOVES AS ONE. `compare_to` is a graph -- a base
    can anchor several comparisons -- and every arm in a connected group
    stops only if EVERY comparison in it is readable and decisive. The
    group is built from the DECLARATIONS, not from the comparisons that
    happened to be readable: until 2026-09-25 an unreadable edge was never
    added to the graph, so with B and C both compared to A, B's unreadable
    edge set A to continue and C's decisive edge then overwrote A to stop,
    and propagation had no edge to carry B's continue back (audit F6).
    """
    pooled = pooled_json.get('arms') or {}
    # `paired` is the key `pool_reports.main` writes. This read `pairs` until
    # 2026-09-23, so every `compare_to` arm found no paired difference and
    # played its second wave however decisive the first had been -- the
    # hand-assignment pair sat at z ~ -18 and played on. Hand-built dicts in
    # the tests used the consumer's spelling and could not see it;
    # `test_the_real_pooled_file_reaches_the_paired_verdict` feeds the
    # producer's own file through instead.
    pairs = {p['arm']: p for p in (pooled_json.get(PAIRED_KEY) or [])}

    def bar(slug: str) -> float:
        if boundary is not None:
            return boundary
        return boundaries((pooled.get(slug) or {}).get('fraction') or 0.5)[0]

    out: dict[str, dict] = {}
    for slug, entry in sorted(pooled.items()):
        why = _incomplete(entry)
        if why:
            out[slug] = {'proceed': True, 'z': None, 'why': why}
            continue
        out[slug] = _verdict(_level(slug, pooled), bar(slug), 'no readable wave-1 result')

    # Every DECLARED comparison is an edge, readable or not. An arm whose
    # partner is ABSENT still gets the paired treatment -- a declared
    # comparison with nothing to compare against is the fail-open case, not
    # licence to fall back on the arm's own level.
    edges: dict[str, tuple[list[str], dict]] = {}
    for slug, entry in sorted(pooled.items()):
        partner = (entry.get('meta') or {}).get('compare_to')
        if not partner:
            continue
        ends = [slug] + ([partner] if partner in out else [])
        pair = pairs.get(slug)
        broken = [why for e in ends if (why := _incomplete(pooled[e]))]
        if partner not in out or not pair or not pair.get('se'):
            verdict = {'proceed': True, 'z': None,
                       'why': f'no readable paired difference against {partner}'}
        elif broken or pair.get('complete') is False:
            verdict = {'proceed': True, 'z': None,
                       'why': f'paired difference against {partner} is incomplete'
                              f'{": " + broken[0] if broken else ""}'}
        else:
            verdict = _verdict((pair['diff_exact'], pair['se']), bar(slug),
                               f'no readable paired difference against {partner}')
            verdict = {**verdict, 'why': f'{verdict["why"]} (paired, vs {partner})'}
        edges[slug] = (ends, verdict)

    # Connected groups over the declared edges.
    group = {slug: slug for slug in out}

    def root(x: str) -> str:
        while group[x] != x:
            group[x] = group[group[x]]
            x = group[x]
        return x

    for ends, _ in edges.values():
        for other in ends[1:]:
            group[root(other)] = root(ends[0])
    members: dict[str, list[str]] = {}
    for slug in out:
        members.setdefault(root(slug), []).append(slug)

    for arms in members.values():
        mine = {a: [v for ends, v in edges.values() if a in ends] for a in arms}
        if not any(mine.values()):
            continue                     # an unpaired arm keeps its own verdict
        going = [a for a in arms if any(v['proceed'] for v in mine[a])]
        for a in sorted(arms):
            own = mine[a]
            if not own:
                continue
            first_go = next((v for v in own if v['proceed']), None)
            if first_go is not None:
                out[a] = dict(first_go)
            elif going:
                out[a] = {**own[0], 'proceed': True,
                          'why': f'{own[0]["why"]}, but paired with {going[0]}, which continues'}
            else:
                out[a] = dict(own[0])
    return out


def select(wave2: list[dict], verdicts: dict[str, dict]) -> list[dict]:
    """The wave-2 shards still worth playing.

    An arm absent from the verdicts never reported at all, which is a
    failure, not a decision -- so it proceeds, on the same fail-open rule.
    """
    return [s for s in wave2 if verdicts.get(s['slug'], {'proceed': True})['proceed']]


def summary(verdicts: dict[str, dict], kept: int, total: int) -> str:
    lines = [f'Interim boundary |z| >= {INTERIM_BOUNDARY:.3f} at half the information '
             f'(final bar {FINAL_BOUNDARY:.3f}, against {SINGLE_LOOK:.3f} for a single look); '
             f'an arm looking at a different fraction is judged at its own pair.', '',
             '| arm | interim z | wave 2 | why |', '| --- | ---: | --- | --- |']
    for slug, v in sorted(verdicts.items()):
        z = '--' if v['z'] is None else f'{v["z"]:+.2f}'
        lines.append(f'| `{slug}` | {z} | {"PLAY" if v["proceed"] else "stop"} | {v["why"]} |')
    lines += ['', f'**{kept} of {total} wave-2 shards will play.**']
    return '\n'.join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pooled', help="the interim pooled.json from wave 1")
    ap.add_argument('--wave2', required=True, help="plan's wave-2 shard list, as JSON")
    ap.add_argument('--out', required=True, help='where to write the shards still to play')
    ap.add_argument('--boundary', type=float, default=None,
                    help="override the interim bar (default: each arm's own, from its fraction)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    wave2 = json.loads(Path(args.wave2).read_text())
    try:
        verdicts = decide(json.loads(Path(args.pooled).read_text()), args.boundary)
    except Exception as exc:
        # A verdict that cannot be computed is not a verdict to stop on. Play
        # the wave and say why, rather than reporting half an experiment.
        print(f'INTERIM UNREADABLE ({exc!r}) -- playing every wave-2 shard.')
        Path(args.out).write_text(json.dumps(wave2))
        print(f'count={len(wave2)}')
        return 0
    kept = select(wave2, verdicts)
    Path(args.out).write_text(json.dumps(kept))
    print(summary(verdicts, len(kept), len(wave2)))
    print(f'count={len(kept)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
