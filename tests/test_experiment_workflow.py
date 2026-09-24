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

import re
from pathlib import Path

import pytest
import yaml   # a hard test dependency: a gate that can skip is not a gate

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'experiments.yml'
ACTION = ROOT / '.github' / 'actions' / 'run-shard' / 'action.yml'


class _NoDuplicates(yaml.SafeLoader):
    """A loader that refuses a repeated mapping key.

    PyYAML's default keeps the LAST of a duplicate pair and says nothing.
    GitHub does not: it refuses the whole file with "'env' is already
    defined" and the job never runs. So a workflow can parse perfectly here,
    pass every assertion in this file, and be rejected on the runner -- which
    is exactly what happened on 2026-09-21, when a second `env:` was added to
    the benchmark step and the smoke dispatch died with "Failed to load
    action.yml". These tests read the files; they have to read them the way
    the runner does.
    """


def _no_duplicate_keys(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise AssertionError(
                f'{key!r} is defined twice in the same mapping at '
                f'line {key_node.start_mark.line + 1}: PyYAML would keep the '
                f'last silently and GitHub refuses the file outright')
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_NoDuplicates.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=_NoDuplicates)


def _steps(path: Path) -> list[dict]:
    doc = _load(path)
    if 'runs' in doc:
        return doc['runs']['steps']
    return [s for job in doc['jobs'].values() for s in job.get('steps', [])]


def test_the_shard_cut_is_one_rule_in_shard_plan():
    """`experiments.yml`'s plan step cuts shards by asking
    `scripts/shard_plan.py` -- the module the registry test checks reserve
    space with. A second spelling of the cut inside the workflow would
    drift from the tests' and only ever be exercised on a runner."""
    body = WORKFLOW.read_text()
    assert 'import shard_plan' in body
    assert 'shard_plan.cut' in body
    assert 'shard_plan.assert_disjoint' in body


def test_the_shard_hands_its_reserve_to_the_benchmark():
    action = ACTION.read_text()
    assert action.count('--reserve-seeds') == 1, (
        'the reserve reaches the benchmark exactly once')
    assert 'RESERVE: ${{ fromJSON(inputs.shard).reserve }}' in action


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


def test_the_benchmarks_own_ceiling_fires_before_the_runners():
    """The two timeouts do different things and the ORDER is the whole point.

    A job timeout kills the process, so nothing is written and the shard
    yields nothing -- `fit-bc-base [5/8]` twice. `--max-seconds` fires first,
    abandons what is running, writes the partial report and names the
    abandoned seeds. If someone raises `--max-seconds` or lowers
    `timeout-minutes` past each other the flag becomes decoration, silently,
    and the next unmeasurable slice looks like the last one.
    """
    body = ACTION.read_text()
    match = re.search(r'--max-seconds (\d+)', body)
    assert match, 'the shard action no longer passes --max-seconds'
    cap = int(match.group(1))
    jobs = _load(WORKFLOW)['jobs']
    for name in ('run', 'run2'):
        job_timeout = jobs[name]['timeout-minutes'] * 60
        assert cap < job_timeout, (
            f'{name}: --max-seconds {cap}s is not below timeout-minutes '
            f'{job_timeout}s, so the runner kills the benchmark before it can '
            f'write a partial report')
        assert job_timeout - cap >= 600, (
            f'{name}: only {job_timeout - cap}s between the benchmark ceiling '
            f'and the job timeout -- not enough for the report, the log and '
            f'the artifact upload')


def test_a_shard_that_did_not_finish_still_prints_what_it_was_doing():
    """A killed step is otherwise a blank one: the `tail -15` closing the
    benchmark pipeline never runs, and the artifact holding the log is not
    downloadable from every environment. So the log is teed to a file and the
    tail printed by a step that runs on a cancel."""
    steps = _steps(ACTION)
    bench = [s for s in steps if 'struggler.bots.benchmark' in (s.get('run') or '')]
    assert len(bench) == 1 and 'tee benchmark.log' in bench[0]['run'], (
        'the benchmark output must be teed to a file, not only piped to tail')
    printers = [s for s in steps
                if 'benchmark.log' in (s.get('run') or '')
                and 'struggler.bots.benchmark' not in (s.get('run') or '')]
    assert printers, 'nothing prints benchmark.log when the shard fails'
    assert any('always()' in (s.get('if') or '') for s in printers), (
        'the step printing the log must run on a cancel, so it needs always()')


