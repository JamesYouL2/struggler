"""No new bare constants added to board-unit values.

Shape 6 in `docs/CLAUDE_NOTES.md`, "a number on the wrong scale", has
recurred at least four times, most recently in a commit whose whole
subject was scale discipline: `CHINA_HOLD_OPS` was named in Ops,
documented in Ops, pinned by a test asserting an Ops floor, and
subtracted from a value where one Op is worth eighty-odd.

The bot's raw scale is large and position-dependent -- one Op is 28 raw
on the opening board and 84 at turn 4 of a developed one -- so a bare
`- 5` looks like a real adjustment and is worth 0.06 Ops. Nothing in the
type system or the tests catches that. This does.

The rule: anything added to or subtracted from a value on the board
scale must itself carry that scale, by passing through one of the
pricing functions or by being multiplied by a weight and an importance.
Two sites do not, both deliberate and both documented; they are listed
here so that closing them is a decision and adding a third is a failure.
"""
from __future__ import annotations

import ast
import pathlib

STRATEGIC = pathlib.Path(__file__).parent.parent / 'src' / 'struggler' / 'bots' / 'strategic'

# Local names that hold a board-scale quantity.
BOARD = {'value', 'score', 'v', 'total', 'loss', 'gain', 'worth', 'best', 'harm',
         'floor', 'mean', 'out', 'risk', 'cap', 'delta', 'base', 'cost', 'credit'}
# Calls whose result is already on the raw board scale.
SCALED_CALLS = {
    'ops_value', 'vp_value', 'game_value', 'event_value', 'card_play_value',
    'hold_value', 'country_value', 'region_score', 'region_margin', 'evaluate',
    'coup', 'realign', 'wipe_risk', 'space_value', 'scoring_card_value',
    'importance', 'seat', 'priced', '_investment', 'access', 'delta',
    '_shallow_event_value', 'military_credit', 'per_card', '_resolve_sandbox',
    'final_scoring_odds',
}
# Names that are board-scale quantities or the weights that scale them.
SCALED_NAMES = BOARD | {'one_op', 'per_vp', 'imp', 'gap', 'guard', 'urgency',
                        'outcomes', 'w', 'weights', 'self', 'ev', 'margins',
                        'before', 'holds', 'pool'}

# The two known unscaled adjustments, as (file, source line). Both are
# deliberate and documented; see docs/CLAUDE_NOTES.md, "The China charge is in
# the wrong units". Matched on source text rather than line number so that
# editing around them does not break the test.
KNOWN = {
    ('policy.py', 'value -= CHINA_HOLD_RAW'),
    ('policy.py', 'value -= max(0, len(obs.hand)-3)'),
}


def _carries_scale(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            fn = n.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', None)
            if name in SCALED_CALLS:
                return True
        if isinstance(n, ast.Name) and n.id in SCALED_NAMES:
            return True
        if isinstance(n, ast.Attribute) and n.attr in SCALED_CALLS:
            return True
    return False


def _unscaled_sites() -> set[tuple[str, str, int]]:
    found = set()
    for path in sorted(STRATEGIC.glob('*.py')):
        source = path.read_text()
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.AugAssign)
                    and isinstance(node.op, (ast.Add, ast.Sub))
                    and isinstance(node.target, ast.Name)
                    and node.target.id in BOARD
                    and not _carries_scale(node.value)):
                found.add((path.name, lines[node.lineno - 1].strip(), node.lineno))
    return found


def test_no_new_bare_constants_on_board_unit_values():
    sites = _unscaled_sites()
    new = {(f, src) for f, src, _ in sites} - KNOWN
    assert not new, (
        'a value on the board scale is being adjusted by something that does '
        'not carry that scale:\n'
        + '\n'.join(f'  {f}:{ln}  {src}' for f, src, ln in sorted(sites)
                    if (f, src) not in KNOWN)
        + '\n\nOne Op is 28 to 84 raw depending on the position, so a bare number '
          'here is a rounding error wearing the costume of an adjustment. Price '
          'it through ops_value/vp_value/game_value, or add it to KNOWN with a '
          'comment saying why it is deliberate.')


def test_the_known_unscaled_sites_are_still_there():
    """If one is fixed, this fails and the entry comes out of `KNOWN` -- so the
    allowlist cannot rot into a list of things that no longer exist."""
    present = {(f, src) for f, src, _ in _unscaled_sites()}
    stale = KNOWN - present
    assert not stale, (
        f'these are on the allowlist but no longer in the source: {sorted(stale)}. '
        f'Remove them from KNOWN.')
