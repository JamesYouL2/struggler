"""`experiments.yml` and the composite action it runs shards with.

Workflows are the part of this repo the test suite has historically not
looked at, and the part whose mistakes cost the most: they surface on a
dispatched runner an hour later, or -- worse -- they do not surface at all
and a pooled table prints a number that was measured differently from how
it says it was. `tests/test_experiment_registry.py` covers the arms;
this covers the machinery that runs them.

Four properties, each one a specific way the shard cache or the wave split
can go quietly wrong.
"""
from __future__ import annotations

from pathlib import Path

import yaml   # a hard test dependency: a gate that can skip is not a gate

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'experiments.yml'
ACTION = ROOT / '.github' / 'actions' / 'run-shard' / 'action.yml'


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _steps(path: Path) -> list[dict]:
    doc = _load(path)
    if 'runs' in doc:
        return doc['runs']['steps']
    return [s for job in doc['jobs'].values() for s in job.get('steps', [])]


def test_the_shard_is_played_in_one_place_only():
    """`run` and `run2` play shards the same way because they run the SAME
    composite action. A second copy of the benchmark invocation is the bug
    shape this repo has been bitten by most -- a rule written down twice --
    and here the second copy would only ever run in wave 2, on arms the
    interim did not settle, which is the half nobody watches."""
    body = WORKFLOW.read_text()
    assert 'struggler.bots.benchmark' not in body, (
        'the benchmark belongs in .github/actions/run-shard, not inlined in a job')
    jobs = _load(WORKFLOW)['jobs']
    for name in ('run', 'run2'):
        uses = [s.get('uses') for s in jobs[name]['steps']]
        assert './.github/actions/run-shard' in uses, f'{name} must run shards through the action'
    assert ACTION.read_text().count('struggler.bots.benchmark') == 1


def test_arm_metadata_is_written_outside_the_benchmark_step():
    """`pool_reports.py` reads `arm.json` for the arm's `compare_to` and its
    anchor, so a shard restored from cache -- which skips the benchmark --
    still has to write it. Folding it back into the benchmark step would
    leave every cached run without its PAIRED readings, and the pooled table
    would simply print one fewer section rather than failing."""
    steps = _steps(ACTION)
    writes = [i for i, s in enumerate(steps) if 'arm.json' in (s.get('run') or '')]
    assert writes, 'nothing writes arm.json'
    plays = [i for i, s in enumerate(steps) if 'struggler.bots.benchmark' in (s.get('run') or '')]
    for i in writes:
        assert not steps[i].get('if'), 'arm.json must be written unconditionally'
        assert all(i < j for j in plays), 'arm.json must be written before the benchmark'


def test_a_failed_or_stalled_shard_is_never_cached():
    """A stall is exit 6: the report is still written, over the seeds that
    finished. Caching that partial reading would serve it for this shard
    forever, and nothing downstream could tell it from a complete one."""
    for step in _steps(ACTION):
        if (step.get('uses') or '').startswith('actions/cache/save'):
            condition = step.get('if') or ''
            assert 'success()' in condition, (
                'the cache save must be guarded on success(): a stalled shard '
                'writes a PARTIAL report and exits 6')
            assert 'always()' not in condition


def test_the_cache_never_falls_back_to_a_prefix():
    """`restore-keys` would serve a DIFFERENT shard's report under this
    shard's name. That is the one failure mode worse than no cache at all,
    and it is a one-line addition away at all times."""
    for step in _steps(ACTION):
        if (step.get('uses') or '').startswith('actions/cache'):
            assert 'restore-keys' not in (step.get('with') or {}), (
                'an experiment shard must match its key exactly or replay')


def test_the_drift_canary_does_not_take_waves():
    """A drift arm is a LEVEL and its number is quoted; an experiment arm is
    a COMPARISON and stops when the comparison is decided. Halving a
    canary's seeds doubles the interval that gets written into a note."""
    measure = _load(ROOT / '.github' / 'workflows' / 'drift.yml')['jobs']['measure']
    assert measure['with']['waves'] is False
