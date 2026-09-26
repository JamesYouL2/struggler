"""Cut an arm's seed blocks into shards, split them into waves, and say what
a complete reading of the arm has to contain.

WHY SPARE SHARDS. A reading planned at N seeds kept delivering fewer. Two
shapes, and they need different cover:

- One game lost at the tail of a shard (the 255-of-256 shape: six shards of
  the 2026-09-19 grid). A few spare SEEDS inside each shard covered that --
  the old per-shard reserve.
- A whole shard lost: a runner shut down mid-job (`scoring-final-tb-05`
  shard 6 on 2026-09-24, killed at 35 minutes, 128 seeds gone) or a slow
  runner hitting the job ceiling (`fit-bc-base [5/8]`, 2026-09-21). No
  seed-level reserve inside the lost shard can cover this -- it died with
  it -- and this is the shape that has actually cost readings since.

So the reserve is now cut into up to `SPARE_SHARDS` whole spare shards of
the arm's shard size (maintainer, 2026-09-25: "plan 2 extra shards and count
the first that finish"). The COUNTING is not done here or in the shard: it
is `pool_reports.py`'s, over every shard the arm played, as the first N
seeds in plan order -- core shards in order, then the spares -- that
finished in every arm being compared. Plan order and not completion order,
for the reason PR #49 gave: the counted set must be a function of what
finished and nothing else, or two dispatches read different samples.

WHY 64 SEEDS A SHARD. Per-shard work is the one term this repo controls
against a slow runner (docs/notes/claude/2026-09-21-the-slow-shard-is-the-
runner.md): 128 seeds had a median ~55 minutes and a worst 134+ against a
180-minute job, no headroom for a 3x runner. 64 halves both, and a lost
shard costs 64 seeds, which one spare shard replaces whole.

THE RESERVE IS DECLARED, NOT DERIVED. The registry's blocks sit flush
(9700-9827 with held 9828-9891), so spares derived from past a block's `hi`
would land inside somebody's core. An arm declares `reserve` as its own
range and `assert_disjoint` holds it apart from every block. Declare
`SPARE_SHARDS * shard` seeds for full cover; a shorter reserve gives
shorter spares, and an arm without one plays exactly its core.

Used by `experiments.yml`'s plan step, `pool_reports.py` and
`tests/test_experiment_registry.py` -- one statement of the rules, as
`docs/notes/claude/bug-shapes.md` demands.
"""
from __future__ import annotations

DEFAULT_SHARD = 64
SPARE_SHARDS = 2


def span(text: str) -> list[int]:
    lo, hi = (int(x) for x in text.split('-'))
    return list(range(lo, hi + 1))


def cut(cores: list[str], reserve: str = '', size: int = DEFAULT_SHARD,
        spares: int = SPARE_SHARDS) -> list[dict]:
    """Shard specs for one arm: `size`-seed core shards, then up to `spares`
    spare shards cut from the reserve.

    Every core block is cut separately, so no shard straddles the gap
    between `seeds` and `held`. Each spec says its `role`: a core shard's
    seeds are the reading's target, a spare's only ever backfill.
    """
    out = []
    for core in cores:
        seeds = span(core)
        for i in range(0, len(seeds), size):
            chunk = seeds[i:i + size]
            out.append({'seeds': f'{chunk[0]}-{chunk[-1]}', 'role': 'core'})
    pool = span(reserve) if reserve else []
    for i in range(0, min(len(pool), spares * size), size):
        chunk = pool[i:i + size]
        out.append({'seeds': f'{chunk[0]}-{chunk[-1]}', 'role': 'spare'})
    return out


