"""Replay fidelity and seat isolation, as explicit contracts.

Five defects found by an external audit, all reproduced before they were
fixed and all pinned here. They shared a cause worth naming: **the suite
tested what the code does, and these are guarantees about what it must
never do.** A default game that cannot replay, and a Decision that
carries a player's hand across a seat boundary, both pass every test
about outcomes.

`frozen=True` on a dataclass protects the fields, not what they point at,
which is how a shared payload dict became a way to edit the engine's
legal moves from a Player's copy of them.
"""
from __future__ import annotations

import pytest

from struggler.engine import DecisionKind as K
from struggler.engine import Engine, Side
from struggler.engine import replay as R
from struggler.engine.types import Action, Decision


def _to_headline(engine: Engine) -> None:
    while engine.pending_decision.kind is not K.HEADLINE_PLAY:
        engine.step(engine.pending_decision.options[0])


# -- 1. a default game's log must replay ------------------------------------

def test_a_default_game_log_replays():
    """The CLI plays with `setup_bonus`, and the log did not record it, so
    every default game's log was unreplayable: the rebuild expected a
    headline while the log was still placing the handicap. It diverged at
    the first action, not at some deep corner."""
    engine = Engine.new_game(seed=42, setup_bonus=True)
    log = {"seed": 42, "new_game": True, "include_optional": True,
           "events": True, "setup_bonus": True, "actions": []}
    assert R.make_engine(log).setup_bonus is True
    # And the reconstruction is at the same decision, not one phase adrift.
    assert R.make_engine(log).pending_decision.kind is engine.pending_decision.kind


def test_the_log_writer_records_setup_bonus(tmp_path):
    engine = Engine.new_game(seed=42, setup_bonus=True)
    writer = R.GameLogWriter(tmp_path / "game.json", engine)
    writer.finalize(winner=None)
    import json
    log = json.loads((tmp_path / "game.json").read_text())
    assert log["setup_bonus"] is True, 'the writer must record what make_engine restores'
    assert R.make_engine(log).setup_bonus is True


def test_logs_written_before_setup_bonus_was_recorded_still_load():
    """Compatibility: a key added to a persisted format has to default."""
    assert R.make_engine({"seed": 42, "new_game": True, "actions": []}).setup_bonus is False