def test_the_log_is_uploaded_with_the_report():
    for job in ('run', 'run2'):
        steps = _load(WORKFLOW)['jobs'][job]['steps']
        uploads = [s for s in steps if (s.get('uses') or '').startswith('actions/upload-artifact')]
        assert uploads, f'{job} uploads nothing'
        assert all('benchmark.log' in (s.get('with') or {}).get('path', '') for s in uploads), (
            f'{job}: benchmark.log is not in the uploaded paths')


def test_the_interim_look_cannot_abort_its_own_step():
    """A total wave-1 failure must not cancel wave 2.

    On 2026-09-21 it did: every wave-1 shard failed, `pool_reports.py` exited
    2 with "no shard reports found", `set -e` killed the step before
    `wave_verdict.py` could apply its fail-open rule, and `run2` was skipped
    for want of a successful `interim`. The guard was in the script and the
    script never ran, which is the worst place for a guard to be."""
    look = [s for s in _load(WORKFLOW)['jobs']['interim']['steps']
            if s.get('id') == 'look']
    assert look, 'the interim job no longer has a `look` step'
    run = look[0]['run']
    # The `set` COMMANDS, not the word in a comment -- the comment above the
    # step says "set -e killed the step", and matching that would make this
    # test pass or fail on prose.
    flags = [line.split()[1] for line in run.splitlines()
             if line.strip().startswith('set -')]
    assert flags, 'the look sets no shell flags at all'
    assert not any('e' in f for f in flags), (
        f'the look must not abort on a failing command: every stage degrades, '
        f'and these flags include -e: {flags}')
    assert 'cp wave2.json next.json' in run, (
        'nothing falls back to the full wave 2 when the verdict script fails')


def test_wave_two_falls_back_to_the_full_plan_when_the_look_did_not_succeed():
    """Fail-open at the job level. The step degrades rather than failing, but
    a lost runner would still leave `run2` with nothing to read -- and
    skipping it reports half an arm's seeds as a whole arm."""
    run2 = _load(WORKFLOW)['jobs']['run2']
    condition = ' '.join(run2['if'].split())
    assert "needs.interim.result != 'success'" in condition, (
        'an interim that did not succeed must still play wave 2')
    matrix = run2['strategy']['matrix']['s']
    assert 'needs.plan.outputs.wave2' in matrix, (
        "the matrix must fall back to plan's full wave 2, not to an empty list")


@pytest.mark.parametrize('path', [
    *sorted((ROOT / '.github' / 'workflows').glob('*.yml')), ACTION])
def test_no_workflow_repeats_a_mapping_key(path):
    """Every workflow and the composite action, read the strict way.

    Parametrised over the directory rather than a list, so a workflow added
    later is covered without anyone remembering to add it here."""
    _load(path)


def test_the_drift_canary_does_not_take_waves():
    """A drift arm is a LEVEL and its number is quoted; an experiment arm is
    a COMPARISON and stops when the comparison is decided. Halving a
    canary's seeds doubles the interval that gets written into a note."""
    measure = _load(ROOT / '.github' / 'workflows' / 'drift.yml')['jobs']['measure']
    assert measure['with']['waves'] is False


def test_a_cancel_never_launches_wave_two():
    """A cancelled run must stay cancelled.

    `interim` and `run2` fail open -- a crashed wave-1 shard is a reason to
    PLAY wave 2 -- and they used `always()` to do it. `always()` also runs
    after a CANCEL: the cancel killed wave 1, `interim` read the empty
    artifacts, failed open, and `run2` played the whole second wave. That
    happened twice before this test existed: the 2026-09-22 hold-option
    "orphan" (run 35752606270) and the 2026-09-23 headline run 35857931995,
    eight shards for twenty minutes after the cancel, on a variant already
    known to be wrong. `!cancelled()` keeps the fail-open on failures and
    honours the cancel.
    """
    jobs = _load(WORKFLOW)['jobs']
    for name in ('interim', 'run2'):
        condition = ' '.join(str(jobs[name].get('if') or '').split())
        assert 'always()' not in condition, (
            f'{name} runs after a cancel with always(); use !cancelled()')
        assert condition.startswith('!cancelled()'), (
            f'{name} must keep failing open on a crashed shard: !cancelled(), '
            f'not success(), is the condition that does both')
