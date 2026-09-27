"""The bot package imports nothing from `struggler.fitting`.

`forecast` and `valuation` moved out of `bots/strategic/` on 2026-09-27
because they are offline tooling -- the exact target
`scripts/fit_country_weights.py` fits the shipped country weights against
-- and the bots package is what a gate's baseline snapshot and the Rust
port copy. An import from `struggler.bots` into `struggler.fitting` would
put fitting code back on the path play can reach, and a snapshot of the
bots package would silently bind the candidate's fitting modules instead
of its own. A static scan, so it catches an import inside a function too.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).parent.parent / 'src' / 'struggler'
BOTS = SRC / 'bots'


def _fitting_imports(path: pathlib.Path, root: pathlib.Path = SRC) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            # `from struggler import fitting` and `from struggler.fitting
            # import x` both count; so does a relative `from ...fitting`.
            names = [node.module or ''] + [f'{node.module}.{a.name}' for a in node.names]
        else:
            continue
        for name in names:
            if name.split('.')[:2] == ['struggler', 'fitting'] or name.split('.')[0] == 'fitting':
                found.append(f'{path.relative_to(root)}:{node.lineno}: {name}')
                break
    return found


def test_the_bots_package_never_imports_fitting():
    sources = sorted(BOTS.rglob('*.py'))
    assert sources, f'no sources under {BOTS}'
    offenders = [hit for path in sources for hit in _fitting_imports(path)]
    assert not offenders, (
        'struggler.bots imports struggler.fitting, which is offline tooling '
        'the bot must not depend on:\n' + '\n'.join(offenders))


def test_the_scan_sees_a_fitting_import(tmp_path):
    """Negative control: the scanner must flag the import it exists to catch."""
    for line in ('from struggler.fitting import forecast as fcst',
                 'import struggler.fitting.valuation',
                 'from struggler import fitting',
                 'def f():\n    from struggler.fitting.forecast import tier_of'):
        probe = tmp_path / 'probe.py'
        probe.write_text(line + '\n')
        assert _fitting_imports(probe, tmp_path), line