def test_a_default_game_replays_action_for_action():
    """The end-to-end version, which is what actually failed: play a real
    default game, then rebuild it from its own log and require the same
    state."""
    from struggler.bots.strategic import StrategicPlayer
    engine = Engine.new_game(seed=42, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    actions = []
    for _ in range(60):
        if engine.is_terminal:
            break
        decision = engine.pending_decision
        action = (decision.options[0] if decision.actor is Side.CHANCE
                  else bots[decision.actor].choose_action(engine.observe(decision.actor),
                                                          []))
        actions.append(R.encode_action(action))
        engine.step(action)
    log = {"seed": 42, "new_game": True, "include_optional": True, "events": True,
           "setup_bonus": True, "actions": actions}
    rebuilt, _ = R.replay_history(log)
    assert rebuilt.serialize() == engine.serialize(), 'replay diverged from the live game'


# -- 2 & 4. a Decision must not cross a seat boundary with its options ------

def test_a_recorded_event_carries_no_option_list():
    """`history` goes to *both* players. The full Decision carries every
    legal option, which during a headline is the actor's whole hand."""
    engine = Engine.new_game(seed=42, setup_bonus=True)
    _to_headline(engine)
    decision = engine.pending_decision
    actor_hand = set(engine.hands[decision.actor.value])
    assert len(actor_hand) > 1, 'need a real hand for this to mean anything'
    event = R.build_event(decision, decision.options[0], engine)
    leaked = {a.payload.get("card") for a in event.decision.options} & actor_hand
    assert not leaked, f'recorded event exposes the actor still-held cards: {sorted(leaked)}'
    # What is public stays public: who acted, and what they were asked.
    assert event.decision.actor is decision.actor
    assert event.decision.kind is decision.kind
    assert event.action == decision.options[0]


@pytest.mark.xfail(reason="known and deliberate: observe() serves both "
                          "'what a Player may see' and 'the board from this "
                          "seat' for analysis, and expert_check needs the "
                          "second. Closing this needs a separate analysis "
                          "view. No production path reaches the leak.",
                   strict=True)
def test_observing_the_other_seat_hides_the_actor_options():
    engine = Engine.new_game(seed=42, setup_bonus=True)
    _to_headline(engine)
    actor = engine.pending_decision.actor
    assert engine.observe(actor.opponent).pending_decision.options == (), \
        'the non-acting seat can read the actor candidate cards'


def test_the_public_view_keeps_everything_that_is_public():
    decision = Decision(id=7, actor=Side.US, kind=K.HEADLINE_PLAY,
                        options=(Action(K.HEADLINE_PLAY, {"card": "NATO"}),),
                        context={"phase": "headline"})
    public = decision.public()
    assert public.options == ()
    assert (public.id, public.actor, public.kind) == (7, Side.US, K.HEADLINE_PLAY)
    assert public.context == decision.context
    # Idempotent, and free when there is nothing to hide.
    assert public.public() is public


# -- 3. resuming must not reveal a buffered headline ------------------------

def test_resuming_between_headline_picks_does_not_reveal_the_first():
    """Live play buffers both halves of the headline until the second is
    chosen. Resume called `finalize()`, which flushed the unmatched pick
    into the visible history -- so the second player, on a resumed game,
    saw a card the uninterrupted game withholds."""
    engine = Engine.new_game(seed=42, setup_bonus=True)
    actions = []
    while engine.pending_decision.kind is not K.HEADLINE_PLAY:
        action = engine.pending_decision.options[0]
        actions.append(R.encode_action(action))
        engine.step(action)
    first = engine.pending_decision.options[0]
    actions.append(R.encode_action(first))
    engine.step(first)

    log = {"seed": 42, "new_game": True, "include_optional": True, "events": True,
           "setup_bonus": True, "actions": actions}
    _, resumed = R.replay_history(log)
    assert isinstance(resumed, R.HistoryBuilder)
    headlines = [e for e in resumed.history if e.decision.kind is K.HEADLINE_PLAY]
    assert not headlines, (
        'a headline pick became visible on resume that live play buffers')
    # Buffered, not lost: it is held until its partner arrives.
    assert len(resumed._pending_headline) == 1
    # And an uninterrupted game agrees at the same point.
    live = R.HistoryBuilder()
    fresh = Engine.new_game(seed=42, setup_bonus=True)
    for data in actions:
        decision = fresh.pending_decision
        action = R.decode_action(data)
        fresh.step(action)
        live.record(decision, action, fresh)
    assert [e.decision.kind for e in live.history] == \
           [e.decision.kind for e in resumed.history]


# -- 5. an observation must not be a handle on the engine -------------------

def test_an_observed_action_payload_cannot_be_edited():
    engine = Engine.new_game(seed=42, setup_bonus=True)
    observed = engine.observe(engine.pending_decision.actor)
    target = next(a for a in observed.pending_decision.options if "country" in a.payload)
    with pytest.raises(TypeError):
        target.payload["country"] = "INVALID"


def test_editing_an_observation_cannot_change_the_legal_moves():
    """The property that matters, stated without reference to how it is
    enforced: whatever a Player does to what it was handed, the engine's
    legal moves are unchanged."""
    engine = Engine.new_game(seed=42, setup_bonus=True)
    before = engine.legal_actions()
    observed = engine.observe(engine.pending_decision.actor)
    for action in observed.pending_decision.options:
        for key in list(action.payload):
            try:
                action.payload[key] = "INVALID"
            except TypeError:
                pass
    assert engine.legal_actions() == before
