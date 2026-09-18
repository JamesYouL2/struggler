"""drift.yml's verdict over a pooled experiments run: drift_check.sh's rule
(DRIFT when the one-sided 95% upper bound is below 0.500), and an incomplete
reading reported as one rather than pooled around."""
from conftest import load_script


def arm(score, lower, upper, missing=(), anchor='v0.2.3'):
    return {'score': score, 'lower': lower, 'upper': upper, 'seeds': 1024,
            'missing': list(missing), 'meta': {'anchor': anchor}}


def test_upper_bound_below_half_is_drift_and_level_is_not():
    verdict = load_script('drift_verdict').verdict
    status, lines = verdict({'arms': {'drift-v0.2.3': arm(0.52, 0.50, 0.54),
                                      'drift-v0.2.2': arm(0.47, 0.45, 0.49, anchor='v0.2.2')}})
    assert status == 1
    assert [line.split()[0] for line in lines] == ['DRIFT', 'ok']


def test_no_drift_exits_zero():
    status, _ = load_script('drift_verdict').verdict({'arms': {'a': arm(0.49, 0.47, 0.51)}})
    assert status == 0


def test_a_missing_shard_is_incomplete_not_ok():
    verdict = load_script('drift_verdict').verdict
    status, lines = verdict({'arms': {'a': arm(0.55, 0.53, 0.57, missing=['3']),
                                      'b': {'shards': 0, 'missing': ['0'], 'meta': {}}}})
    assert status == 3
    assert all(line.startswith('INCOMPLETE') for line in lines)
