"""The drift canary's verdict over a pooled experiments run.

`.github/workflows/drift.yml` measures each anchor as an anchored arm of
`experiments.yml` (sharded, pooled by scripts/pool_reports.py). This reads
the pooled JSON and applies drift_check.sh's rule: an anchor is DRIFT when
the one-sided 95% upper bound of HEAD's score against it is below 0.500.

Exit status is the verdict, as drift_check.sh's is: 0 no drift, 1 drift
against at least one anchor, 3 an arm with missing shards or no finished
pairs (an incomplete reading is not a clean one).

    python3 scripts/drift_verdict.py pooled.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def verdict(pooled: dict) -> tuple[int, list[str]]:
    lines, status = [], 0
    for slug, arm in sorted(pooled['arms'].items()):
        anchor = (arm.get('meta') or {}).get('anchor') or slug
        if arm.get('missing') or arm.get('score') is None:
            lines.append(f'INCOMPLETE {anchor}: {len(arm.get("missing") or [])} shard(s) missing')
            status = max(status, 3)
            continue
        reading = (f'{anchor}: score {arm["score"]:.3f} [{arm["lower"]:.3f}, {arm["upper"]:.3f}] '
                   f'over {arm["seeds"]} seeds')
        # Short of its plan with nothing missing: a partial shard's lost games.
        # Still a level worth quoting, but never quoted as the full sample --
        # pool_reports says what it was owed (audit 2026-09-25, F2).
        if arm.get('complete') is False:
            reading += f' (SHORT: {arm["seeds"]} of {arm.get("target")} planned)'
        if arm['upper'] < 0.5:
            lines.append(f'DRIFT {reading}')
            status = max(status, 1)
        else:
            lines.append(f'ok    {reading}')
    return status, lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    status, lines = verdict(json.loads(Path(argv[0]).read_text()))
    print('\n'.join(lines))
    return status


if __name__ == '__main__':
    sys.exit(main())
