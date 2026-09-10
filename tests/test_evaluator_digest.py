"""`Position.digest` is a content hash, and it must never drift from `inf`.

The commonest defect in this repo, six times over, is a cached value keyed
on less state than it reads. `_access` was keyed on one country while
reading influence two hops out, so a trial placement left it stale and 39
of 598 corpus rankings changed when the memo was bypassed.

Six recurrences say the fix is not more careful key-writing. `digest` gives
the position an identity instead: equal influence means an equal digest,
any change to any country changes it, and an undo restores it exactly. A
memo keyed on `(pos.digest, ...)` is therefore correct however far its term
reads, and still hits in the trial-placement loops, which put the board
back between candidates.

All of which is worth nothing if the digest and the influence it summarises
can come apart, so that is what these tests pin -- not the digest's value,
which is an implementation detail, but the invariant.
All of which is worth nothing if the digest and the influence it
summarises can come apart, so that is what these tests pin -- not the
digest's value, which is an implementation detail, but the invariant.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import random

import pytest

from struggler.bots.strategic import evaluator as ev
from struggler.engine import Engine

CORPUS = pathlib.Path(__file__).parent / 'corpus' / 'positions.json.gz'


@pytest.fixture(autouse=True)
def digest_on(monkeypatch):
    """The digest is off in production -- maintaining it costs 6.4% of bot
    time and the memo it enables is worth 2.3%, so it earns its place as a
    correctness instrument rather than a performance one. These tests are
    that instrument, so they turn it on."""
    monkeypatch.setattr(ev, 'DIGEST', True)


def recomputed(pos: ev.Position) -> int:
    """The digest derived from `inf` alone, the slow and obvious way."""
    keys = ev._zobrist_table(len(pos.terrain.ids))
    out = 0
    for i in range(len(pos.terrain.ids)):
        out ^= keys[ev.US][i][ev._fold(pos.inf[ev.US][i])]
        out ^= keys[ev.USSR][i][ev._fold(pos.inf[ev.USSR][i])]
    return out


@pytest.fixture(scope='module')
def boards():
    records = json.loads(gzip.open(CORPUS).read())['records']
    return [Engine.deserialize(r['engine']).board for r in records[::37]]


def test_the_digest_always_describes_the_influence_it_summarises(boards):
    """The invariant, over every mutation path: `sync`, `refresh`, `place`,
    and long random walks of placements. A write site that forgets to
    maintain the digest fails here rather than silently poisoning a memo."""
    rng = random.Random(20260910)
    for board in boards:
        pos = ev.Position().sync(board)
        assert pos.digest == recomputed(pos), 'sync'
        for _ in range(60):
            i = rng.randrange(len(pos.terrain.ids))
            pos.place(i, rng.randrange(0, 9), rng.randrange(0, 9))
            assert pos.digest == recomputed(pos), 'place'
        pos.refresh(board)
        assert pos.digest == recomputed(pos), 'refresh'
        assert pos.digest == ev.Position().sync(board).digest, 'refresh == sync'


def test_equal_influence_means_an_equal_digest(boards):
    """Both directions. Equal boards agree, and no two different boards in
    the sample collide -- a collision would be a silently wrong memo, so it
    is worth knowing if one ever appears."""
    seen = {}
    for board in boards:
        pos = ev.Position().sync(board)
        twin = ev.Position().sync(board)
        assert pos.digest == twin.digest
        key = (tuple(pos.inf[ev.US]), tuple(pos.inf[ev.USSR]))
        clash = seen.setdefault(pos.digest, key)
        assert clash == key, f'digest collision between two different boards: {pos.digest:x}'


def test_an_undone_placement_restores_the_digest_exactly(boards):
    """What makes the digest useful rather than merely safe. The placement
    loops try a country, price it, and put the board back; a monotonic
    counter would invalidate every one of those and never hit."""
    rng = random.Random(7)
    for board in boards[:6]:
        pos = ev.Position().sync(board)
        before = pos.digest
        for _ in range(25):
            i = rng.randrange(len(pos.terrain.ids))
            was = pos.place(i, rng.randrange(0, 7), rng.randrange(0, 7))
            pos.place(i, *was)
            assert pos.digest == before, 'undo did not restore the digest'


def test_every_single_country_change_moves_the_digest(boards):
    """No blind spots: adding one point anywhere must change the hash, for
    both sides and every country. A term that reads a neighbour depends on
    this being true of the neighbour, not only of itself."""
    board = boards[0]
    pos = ev.Position().sync(board)
    for i in range(len(pos.terrain.ids)):
        for side in (ev.US, ev.USSR):
            before = pos.digest
            us, ussr = pos.inf[ev.US][i], pos.inf[ev.USSR][i]
            bumped = (us + 1, ussr) if side == ev.US else (us, ussr + 1)
            was = pos.place(i, *bumped)
            assert pos.digest != before, (
                f'{pos.terrain.ids[i]} side {side} moved without changing the digest')
            pos.place(i, *was)
            assert pos.digest == before
