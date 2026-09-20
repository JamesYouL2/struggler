#!/usr/bin/env python
"""Recompute `models/provenance.json`'s `_summary` counts from the entries.

The counts were hand-patched four times and were wrong three of them: a
ledger whose totals are maintained separately from its rows is two copies of
the same fact (bug shape 3's cousin). Run this after adding, removing or
retyping any entry; `tests/test_provenance.py` checks the result.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

LEDGER = pathlib.Path(__file__).resolve().parents[1] / 'models' / 'provenance.json'
SECTIONS = ('StrategicWeights', 'SurvivalPrior', 'constants')


def entries(doc: dict) -> list[dict]:
    """Every row in the ledger, across all three sections."""
    return [row for section in SECTIONS for row in doc[section].values()]


def counts(doc: dict) -> dict:
    """The `_summary` block the ledger's rows imply."""
    rows = entries(doc)
    by_source = collections.Counter(row['source'] for row in rows)
    by_determination = collections.Counter(row['determination'] for row in rows)
    return {
        'total': len(rows),
        'counts_by_source': dict(by_source),
        'counts_by_determination': dict(by_determination),
    }


def main(argv: list[str]) -> int:
    check = '--check' in argv
    doc = json.loads(LEDGER.read_text())
    want = counts(doc)
    summary = doc['_summary']
    have = {k: summary.get(k) for k in want}
    if have == want:
        print(f'provenance _summary is correct ({want["total"]} entries)')
        return 0
    if check:
        print('provenance _summary is stale:', file=sys.stderr)
        for key in want:
            if have[key] != want[key]:
                print(f'  {key}: recorded {have[key]!r}, entries say {want[key]!r}', file=sys.stderr)
        print(f'run: uv run python {pathlib.Path(__file__).name}', file=sys.stderr)
        return 1
    summary.update(want)
    LEDGER.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    print(f'provenance _summary rewritten from {want["total"]} entries: {want}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
