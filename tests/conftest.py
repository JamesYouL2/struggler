"""Shared test fixtures/helpers.

Centralized here so a mechanic that grows (e.g. the headline-pending
state or Our Man in Tehran's peek queue) only needs to be taught to one
"where do cards live" helper instead of several near-duplicate copies
drifting out of sync (see the ``_headline_pending`` incident in
test_engine_m2.py, fixed by consolidating here).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from struggler.engine import Engine
from struggler.engine.cards import ENTRY_TURN, cards_entering
from struggler.engine.core import HIDDEN_CARD
from struggler.engine.rules import RULES

ROOT = Path(__file__).resolve().parents[1]


def bare_engine(seed: int = 0) -> Engine:
    """A minimal engine with the event layer on but no turn loop running."""
    engine = Engine(seed=seed)
    engine.events_enabled = True
    return engine


def headline_setup(engine: Engine, ussr_card: str, us_card: str) -> None:
    """Put a controlled headline in front of a bare, events-on engine."""
    engine.phase = "headline"
    engine.hands = {"USSR": [ussr_card], "US": [us_card]}
    engine._advance()  # pushes the USSR headline choice


def cards_in_play(engine: Engine) -> Counter:
    """Tally every card by id across every location the engine can hold one.

    Every piece of state that can transiently own a card id must be listed
    here — this is the single source of truth `_assert_invariants` checks
    against, so a new mechanic that introduces a new such location (like
    `_headline_pending` or Our Man in Tehran's peek queue did) only needs
    one edit, not one per test file.
    """
    c: Counter = Counter()
    # HIDDEN_CARD placeholders (physical mode) are not real card ids — skip
    # them here and count `hidden_pool` instead (see below), the "no fixed
    # location yet" bucket for a physical hand's true, unknown contents.
    for cards in engine.hands.values():
        c.update(cid for cid in cards if cid != HIDDEN_CARD)
    c.update(cid for cid in engine.draw_pile if cid != HIDDEN_CARD)
    c.update(engine.discard_pile)
    c.update(engine.removed_cards)
    for cid in engine._headline.values():
        if cid is not None:
            c.update([cid])
    # A headlined card whose event is mid-resolution (its sub-decisions still
    # draining) lives here until it is filed to a pile.
    for _side, cid in engine._headline_pending:
        c.update([cid])
    # Our Man in Tehran's peeked-but-undecided cards live here mid-resolution;
    # they are deliberately excluded from observe() (mandate #4) but must
    # still be accounted for exactly once.
    c.update(engine._our_man_queue)
    c.update(engine._our_man_kept)
    c.update(engine.hidden_pool)
    return c


def expected_in_play(engine: Engine) -> set[str]:
    ids: set[str] = set()
    for period, turn in ENTRY_TURN.items():
        if engine.turn >= turn:
            ids |= set(cards_entering(engine.cards, period, engine.include_optional))
    return ids


def assert_core_invariants(engine: Engine) -> None:
    """The checks that hold for *any* engine, including a bare one that was
    never dealt a deck.

    Split out so the property tests, which drive a bare `Engine(seed=...)`
    through single operations, can share one definition with the full-game
    checker below instead of keeping a near-copy. A near-duplicate invariant
    checker is exactly what once let a real defect hide for weeks (CLAUDE.md),
    and the copy that existed here was silently the weaker of the two.
    """
    assert 1 <= engine.defcon <= 5
    for values in engine.board.influence.values():
        assert values["US"] >= 0 and values["USSR"] >= 0
    if not engine.is_terminal and engine.pending_decision is not None:
        assert len(engine.legal_actions()) > 0  # never deadlock on a live decision


def assert_invariants(engine: Engine) -> None:
    """Everything above, plus what only holds for a real game from
    `Engine.new_game`: a bare engine has no cards, so card conservation and
    "there is always a decision" are not its properties to keep."""
    assert_core_invariants(engine)
    if not engine.is_terminal:
        assert engine.pending_decision is not None

    # No card is ever in two places at once, and The China Card is tracked
    # separately (never in a hand or pile).
    in_play = cards_in_play(engine)
    assert all(count == 1 for count in in_play.values())
    assert RULES["china_card_id"] not in in_play
    assert set(in_play) == expected_in_play(engine)

    if engine.physical_mode:
        placeholder_slots = sum(cards.count(HIDDEN_CARD) for cards in engine.hands.values())
        placeholder_slots += engine.draw_pile.count(HIDDEN_CARD)
        assert placeholder_slots == len(engine.hidden_pool)
        assert HIDDEN_CARD not in engine.discard_pile
        assert HIDDEN_CARD not in engine.removed_cards


def gate_lock_free() -> bool:
    """Whether nothing already holds the gate lock -- i.e. no gate is running.

    A precondition several tests share and none of them used to check. The
    lock tests in `test_gate_script.py` take the lock themselves, non-blocking,
    to simulate a held one; `test_the_checker_does_not_see_itself` asserts
    `gate_pids()` finds nothing. All three are true only on an idle machine,
    and all three failed together on 2026-09-12 with a 128-seed gate live --
    three failures about the machine, reported as failures of the code.

    That matters because it is the normal case, not an exotic one: CLAUDE.md
    says to run the full suite before committing, the queue scripts run gates,
    and a gate takes over an hour.

    The lock is used as the signal DELIBERATELY, rather than `gate_pids()`.
    The checker test exists to catch `gate_pids()` returning a false positive,
    so gating it on `gate_pids()` would turn exactly that defect into a skip.
    An independent signal keeps the test honest.
    """
    import fcntl
    lock = ROOT / 'logs' / 'game-check' / '.lock'
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        with open(lock, 'w') as probe:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(probe, fcntl.LOCK_UN)
        return True
    except (BlockingIOError, OSError):
        return False
