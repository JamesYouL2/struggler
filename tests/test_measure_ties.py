"""`scripts/measure_ties.py` counts LIVE decisions only.

Codex audit 2026-09-25, F3: the first version patched `rank_actions` and
`safety_key` onto the StrategicPlayer class, so the event helpers -- which
are StrategicPlayers -- recorded every SIMULATED decision as a live one,
and a module-level counter carried one game's counts into the next on the
same worker. The classification itself is `benchmark.event_choice_kind`
(tested in test_benchmark.py); what is pinned here is the shape that made
the old counts wrong.
"""
from __future__ import annotations

from conftest import load_script
from struggler.bots.strategic import StrategicPlayer


def test_importing_the_instrument_patches_nothing():
    rank, key = StrategicPlayer.rank_actions, StrategicPlayer.safety_key
    load_script('measure_ties')
    assert StrategicPlayer.rank_actions is rank
    assert StrategicPlayer.safety_key is key


def test_the_counts_are_per_game_not_per_worker():
    script = load_script('measure_ties')
    assert not any(isinstance(v, dict) and not callable(v) and name.isupper()
                   for name, v in vars(script).items()), 'a module-level counter is back'
