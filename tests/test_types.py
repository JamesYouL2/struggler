"""The hard type gate: four rules that are clean and must stay clean.

`ty` found a bug on the day it was tried -- `CARDS[c].side is Side.US`
compares a `CardSide` against a `Side`, so it is always False; the term
ran, priced nothing, and returned a plausible zero. mypy missed it in
both the `is` and the `==` form.

Five rules are gated, chosen by counting rather than taste: each was read
finding by finding and kept where real positives outnumbered false ones.
The tally is in `ty-strict.toml`.

The rule that catches that bug is `redundant-condition-strict`, and it was
nearly left off -- an earlier triage credited the catch to
`unsupported-operator` and disabled this one for two false positives. The
negative control below is what found the mistake, by planting the bug and
watching the gate pass it.
Everything else -- about 95 findings of annotation debt, mostly
`Decision | None` where a loop guarantees non-None -- is advisory and
reported by `scripts/gate.sh` step 1c, because gating a backlog means
nobody runs the tool at all.

The rules deliberately *not* gated matter as much. `redundant-condition-
strict` is off because acting on it would have introduced a defect: ty
narrows a property across a mutating call, so after
`if engine.is_terminal: return` it reads the next `not engine.is_terminal`
as always true -- ignoring that the intervening `_change_defcon(-1)` can
reach DEFCON 1 and end the game. Both flagged guards were load-bearing.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from struggler.engine import Region, Side

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'ty-strict.toml'
GATED = ('redundant-condition-strict', 'unsupported-operator',
         'possibly-unresolved-reference', 'call-non-callable',
         'invalid-method-override')


def run_ty(*extra: str) -> subprocess.CompletedProcess:
    # The venv's binary first: `shutil.which` misses it when pytest runs
    # without the venv on PATH, and a type gate that skips is a type gate
    # that does not exist.
    local = ROOT / '.venv' / 'bin' / 'ty'
    ty = str(local) if local.exists() else shutil.which('ty')
    if ty is None:
        pytest.skip('ty is not installed; `uv pip install ty` or the test extra')
    return subprocess.run(
        # No `--ignore all`: it wins over a later `--error`, whichever
        # order the flags are given, so the gate passed while checking
        # nothing. The config silences rules by name instead.
        [ty, 'check', '--config-file', str(CONFIG), '--output-format', 'concise', *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=300)


def test_the_gated_rules_are_clean():
    done = run_ty()
    assert done.returncode == 0, (
        f'a gated type rule fired. These are the four that were at zero and the '
        f'ones that catch real defects -- read the finding before suppressing it.\n'
        f'{done.stdout}\n{done.stderr}')


def test_the_gate_would_catch_the_bug_it_was_adopted_for():
    """A negative control. Without it this file passes whether or not the
    rules are actually enabled, which is how a type gate rots."""
    probe = ROOT / 'src' / 'struggler' / '_ty_probe_tmp.py'
    probe.write_text(
        'from struggler.engine import Side\n'
        'from struggler.engine.cards import load_cards\n'
        'CARDS = load_cards()\n'
        'def rider(hand: list[str]) -> float:\n'
        '    return sum(1.0 for c in hand if CARDS[c].side is Side.US)\n')
    try:
        done = run_ty()
        assert done.returncode != 0, (
            'the gate passed a CardSide-against-Side comparison, which is the '
            'exact bug it was adopted for. The rules are not actually on.')
        # The rule is `redundant-condition-strict`, not
        # `unsupported-operator`. Getting that wrong is what nearly shipped
        # a gate with the useful rule switched off -- pyright words this as
        # "no overlap" and ty's default output prints no rule name, so the
        # catch was credited to the wrong rule for most of a day.
        assert 'redundant-condition-strict' in done.stdout, done.stdout
    finally:
        probe.unlink()


def test_the_fast_attributes_are_the_slow_ones():
    """`Side.key`/`Region.key` and `Side.opp_key` are plain attributes that
    exist only because `Enum.value` is a descriptor costing 82 ns a read.
    They are the SAME facts, so they are held against the descriptors here
    for every member.

    Two copies of one fact is the shape that has bitten this codebase
    repeatedly (docs/notes/claude/bug-shapes.md). The copy is deliberate and
    measured; this is the test that keeps it honest. A member added to either
    enum without a `key` fails here rather than at the first hot-path read.
    """
    for member in (*Side, *Region):
        assert member.key == member.value, f'{member!r}: key {member.key!r} != value'
        assert member.key is member.value, f'{member!r}: key is not the same object'
        assert member.key == member.name, f'{member!r}: these enums name themselves'

    for side in (Side.US, Side.USSR):
        assert side.opp_key == side.opponent.value, f'{side!r}: opp_key disagrees'
        assert side.opp_key is side.opponent.value

    # CHANCE has no opponent, and must not quietly answer as if it had one.
    with pytest.raises(AttributeError):
        _ = Side.CHANCE.opp_key
    with pytest.raises(ValueError):
        _ = Side.CHANCE.opponent
