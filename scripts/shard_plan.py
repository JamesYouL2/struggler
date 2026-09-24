"""Cut an arm's seed blocks into shard cores, with a declared tail reserve.

WHY A RESERVE EXISTS. A shard used to plan exactly its sample and lose its
last game to a slow tail. The stall detector (benchmark's adaptive floor)
then abandoned the laggard -- correctly, a hang looks exactly like a slow
old anchor bot -- but the shard had planned 256 games and delivered 255:
exit 6, a PARTIAL report, never cached, and every future dispatch replayed
the whole shard to recover the one game (six shards of the 2026-09-19 grid
lost exactly their last game this way; `fit-bc-base [5/8]` cost two
dispatches). A reading planned at N could not deliver N.

THE SHAPE OF THE FIX (maintainer, 2026-09-24: "run 130 seeds and stop at
128 finished"). Each shard plays its core (`size` seeds) plus spare seeds
from the arm's `reserve` range -- tail work that fills the workers while
core games run. The reading counts the first `size` COMPLETE PAIRS IN SEED
ORDER (benchmark's `counted_pairs`), so a reserve pair counts only when a
core pair is genuinely lost: one lost game costs a backfill, not a sample.
The counted set is a function of what finished and nothing else -- not of
completion order -- which keeps two dispatches of one shard reading the
same sample and keeps the shard cache's reproducibility warrant true.

THE RESERVE IS DECLARED, NOT DERIVED. It could have been carved from just
past the block's `hi`, but the registry's blocks sit flush against one
another (9700-9827 with held 9828-9891), so a derived reserve would land
inside somebody's core. An arm declares `reserve` as its own range and
`assert_disjoint` holds it apart from every block -- identical texts share
(that is what pairing is), distinct texts collide nowhere. Arms without
`reserve` play exactly what they always played.

Used by `experiments.yml`'s plan step and by
`tests/test_experiment_registry.py` -- one statement of the rules, as
`docs/notes/claude/bug-shapes.md` demands.
"""
from __future__ import annotations


def span(text: str) -> list[int]:
    lo, hi = (int(x) for x in text.split('-'))
    return list(range(lo, hi + 1))


def cut(cores: list[str], reserve: str = '', size: int = 128) -> list[dict]:
    """Shard specs for one arm: `size`-seed cores, each with one slice of
    the reserve block.

    Every block of the arm is cut separately (so no shard straddles a gap
    between `seeds` and `held`) and the reserve is then split across ALL of
    the arm's shards in order -- shard i's spares are its own, so a backfill
    can never count one seed twice. A short last core keeps its full size as
    the counting target and its own spares. An empty or exhausted reserve
    leaves a shard with no spares: the pre-reserve behaviour.
    """
    chunks: list[list[int]] = []
    for core in cores:
        seeds = span(core)
        chunks += [seeds[i:i + size] for i in range(0, len(seeds), size)]
    pool = span(reserve) if reserve else []
    per = -(-len(pool) // len(chunks)) if pool else 0
    out = []
    for i, chunk in enumerate(chunks):
        spares = pool[i * per:(i + 1) * per]
        out.append({
            'seeds': f'{chunk[0]}-{chunk[-1]}',
            'reserve': f'{spares[0]}-{spares[-1]}' if spares else '',
            'target': len(chunk),
        })
    return out


def assert_disjoint(arms: list[dict]) -> None:
    """Every DISTINCT seed text an arm set uses -- `seeds`, `held`,
    `reserve` -- occupies its own space.

    Identical texts overlap on purpose: that is how arms are paired. A
    partial overlap between different texts is the trap -- two shards
    reading the same games while presenting as independent, and (with
    reserves) a seed that could be counted twice in one pool.
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
