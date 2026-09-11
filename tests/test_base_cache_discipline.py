"""Anything that moves the board mid-ranking must drop the base caches.

`delta` prices a change against per-decision caches -- `_base_regions`,
`_base_margins`, `_base_country` -- that are keyed on *the board as it
was synced*. Its own comment says so: "anyone committing a change
mid-ranking must clear `_base_regions`."

The half-action-round forward search did not, and the consequence was
not a small error. `_after_reply` placed a trial point, then asked
`delta` what the opponent's answer was worth -- and `delta` answered
from a base computed for the board *before* the point. The sign
inverted: chosen breaks came back **more** attractive, Iran 26.2 -> 36.2
and Pakistan 32.6 -> 36.1, so a term written to discourage poking
encouraged it. The measured minimum-poke rate was 13.25 a game against
an expected 1, and dropped to 0.25 once the caches were invalidated.

That is the seventh occurrence of this repository's commonest defect --
a cached value keyed on less state than it reads -- and the first one
written by the same hand that had just documented the other six. Hence
this file: the rule is now checked mechanically rather than remembered.
"""
from __future__ import annotations

import os
import pathlib

import pytest

# The two ways a method moves the board.
PROBE = """
import sys; sys.path.insert(0, %r)
import dataclasses
from struggler.bots.strategic import evaluator as ev, policy as pol
from struggler.bots.strategic import StrategicWeights
from conftest import bare_engine
from struggler.engine import Side
assert ev.DIGEST and pol.CHECK_SNAPSHOT, 'the checker must be on'

# Reconstruct the defect exactly: `_after_reply` moves the board and then
# asks `delta` about it, without dropping the base caches first.
original = pol.StrategicPlayer._invalidate_base
pol.StrategicPlayer._invalidate_base = lambda self: None

w = dataclasses.replace(StrategicWeights(), reply_model=3.0)
e = bare_engine()
e.board.influence['Italy']['US'] = 2
e.board.influence['Greece']['USSR'] = 1
e.begin_influence_operations(Side.USSR, 4)
b = pol.StrategicPlayer(w)
try:
    b.rank_actions(e.observe(Side.USSR))
except AssertionError as exc:
    assert 'moved away from the base' in str(exc), exc
    print('GUARD FIRED')
else:
    print('GUARD SILENT')

pol.StrategicPlayer._invalidate_base = original
e2 = bare_engine()
e2.board.influence['Italy']['US'] = 2
e2.board.influence['Greece']['USSR'] = 1
e2.begin_influence_operations(Side.USSR, 4)
pol.StrategicPlayer(w).rank_actions(e2.observe(Side.USSR))
print('OK WITH INVALIDATE')
"""


def test_a_ranking_that_moves_the_board_without_invalidating_is_caught():
    """The regression test for the defect itself, reconstructed.

    `_after_reply` places a trial point and asks `delta` what the
    opponent's answer is worth. When it did that without dropping the base
    caches, `delta` priced against a board that was no longer there and
    the **sign inverted**: breaks came back more attractive, Iran
    26.2 -> 36.2, so a term written to discourage poking encouraged it.
    The minimum-poke rate was 13.25 a game against an expected 1, and fell
    to 0.25 once the caches were invalidated.

    Stubbing `_invalidate_base` to a no-op puts the bug back, and the
    checker must catch it. Note the base caches exist only *during* a
    ranking -- `rank_actions` clears them on the way out -- so the guard
    has to be provoked inside one, which an earlier version of this test
    failed to do and passed vacuously.

    Subprocess because `STRUGGLER_CHECK_SNAPSHOT` is read at import.
    """
    import subprocess
    import sys
    env = dict(os.environ, STRUGGLER_CHECK_SNAPSHOT='1')
    result = subprocess.run(
        [sys.executable, '-c', PROBE % str(pathlib.Path(__file__).parent)],
        capture_output=True, text=True, env=env,
        cwd=str(pathlib.Path(__file__).parent.parent))
    assert result.returncode == 0, result.stderr[-2000:]
    assert 'GUARD FIRED' in result.stdout, (
        'a ranking moved the board and `delta` priced against a stale base '
        f'without complaint.\n{result.stdout}')
    assert 'OK WITH INVALIDATE' in result.stdout, (
        f'the real code path now trips its own guard.\n{result.stdout}')


def test_the_forward_search_discounts_a_break_rather_than_rewarding_it():
    """The behavioural half, stated as a direction rather than a number.

    A break that the opponent can undo cheaply must be worth *less* after
    the reply than before it. When the caches went stale this was
    inverted, and no unit test noticed because every one of them asked
    about a single value rather than about the sign of a difference.
    """
    import dataclasses
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from conftest import bare_engine
    from struggler.bots.strategic import StrategicPlayer, StrategicWeights
    from struggler.engine import Side

    weights = dataclasses.replace(StrategicWeights(), reply_model=3.0)
    engine = bare_engine()
    engine.board.influence['Italy']['US'] = 2      # US controls, bare
    engine.board.influence['Greece']['USSR'] = 1   # so the USSR can reach it
    engine.begin_influence_operations(Side.USSR, 4)

    bot = StrategicPlayer(weights)
    obs = engine.observe(Side.USSR)
    bot.rank_actions(obs)
    raw = bot.delta(obs, 'Italy', own=1)
    after = bot._after_reply(obs, 'Italy', 1, raw)

    assert raw > 0, 'breaking bare control should look good before the reply'
    assert after < raw, (
        f'the reply made the break MORE attractive ({raw:.1f} -> {after:.1f}); '
        f'this is the stale-base inversion')
    assert after < 0.5 * raw, (
        f'a break the opponent undoes for one Op should lose most of its '
        f'value, not {100 * after / raw:.0f}% of it')
