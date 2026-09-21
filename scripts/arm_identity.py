"""The identity of an experiment shard: what makes its result reproducible.

A benchmark game is `Engine.new_game(seed=...)` driven by two deterministic
players, and chance is a logged CHANCE decision (mandate #3). So a shard's
report is a pure function of

    (the engine and bots that played, the opponent, the weights, the seeds,
     the opening books)

and re-running the same shard is guaranteed to reproduce it. That is what
lets `experiments.yml` cache a shard instead of replaying it -- which is not
a micro-optimisation: on 2026-09-21 one hung shard forced a 16-shard re-run
to recover a single missing 128-seed slice, and the other 15 shards replayed
answers already known to the thousandth.

THE KEY HAS TO COVER EVERYTHING THAT CAN CHANGE PLAY, or the cache serves a
stale reading, which is worse than no cache at all. That is why it keys on
the tree hash of `src/` and not of `src/struggler/bots`: the gate's notion
of "the bot" is the bots package alone, but the ENGINE decides what a play
does, and `src/struggler/data` holds the cards. A cache keyed on the bots
package would survive a rules change and hand back a reading from a
different game.

`bot_ref` and `anchor` are resolved to commit SHAs by the caller, because a
branch name is not an identity -- the same name is a different bot tomorrow.

`runtime` is the interpreter version. The package declares no runtime
dependencies and the benchmark is stdlib, so CPython is the only thing
outside `src/` that the games run on -- and a runner image can move it
underneath an unchanged repository. It is in the key because leaving it out
would be an assumption about float arithmetic across versions that nobody
here has measured.

What is deliberately NOT in the key: `slug`, `shard`, `of`, `compare_to`
and `logs`. The first four are bookkeeping -- two arms that differ only in
name play the same games, which is what lets one arm reuse another's
shards. `logs` is the one real hole: it changes the ARTIFACT (tens of MB of
INFO logs) without changing the REPORT, so a hit would serve the report
without the logs. The workflow closes that by not restoring for an arm that
asked for logs; the key cannot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

# Bump when the key's MEANING changes -- a new field, or a different notion
# of what makes a shard reproducible. Bumping invalidates every entry, which
# is the point: an old entry was computed under the old meaning.
VERSION = 'v1'


def canonical_weights(weights: dict | None) -> str:
    """Weights as one string, key order and float formatting fixed.

    `{'a': 1.0}` and `{'a': 1}` are the same bot, and a dict's insertion
    order is not part of its meaning; both must hash the same.
    """
    items = {k: float(v) for k, v in sorted((weights or {}).items())}
    return json.dumps(items, separators=(',', ':'), sort_keys=True)


def cache_key(*, src_tree: str, seeds: str, weights: dict | None = None,
              bot_ref_sha: str = '', anchor_sha: str = '', openings: str = '',
              runtime: str = '', version: str = VERSION) -> str:
    """A stable digest of everything that decides a shard's report."""
    if not src_tree:
        raise ValueError('src_tree is required: without it the key cannot see a code change')
    if not seeds:
        raise ValueError('seeds is required')
    material = '|'.join((
        version, src_tree, bot_ref_sha, anchor_sha,
        canonical_weights(weights), seeds, openings, runtime,
    ))
    return 'exp-' + hashlib.sha256(material.encode()).hexdigest()[:32]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--shard', required=True, help="the matrix shard object, as JSON")
    ap.add_argument('--src-tree', required=True, help="git rev-parse HEAD:src")
    ap.add_argument('--bot-ref-sha', default='', help='resolved commit for the arm bot_ref, if any')
    ap.add_argument('--anchor-sha', default='', help='resolved commit for the arm anchor, if any')
    ap.add_argument('--runtime', default='', help='the interpreter the games will run on')
    args = ap.parse_args(argv)

    shard = json.loads(args.shard)
    print(cache_key(
        src_tree=args.src_tree,
        seeds=shard['seeds'],
        weights=shard.get('weights'),
        bot_ref_sha=args.bot_ref_sha,
        anchor_sha=args.anchor_sha,
        openings=shard.get('openings', ''),
        runtime=args.runtime,
    ))
    return 0


if __name__ == '__main__':
    sys.exit(main())
