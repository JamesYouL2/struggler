"""A pre-split bot runs from its own namespace, and leaves `struggler.bots` alone.

`scripts/legacy_anchor.py` exists because `benchmark.load_module` must undo
every substitution it makes (two tests in test_benchmark.py pin that), and a
bot from before the package split imports `struggler.bots.public_cards` inside
a function, after the undo. Rewriting the snapshot to its own package name
is the alternative; these check the two things it has to be true to: the old
bot binds its OWN modules, including through a lazy import, and nothing it
loads lands under `struggler.bots`.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys

from conftest import ROOT


def _harness():
    spec = importlib.util.spec_from_file_location('legacy_anchor', ROOT / 'scripts' / 'legacy_anchor.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_rewrite_binds_the_snapshot_and_leaks_nothing(tmp_path, monkeypatch):
    pkg = 'legacy_test000'
    root = tmp_path / pkg
    root.mkdir()
    (root / '__init__.py').write_text('')
    # A name today's package does not have at this path, imported lazily --
    # exactly the shape that failed.
    (root / 'public_cards.py').write_text("MARKER = 'snapshot cards'\n")
    (root / 'strategic.py').write_text(
        'from struggler.bots import public_cards as eager\n'
        'class StrategicPlayer:\n'
        '    def lazy(self):\n'
        '        from struggler.bots.public_cards import MARKER\n'
        '        return MARKER\n')
    before = {k for k in sys.modules if k.startswith('struggler.bots')}

    entry = _harness().rewrite(root, pkg)
    assert 'struggler.bots' not in (root / 'strategic.py').read_text()

    monkeypatch.syspath_prepend(str(tmp_path))
    spec = importlib.util.spec_from_file_location('legacy_entry_under_test', entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    player = module.StrategicPlayer()
    assert player.lazy() == 'snapshot cards', 'the lazy import must bind the snapshot'
    assert sys.modules[f'{pkg}.public_cards'].MARKER == 'snapshot cards'

    after = {k for k in sys.modules if k.startswith('struggler.bots')}
    assert after == before, f'the legacy bot registered {sorted(after - before)} under struggler.bots'
    for key in [k for k in sys.modules if k.startswith(pkg)]:
        del sys.modules[key]


def test_a_snapshot_that_still_names_the_real_package_is_refused(tmp_path, monkeypatch):
    """The guard is what makes a missed import form loud. Break the
    substitution and the rewrite must refuse, not hand back a snapshot that
    would bind today's module and play part of the candidate."""
    import pytest

    root = tmp_path / 'legacy_test001'
    root.mkdir()
    (root / 'strategic.py').write_text('from struggler.bots import greedy\nclass StrategicPlayer: pass\n')
    harness = _harness()
    monkeypatch.setattr(harness, '_substitute', lambda text, pkg: text)
    with pytest.raises(RuntimeError, match='still referenced'):
        harness.rewrite(root, 'legacy_test001')
