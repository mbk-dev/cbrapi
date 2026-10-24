"""Explicitly reviewed parser gaps, bound to source bytes and scanner/rule pins."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from collections import Counter


def error_identity(error, root, policy):
    try:
        kind = error['type']
        kind = kind[0] if isinstance(kind, list) and kind else kind
        if kind not in {'PartialParsing', 'Syntax error', 'Other syntax error'} or type(error['code']) is not int or error['code'] not in {2, 3}:
            return None
        root = root.resolve()
        source = Path(error['path'])
        source = (root / source).resolve()
        if not source.is_relative_to(root) or not source.is_file() or source.stat().st_size > 2_000_000:
            return None
        positions = []
        spans = error.get('spans', [])
        if not isinstance(spans, list):
            return None
        for span in spans:
            position = {}
            for boundary in ('start', 'end'):
                coordinates = span[boundary]
                if not all(type(coordinates.get(k)) is int and coordinates[k] >= 0 for k in ('line', 'col')):
                    return None
                position[boundary] = {k: coordinates[k] for k in ('line', 'col')}
            positions.append(position)
        record = {'path': str(source.relative_to(root)), 'file_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'code': error['code'], 'type': kind, 'rule_id': error.get('rule_id'), 'positions': positions,
                      'semgrep_version': policy['semgrep_version'], 'rules_sha256': policy['rules_sha256']}
        return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    except (KeyError, TypeError, ValueError, OSError):
        return None


def apply_known_gaps(summary, payload, policy, root):
    result = dict(summary, known_errors=0)
    if summary['status'] != 'partial' or not isinstance(payload, dict):
        return result
    errors = payload.get('errors')
    if not isinstance(errors, list) or len(errors) != summary['errors']:
        return result
    accepted = Counter(policy['accepted_parser_errors'])
    for error in errors:
        identity = error_identity(error, root, policy)
        if identity is not None and accepted[identity] > 0:
            result['known_errors'] += 1
            accepted[identity] -= 1
    if errors and result['known_errors'] == len(errors) and type(summary['inputs']) is int and summary['inputs'] > 0:
        result['status'] = 'partial_known'
    return result


def validate_policy(data, pins):
    semgrep = next(p['version'] for p in pins if p['tool'] == 'semgrep')
    rules = next(p['sha256'] for p in pins if p['tool'] == 'semgrep-rules')
    default = {'version': 1, 'semgrep_version': semgrep, 'rules_sha256': rules, 'accepted_parser_errors': []}
    if data is None:
        return default
    if (not isinstance(data, dict) or set(data) != set(default) or type(data['version']) is not int
            or data['version'] != 1 or data['semgrep_version'] != semgrep or data['rules_sha256'] != rules):
        raise ValueError('baseline_binding')
    if not isinstance(data['accepted_parser_errors'], list) or len(data['accepted_parser_errors']) > 5000:
        raise ValueError('baseline_ids')
    if not all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in data['accepted_parser_errors']):
        raise ValueError('baseline_ids')
    return data


def load_policy(path, pins):
    if not path.exists():
        return validate_policy(None, pins)
    if path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError('baseline_file')
    return validate_policy(json.loads(path.read_text()), pins)


def load_source_policy(root, base_sha, pins):
    if not base_sha:
        return load_policy(root / '.security-ci-baseline.json', pins)
    if not re.fullmatch('[0-9a-f]{40}', base_sha):
        raise ValueError('baseline_base_sha')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, timeout=10)
    git('cat-file', '-e', base_sha + '^{commit}')
    entries = git('ls-tree', '-z', base_sha, '--', '.security-ci-baseline.json').split(b'\0')
    entries = [entry for entry in entries if entry]
    if not entries:
        return validate_policy(None, pins)
    if len(entries) != 1:
        raise ValueError('baseline_tree')
    prefix, name = entries[0].split(b'\t', 1)
    mode, kind, oid = prefix.split()
    if mode not in {b'100644', b'100755'} or kind != b'blob' or name != b'.security-ci-baseline.json':
        raise ValueError('baseline_tree')
    oid = oid.decode('ascii')
    size = int(git('cat-file', '-s', oid))
    if not 0 <= size <= 1_000_000:
        raise ValueError('baseline_size')
    payload = git('cat-file', 'blob', oid)
    if len(payload) != size:
        raise ValueError('baseline_size')
    return validate_policy(json.loads(payload), pins)
