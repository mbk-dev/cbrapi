"""Allowlisted scanner aggregates. Never copy source, paths or scanner messages."""
import json
from pathlib import Path
import sys


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
        elif tool == 'semgrep':
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
    if tool == 'semgrep':
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