def build(arms: list[dict]) -> list[dict]:
    """Every arm's shard objects, as the matrix runs them.

    The shard object IS what `run-shard` hashes into the cache key (via
    `arm_identity`, which reads `seeds`, `weights` and `openings` only), so
    `role` and `wave` ride along as bookkeeping without moving an identity:
    a spare shard on seeds X plays the same games a core shard on X would.
    """
    shards = []
    for a in arms:
        specs = cut([a['seeds']] + ([a['held']] if a.get('held') else []),
                    a.get('reserve') or '', int(a.get('shard', DEFAULT_SHARD)))
        # Any arm with a ref pins both seats' books unless it names its own:
        # two revisions' defaults are not the same board. "default" asks each
        # side for its own revision's book (drift.yml).
        openings = a.get('openings') or (
            'US=italy,USSR=austria' if (a.get('anchor') or a.get('bot_ref')) else '')
        if openings == 'default':
            openings = ''
        for i, spec in enumerate(specs):
            shards.append({
                'slug': a['slug'], 'shard': i, 'of': len(specs),
                'seeds': spec['seeds'], 'role': spec['role'],
                'weights': a.get('weights') or {},
                'anchor': a.get('anchor', ''), 'bot_ref': a.get('bot_ref', ''),
                'openings': openings, 'compare_to': a.get('compare_to', ''),
                'logs': bool(a.get('logs')),
            })
    return shards


def split_waves(shards: list[dict], waves: bool) -> tuple[list[dict], list[dict]]:
    """Each arm's shards into (wave 1, wave 2), stamping `wave` on each.

    Wave 1 is the first half of an arm's CORE shards, in shard order, so two
    arms on one block and one shard size play the same seeds in wave 1 --
    which is what the paired interim reads. `ceil` puts the odd shard in
    wave 1: the look is what is being paid for. Spares go to the arm's LAST
    wave: an interim reads wave 1 whole or fails open, so backfill is only
    ever needed at the end.

    `waves=False` puts everything in wave 1, which is what a LEVEL reading
    wants (drift.yml): halving the seeds doubles the interval.
    """
    by_arm: dict[str, list[dict]] = {}
    for s in shards:
        by_arm.setdefault(s['slug'], []).append(s)
    wave1, wave2 = [], []
    for arm in by_arm.values():
        core = [s for s in arm if s.get('role', 'core') == 'core']
        spare = [s for s in arm if s.get('role') == 'spare']
        cut_at = -(-len(core) // 2) if waves else len(core)
        wave1 += [{**s, 'wave': 1} for s in core[:cut_at]]
        later = core[cut_at:] + spare
        if waves:
            wave2 += [{**s, 'wave': 2} for s in later]
        else:
            wave1 += [{**s, 'wave': 1} for s in later]
    return wave1, wave2


def fraction(shards: list[dict], slug: str) -> float:
    """The information fraction the arm's interim look sees: wave-1 core
    seeds over all core seeds. One half only when the core cuts evenly --
    18 shards do, 17 do not -- and the boundary has to be computed for the
    fraction actually looked at (audit 2026-09-25, F5)."""
    core = [s for s in shards if s['slug'] == slug and s.get('role', 'core') == 'core']
    total = sum(len(span(s['seeds'])) for s in core)
    first = sum(len(span(s['seeds'])) for s in core if s.get('wave', 1) == 1)
    return first / total if total else 1.0


def seed_order(shards: list[dict], slug: str) -> tuple[list[int], int]:
    """The arm's seeds in plan order -- core shards by index, then spares --
    and the target: how many core seeds a complete reading counts.

    `shards` is what the arm was EXPECTED to play; a wave-2 shard the
    interim skipped is not in it, so an arm stopped early targets its
    wave-1 core, which is the design and not a loss.
    """
    mine = sorted((s for s in shards if s['slug'] == slug), key=lambda s: s['shard'])
    core = [x for s in mine if s.get('role', 'core') == 'core' for x in span(s['seeds'])]
    spare = [x for s in mine if s.get('role') == 'spare' for x in span(s['seeds'])]
    return core + spare, len(core)


def assert_disjoint(arms: list[dict]) -> None:
    """Every DISTINCT seed text an arm set uses -- `seeds`, `held`,
    `reserve` -- occupies its own space.

    Identical texts overlap on purpose: that is how arms are paired. A
    partial overlap between different texts is the trap -- two shards
    reading the same games while presenting as independent, and (with
    spares) a seed that could be counted twice in one pool.
    """
    claimed: dict[str, set[int]] = {}
    for arm in arms:
        for field in ('seeds', 'held', 'reserve'):
            text = arm.get(field) or ''
            if text:
                claimed.setdefault(text, set(span(text)))
    texts = sorted(claimed)
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            overlap = claimed[a] & claimed[b]
            assert not overlap, (
                f'seed blocks {a} and {b} overlap on {sorted(overlap)[:5]}; '
                f'shards on them read the same games while looking independent')
