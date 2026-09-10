"""Property-based invariants that must hold after every step()."""

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import assert_core_invariants
from struggler.engine import Engine, Side

MAX_INT32 = 2**31 - 1


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=MAX_INT32),
    ops=st.integers(min_value=1, max_value=6),
    driver_seed=st.integers(min_value=0, max_value=MAX_INT32),
    operation=st.sampled_from(["influence", "coup", "realignment"]),
    side=st.sampled_from([Side.US, Side.USSR]),
)
def test_random_legal_sequences_keep_state_valid(seed, ops, driver_seed, operation, side):
    engine = Engine(seed=seed)
    if operation == "influence":
        engine.begin_influence_operations(side, ops)
    elif operation == "coup":
        engine.begin_coup(side, ops)
    else:
        engine.begin_realignment_operations(side, ops)

    driver = random.Random(driver_seed)
    steps = 0
    while engine.pending_decision is not None and steps < 100:
        options = engine.legal_actions()
        assert len(options) > 0
        engine.step(driver.choice(options))
        assert_core_invariants(engine)
        steps += 1


@settings(max_examples=15, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=MAX_INT32),
    driver_seed=st.integers(min_value=0, max_value=MAX_INT32),
)
def test_serialize_deserialize_round_trips_after_every_step(seed, driver_seed):
    engine = Engine(seed=seed)
    engine.begin_realignment_operations(Side.US, ops=3)
    driver = random.Random(driver_seed)
    steps = 0
    while engine.pending_decision is not None and steps < 30:
        action = driver.choice(engine.legal_actions())
        engine.step(action)
        data = engine.serialize()
        assert Engine.deserialize(data).serialize() == data
        steps += 1
