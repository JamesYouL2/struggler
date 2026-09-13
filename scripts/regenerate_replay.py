#!/usr/bin/env python
"""Rebuild a golden replay log whose recorded actions no longer replay.

Golden logs under `tests/replays/` are read-only fixtures: `seed` plus
`actions` reproduces a game byte for byte, and `checkpoints` pins
`engine.serialize()` at chosen steps. That works until the *rules* change
under them. A recorded action that is no longer legal -- a country removed
from the map, a play mode withdrawn -- makes the whole log unreplayable
from that point, and there is then nothing to regenerate it with.

This is that something. It keeps the log's start descriptor (seed, and
whether events, optional cards or physical mode are on) and drives a fresh
game from it, choosing among `legal_actions()` with a seeded RNG so the
result is reproducible from this script alone. Checkpoints land at quarters
plus the final step.

Prefer `--repair`, which keeps every recorded action that is still legal and
only drives from the first one that is not: a log regenerated that way still
exercises most of the sequence it was built to exercise.

    python scripts/regenerate_replay.py tests/replays/full_game_ops_only.json --repair

Regenerating a golden throws away the evidence it was holding, so do it only
when the log genuinely cannot replay, say so in the commit message, and
check that whatever the log existed to cover is still covered (there are
tests that assert a golden still fires events, for instance).
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from struggler.engine.replay import decode_action, make_engine


def _matches(action, options) -> bool:
    return any(o.kind == action.kind and o.payload == action.payload for o in options)


def rebuild(log: dict, *, repair: bool, driver_seed: int, limit: int = 5000) -> dict:
    """Return a new log: the same start descriptor, a replayable action list,
    and checkpoints at quarters plus the end."""
    engine = make_engine(log)
    rng = random.Random(driver_seed)
    recorded = [decode_action(a) for a in log.get("actions", [])] if repair else []
    actions, kept = [], 0

    for index in range(limit):
        if engine.is_terminal or engine.pending_decision is None:
            break
        options = engine.legal_actions()
        if not options:
            break
        action = None
        if index < len(recorded) and _matches(recorded[index], options):
            action = recorded[index]
            kept += 1
        else:
            action = rng.choice(options)
        engine.step(action)
        actions.append({"kind": action.kind.value, "payload": action.payload})

    total = len(actions)
    marks = sorted({max(1, total // 4), max(1, total // 2), max(1, 3 * total // 4), total})
    out = {k: v for k, v in log.items() if k not in ("actions", "checkpoints")}
    out["actions"] = actions

    # Replay what we just built to capture the checkpoints, so they are
    # produced by the same path the test will use rather than by this loop.
    engine = make_engine(out)
    checkpoints = []
    for step, entry in enumerate(actions, start=1):
        engine.step(decode_action(entry))
        if step in marks:
            checkpoints.append({"after_step": step, "state": engine.serialize()})
    out["checkpoints"] = checkpoints
    out["_kept_recorded_actions"] = kept
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="the golden log to rebuild, in place")
    parser.add_argument("--repair", action="store_true",
                        help="keep recorded actions that are still legal (recommended)")
    parser.add_argument("--driver-seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = parser.parse_args(argv)

    logging.disable(logging.CRITICAL)
    path = Path(args.path)
    raw = path.read_text(encoding="utf-8")
    log = json.loads(raw)
    out = rebuild(log, repair=args.repair, driver_seed=args.driver_seed)
    kept = out.pop("_kept_recorded_actions")
    print(f"{path.name}: {len(log.get('actions', []))} recorded actions -> "
          f"{len(out['actions'])}, {kept} kept; "
          f"checkpoints at {[c['after_step'] for c in out['checkpoints']]}")
    if args.dry_run:
        return 0
    indent = 2 if raw.startswith('{\n  "') else None
    path.write_text(json.dumps(out, indent=indent) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
