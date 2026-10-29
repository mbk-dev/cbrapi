"""Allowlisted scanner aggregates. Never copy source, paths or scanner messages."""
import json
from pathlib import Path
import sys


def checkpoint_integer(value, nullable=False, signed=False):
    if value is None:
        return nullable
    return type(value) is int and (-2_147_483_648 if signed else 0) <= value <= 2_147_483_647


def checkpoint_execution(value):
    if not isinstance(value, dict):
        return False
    required = {'status', 'returncode', 'duration_ms'}
    if not required <= set(value) or not set(value) <= required | {'wall_limit_seconds'}:
        return False
    if value['status'] not in ('exited', 'timeout', 'cancelled', 'launch_error'):
        return False
    return (checkpoint_integer(value['returncode'], nullable=True, signed=True)
            and checkpoint_integer(value['duration_ms'])
            and ('wall_limit_seconds' not in value or checkpoint_integer(value['wall_limit_seconds'])))


def checkpoint_scanner(value):
    if not isinstance(value, dict):
        return False
    required = {'status', 'findings', 'errors', 'inputs'}
    if not required <= set(value) or not set(value) <= required | {
            'timeouts', 'known_errors', 'execution', 'report_state'}:
        return False
    if value['status'] not in ('tool_error', 'partial', 'partial_known', 'coverage_gap', 'findings', 'completed'):
        return False
    counters = [checkpoint_integer(value[key], nullable=key in {'inputs', 'findings'})
                for key in ('findings', 'errors', 'inputs')]
    counters += [checkpoint_integer(value[key]) for key in ('timeouts', 'known_errors') if key in value]
    return (all(counters)
            and ('execution' not in value or checkpoint_execution(value['execution']))
            and ('report_state' not in value or value['report_state'] in (
                'json', 'missing', 'invalid_json', 'unreadable', 'unverified_after_cancel')))


def safe_checkpoint(value):
    """Validate progress before copying it from a job summary into public logs."""
    if not isinstance(value, dict) or set(value) != {'version', 'phase', 'state', 'scanners'}:
        return False
    if type(value['version']) is not int or value['version'] != 1:
        return False
    if value['phase'] not in ('bootstrap', 'gitleaks', 'trivy', 'semgrep', 'opengrep'):
        return False
    if value['state'] not in ('started', 'finished', 'cancelled'):
        return False
    scanners = value['scanners']
    return (isinstance(scanners, dict)
            and set(scanners) <= {'gitleaks', 'trivy', 'semgrep', 'opengrep'}
            and all(checkpoint_scanner(row) for row in scanners.values()))


def summarize(tool, payload, code):  # noqa: C901 - One allowlisted dispatcher keeps scanner schemas separate and never copies raw fields.
    error = {'status': 'tool_error', 'findings': None, 'errors': 1, 'inputs': None}
    if type(code) is not int or code not in ({0, 10} if tool == 'gitleaks' else {0}):
        return error
    try:
        if tool == 'gitleaks':
            if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
                return error
            count, errors, inputs = len(payload), 0, None
            if (code == 10) != bool(count):
                return error
        elif tool in {'semgrep', 'opengrep'}:
            rows, failures, paths = payload['results'], payload['errors'], payload['paths']['scanned']
            if not all(isinstance(x, list) for x in (rows, failures, paths)):
                return error
            fixpoint_timeouts = payload.get('time', {}).get('fixpoint_timeouts', [])
            if not isinstance(fixpoint_timeouts, list):
                return error
            count, errors, inputs = len(rows), len(failures) + len(fixpoint_timeouts), len(paths)
        elif tool == 'trivy':
            if payload['SchemaVersion'] != 2:
                return error
            rows = payload.get('Results')
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                return error
            packages = [r.get('Packages') if r.get('Packages') is not None else [] for r in rows]
            vulnerabilities = [r.get('Vulnerabilities') if r.get('Vulnerabilities') is not None else [] for r in rows]
            if not all(isinstance(x, list) for x in packages + vulnerabilities):
                return error
            inputs = sum(map(len, packages))
            count, errors = sum(map(len, vulnerabilities)), 0
        else:
            return error
    except (KeyError, TypeError, AttributeError):
        return error
    status = 'partial' if errors else 'coverage_gap' if inputs == 0 else 'findings' if count else 'completed'
    result = {'status': status, 'findings': None if inputs == 0 else count, 'errors': errors, 'inputs': inputs}
    if tool in {'semgrep', 'opengrep'}:
        result['timeouts'] = len(fixpoint_timeouts)
    return result


if __name__ == '__main__':
    try:
        payload = json.loads(Path(sys.argv[2]).read_text())
    except (ValueError, OSError):
        payload = None
    result = summarize(sys.argv[1], payload, int(sys.argv[3]))
    print(json.dumps(result, sort_keys=True))
    sys.exit(1 if result['status'] in ('tool_error', 'partial') else 0)
