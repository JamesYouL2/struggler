"""Central "resolve path under data/, open, json.load" helper (mandate #5):
every module that reads a data/*.json file routes through here instead of
each hand-rolling its own Path(__file__).resolve()... + open() + json.load().
"""

from __future__ import annotations

import copy
import functools
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@functools.lru_cache(maxsize=None)
def _parse(filename: str) -> dict:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json(filename: str) -> dict:
    """Load and parse `filename` from struggler/data/.

    The files are static, so the parse is cached; callers get their own deep
    copy and may mutate it freely."""
    return copy.deepcopy(_parse(filename))
