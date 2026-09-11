"""One gate per defect shape that has bitten this repo more than once.

`docs/CLAUDE_NOTES.md` "The bugs this repo actually gets" lists eight
shapes with how often each has recurred. The maintainer's rule is that a
mistake made twice is a property of the code, not of whoever made it, and
the only thing that fixes a property is a test.

This file is the index and the backstop:

- `SHAPE_GATES` names, for every shape, the tests that make it fail. Most
  live in the file that owns the subject -- region scoring against the
  engine in `test_evaluator.py`, the gate's isolation in
  `test_benchmark.py` -- and are only *listed* here.
- `test_every_recurring_shape_has_a_gate` reads the notes and requires an
  entry for every shape recorded as having happened twice or more. Add a
  recurrence to the notes and the suite asks for the test.
- The gates that had no home anywhere else are written below: the sentinel
  (shape 2), interleaved timing (shape 7), and the characterisation-test
  convention (shape 8).
"""
from __future__ import annotations

import dataclasses
import re
import time
from pathlib import Path

import pytest

from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.policy import LOSS, Certain, is_certain, priced
from struggler.engine import Engine, Side

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / 'docs' / 'CLAUDE_NOTES.md'
TESTS = Path(__file__).resolve().parent

WORD_COUNTS = {'once': 1, 'twice': 2, 'three': 3, 'four': 4, 'five': 5,
               'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

SHAPE_GATES: dict[int, list[str]] = {
    1: ['test_values_do_not_depend_on_the_order_they_are_asked_for',
        'test_a_repeated_question_gives_a_repeated_answer',
        'test_every_single_country_change_moves_the_digest',
        'test_a_ranking_that_moves_the_board_without_invalidating_is_caught'],
    2: ['test_a_certain_outcome_refuses_arithmetic',
        'test_a_certain_outcome_still_orders',
        'test_the_value_terms_bound_the_sentinel_before_returning_it'],
    3: ['test_a_baseline_policy_loads_its_own_bot_modules_not_the_candidates',
        'test_a_snapshotted_package_binds_its_own_submodules',
        'test_an_opponent_nuclear_defeat_is_not_a_candidate_nuclear_loss',
        'test_early_stopping_never_predicts_a_held_out_seed_from_a_tuning_seed',
        'test_acceptance_warns_when_every_game_is_a_dead_heat',
        'test_every_record_pins_every_weight'],
    4: ['test_region_vp_matches_the_engine_region_scoring',
        'test_region_vp_matches_the_engine_under_every_scoring_override',
        'test_coup_forbidden_matches_the_engine_under_every_prohibition',
        'test_shared_history_names_no_card_it_has_not_revealed',
        'test_the_bot_takes_its_ops_modifiers_from_the_engine'],
    5: ['test_a_broken_event_simulation_is_reported_not_silently_estimated',
        'test_the_sandbox_drives_every_event_it_claims_to',
        'test_profiled_path_still_exists'],
    6: ['test_no_new_bare_constants_on_board_unit_values',
        'test_the_known_unscaled_sites_are_still_there',
        'test_every_weight_and_prior_has_an_entry',
        'test_declared_values_match_the_code'],
    7: ['test_interleaved_comparison_alternates_between_the_arms',
        'test_interleaved_comparison_survives_a_drifting_machine',
        'test_a_sequential_comparison_is_fooled_by_the_same_drift'],
    8: ['test_mutation_can_be_restricted_to_named_weights',
        'test_every_characterisation_test_says_so'],
}


# -- the index ---------------------------------------------------------------


def recurring_shapes() -> dict[int, tuple[str, int]]:
    """Every numbered shape in the notes, with its recorded count."""
    found = {}
    for line in NOTES.read_text().splitlines():
        m = re.match(r'^### (\d+)\. (.+?) \((\w+)[ ,)]', line)
        if m and m.group(3).lower() in WORD_COUNTS:
            found[int(m.group(1))] = (m.group(2), WORD_COUNTS[m.group(3).lower()])
    return found


def all_test_names() -> set[str]:
    names = set()
    for path in TESTS.glob('test_*.py'):
        names.update(re.findall(r'^def (test_\w+)', path.read_text(), re.M))
    return names


def test_the_notes_still_list_the_shapes_in_the_form_this_file_reads():
    """A parse that finds nothing would make every check below vacuous."""
    shapes = recurring_shapes()
    assert len(shapes) >= 8, f'only parsed {sorted(shapes)} from {NOTES.name}'


@pytest.mark.parametrize('shape', sorted(recurring_shapes()))
def test_every_recurring_shape_has_a_gate(shape):
    """The maintainer's rule, mechanised: twice means a test."""
    title, count = recurring_shapes()[shape]
    if count < 2:
        pytest.skip(f'shape {shape} has happened once')
    assert SHAPE_GATES.get(shape), (
        f'shape {shape} ({title}) has happened {count} times and no test is '
        f'named for it. Add the gate, then list it in SHAPE_GATES -- a note '
        f'is not a gate.')


@pytest.mark.parametrize('shape', sorted(SHAPE_GATES))
def test_the_named_gates_exist(shape):
    """A registry of names that have been renamed away gates nothing."""
    missing = sorted(set(SHAPE_GATES[shape]) - all_test_names())
    assert not missing, (
        f'shape {shape} names tests that no longer exist: {missing}. '
        f'They were renamed or deleted; the shape is ungated until this is fixed.')


# -- shape 2: a sentinel used as a number ------------------------------------


def test_a_certain_outcome_refuses_arithmetic():
    """`LOSS` escaped into arithmetic four times -- `ops_value`,
    `_resolve_sandbox` (`0.4167 * LOSS`), `hold_value`, `_hand_upgrade_value`
    -- and each fix was another clamp at another boundary. `Certain` makes
    it unrepresentable instead: the operations that would turn an ordering
    flag into a price raise."""
    for operation in (lambda: LOSS + 1, lambda: 1 + LOSS, lambda: LOSS - 1,
                      lambda: 1 - LOSS, lambda: LOSS * 2, lambda: 2 * LOSS,
                      lambda: LOSS / 2, lambda: 2 / LOSS, lambda: LOSS // 2,
                      lambda: LOSS % 2, lambda: sum([LOSS, 1.0])):
        with pytest.raises(TypeError, match='ordering flag, not a price'):
            operation()


def test_a_certain_outcome_still_orders():
    """It has to keep working as a flag, or the safety keys break: the
    point is to refuse pricing, not to refuse comparison."""
    assert LOSS < -1000. and min(LOSS, 0.) is LOSS
    assert max(LOSS, 0.) == 0.
    assert sorted([0., LOSS, 5.])[0] is LOSS
    assert is_certain(LOSS) and is_certain(-LOSS) and not is_certain(-5.)
    assert isinstance(-LOSS, Certain) and -LOSS > 0  # negation is the certain win
    assert isinstance(abs(LOSS), Certain)
    assert priced(LOSS, 40.) == -40. and not isinstance(priced(LOSS, 40.), Certain)


def test_the_value_terms_bound_the_sentinel_before_returning_it():
    """The escapes were all one step: a value term handing the flag to a
    caller that averages. `hold_value` is where it bit hardest -- a hand
    holding one unplayable card priced at -999,904, and the mean of that
    hand is not a number."""
    engine = Engine.new_game(seed=4000, setup_bonus=True)
    bot = StrategicPlayer()
    obs = engine.observe(Side.USSR)
    bot.rank_actions(obs)
    cap = bot.game_value(obs)
    for cid in obs.hand:
        for shallow in (False, True):
            value = bot.hold_value(obs, cid, shallow=shallow)
            assert not is_certain(value), f'hold_value({cid}) returned the sentinel'
            assert abs(value) <= cap + 1e-9, f'hold_value({cid}) = {value} exceeds {cap}'


# -- shape 4: two implementations of one rule, drifting ----------------------


def test_the_bot_takes_its_ops_modifiers_from_the_engine():
    """The bot once had its own copy of the Ops modifiers, and both copies
    were missing the Containment/Brezhnev ceiling -- so a 4-Ops card under
    Containment was worth 5 to each of them, consistently and wrongly.

    It is derived now (`_effective_ops_estimate` calls `effective_ops`),
    which is the strong fix; this proves the two still agree over every
    combination rather than trusting that nobody re-inlines it. The rule
    has three independent flags and two bounds, so the space is small
    enough to walk exhaustively -- and each bound is asserted to have
    actually fired, or the walk could pass while testing nothing.
    """
    import itertools

    from struggler.bots.greedy import _effective_ops_estimate
    from struggler.engine.core import OPS_CEILING, OPS_FLOOR, effective_ops

    class FakeCard:
        def __init__(self, ops):
            self.ops = ops

    engine = Engine.new_game(seed=4000, setup_bonus=True)
    observation = engine.observe(Side.US)
    floored = capped = 0
    for ops, containment, brezhnev, red_scare, side in itertools.product(
            range(1, 5), (False, True), (False, True),
            (None, 'US', 'USSR'), (Side.US, Side.USSR)):
        effects = {}
        if containment:
            effects['containment'] = True
        if brezhnev:
            effects['brezhnev'] = True
        if red_scare:
            effects['red_scare'] = red_scare
        expected = effective_ops(ops, effects, side)
        seat_view = dataclasses.replace(observation, turn_effects=effects)
        assert _effective_ops_estimate(FakeCard(ops), seat_view, side) == expected, (
            f'the bot and the engine disagree at ops={ops} {effects} {side}')
        floored += expected == OPS_FLOOR
        capped += expected == OPS_CEILING
    assert floored and capped, (
        f'the walk never reached a bound (floor {floored}, ceiling {capped}), '
        f'so it would pass with both bounds deleted')


# -- shape 7: timing measured under uncontrolled conditions ------------------


def interleaved(arms: dict[str, object], repeats: int, clock=time.perf_counter) -> dict[str, float]:
    """Total seconds per arm, running them alternately.

    Three times this repo has compared two timings taken under conditions
    that were not the same -- twice in one night, a 3x "slowdown" that was
    a gate running in the background and a 3.7x "speedup" that was two
    different revisions. Interleaving is what makes the comparison a
    comparison: whatever the machine is doing, it is doing it to both arms.

    `clock` is injectable so the tests below can prove that without
    measuring anything. A test of a timing method that depends on real
    timings is the same mistake one level up -- the first version of it
    failed on this machine because a gate was running, which is the
    sentence this whole shape is about.
    """
    totals = {name: 0. for name in arms}
    for _ in range(repeats):
        for name, arm in arms.items():
            start = clock()
            arm()
            totals[name] += clock() - start
    return totals


def sequential(arms: dict[str, object], repeats: int, clock=time.perf_counter) -> dict[str, float]:
    """The wrong way, kept so a test can show it is the wrong way."""
    totals = {}
    for name, arm in arms.items():
        start = clock()
        for _ in range(repeats):
            arm()
        totals[name] = clock() - start
    return totals


def drifting_machine():
    """A clock on which every unit of work costs more than the last.

    The drift stands in for the contention behind the real errors: it is a
    property of *when* the work runs, not of which arm runs it. Two arms
    that do identical work must therefore measure as identical under any
    honest comparison.
    """
    now = {'t': 0., 'step': 1.}

    def clock():
        return now['t']

    def work():
        now['t'] += now['step']
        now['step'] += 0.05      # the machine gets slower as the run goes on

    return clock, {'a': work, 'b': work}


def test_interleaved_comparison_alternates_between_the_arms():
    """The mechanism, before the claim about it: each repeat runs every arm
    once, in order."""
    calls = []
    interleaved({'a': lambda: calls.append('a'), 'b': lambda: calls.append('b')},
                repeats=3, clock=lambda: 0.)
    assert calls == ['a', 'b', 'a', 'b', 'a', 'b']


def test_interleaved_comparison_survives_a_drifting_machine():
    """Two identical arms measure as identical, though the machine slows
    by a factor of five across the run."""
    clock, arms = drifting_machine()
    totals = interleaved(arms, repeats=40, clock=clock)
    ratio = totals['a'] / totals['b']
    assert 0.95 < ratio < 1.05, f'interleaving did not cancel the drift: ratio {ratio:.3f}'


def test_a_sequential_comparison_is_fooled_by_the_same_drift():
    """The negative control. Without it the test above proves nothing: it
    would pass on a machine with no drift, which is exactly the condition
    the real measurements did not have."""
    clock, arms = drifting_machine()
    totals = sequential(arms, repeats=40, clock=clock)
    ratio = totals['b'] / totals['a']
    assert ratio > 2., (
        f'the planted drift was too small to fool a sequential comparison '
        f'(ratio {ratio:.2f}); the interleaving test above is then vacuous')


# -- shape 8: a test that encodes the defect as the contract -----------------

# Tests that deliberately pin current behaviour rather than desired
# behaviour. The practice is that they say so, so the next reader does not
# mistake one for a specification -- `test_mutation_can_be_restricted_to_
# named_weights` asserted that *every* weight changes under a default
# mutation, which was the bug it should have caught, and the parity test
# that expected a `vp` ending partway through Final Scoring preserved a
# rules defect the same way. Both have since been rewritten to assert
# intent, which is why this list is empty.
CHARACTERISATION_TESTS: set[str] = set()

_MARKER = re.compile(r'characteris(?:ation|e|ed)|characteriz(?:ation|e|ed)', re.I)


def test_every_characterisation_test_says_so():
    """Declared and found must agree in both directions.

    This is bookkeeping, not detection: nothing here can tell a pinned
    output from a specified one. What it does is keep the category
    visible -- a new characterisation test has to be declared, and a
    declared one that gets deleted or promoted to a real specification
    has to be removed.
    """
    found = set()
    for path in TESTS.glob('test_*.py'):
        source = path.read_text()
        for match in re.finditer(r'^def (test_\w+)\([^)]*\):\n(\s+"""(?:.|\n)*?""")?', source, re.M):
            # The scanner names the category it looks for, so it matches
            # itself; that is bookkeeping about the rule, not a test that
            # pins behaviour.
            if match.group(1) == 'test_every_characterisation_test_says_so':
                continue
            if match.group(2) and _MARKER.search(match.group(2)):
                found.add(match.group(1))
    assert found == CHARACTERISATION_TESTS, (
        f'undeclared: {sorted(found - CHARACTERISATION_TESTS)}; '
        f'declared but gone: {sorted(CHARACTERISATION_TESTS - found)}')
