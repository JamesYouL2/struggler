"""The scripts address the source tree by string, so a rename breaks them
silently.

`scripts/profile_baseline.py` names the paths it profiles as substrings
matched against a profile's frame filenames. When `bots/strategic.py`
became `bots/strategic/`, seven of its ten rows stopped matching anything
and the report went on printing them as 0% -- not "this is cheap", but
"this question was not asked", and the output cannot tell the two apart.

The script now raises on a row that matches no frame, but only when it is
run, and it is run rarely, by hand, on a machine quiet enough for the
timings to mean anything. This test is the cheap half: every path it
names must still exist in the tree. It cannot catch a function renamed
while its module stayed put -- `shares()` does that at profile time --
but it does catch the move that actually happened.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src' / 'struggler'


def _paths():
    spec = importlib.util.spec_from_file_location(
        'profile_baseline', ROOT / 'scripts' / 'profile_baseline.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATHS


def missing(file_part: str) -> str | None:
    """The reason `file_part` names nothing, or None if it resolves.

    Trailing-slash parts name a package directory; the rest name a module.
    Paths outside `struggler` (the stdlib's `enum.py`) are not ours to check.
    """
    if not file_part.startswith(('bots/', 'engine/')):
        return None
    if (PACKAGE / file_part).exists():
        return None
    return (f'{file_part} is not in the tree. A profile row that matches nothing '
            f'reports 0%, which reads as "cheap" rather than "not measured" -- '
            f'update scripts/profile_baseline.py:PATHS.')


@pytest.mark.parametrize('label', list(_paths()))
def test_profiled_path_still_exists(label):
    file_part, _func = _paths()[label]
    assert missing(file_part) is None, f'profile row {label!r}: {missing(file_part)}'


def test_the_move_that_happened_is_caught():
    """Reconstruct the defect. `bots/strategic.py` is what the rows named
    before the split, and the checker has to object to it -- otherwise this
    file passes by never rejecting anything."""
    assert not (PACKAGE / 'bots/strategic.py').exists(), \
        'the package split is undone; this test no longer means anything'
    assert missing('bots/strategic.py') is not None
    assert missing('bots/defcon.py') is not None
    assert missing('bots/strategic/policy.py') is None  # and it accepts what is there
