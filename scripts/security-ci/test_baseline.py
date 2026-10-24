import importlib.util
import json
import subprocess
from pathlib import Path
import tempfile
import unittest


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('baseline', Path(__file__).with_name('baseline.py'))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'script.sh').write_text('echo hello\n')
        self.policy = {'semgrep_version': '1.182.0', 'rules_sha256': 'a' * 64, 'accepted_parser_errors': []}
        self.error = {'code': 3, 'type': 'PartialParsing', 'path': str(self.root / 'script.sh')}
        self.summary = {'status': 'partial', 'findings': 2, 'errors': 1, 'inputs': 1}

    def test_known_gap_remains_partial_and_keeps_findings(self):
        identity = self.module.error_identity(self.error, self.root, self.policy)
        self.policy['accepted_parser_errors'] = [identity]
        result = self.module.apply_known_gaps(self.summary, {'errors': [self.error]}, self.policy, self.root)
        self.assertEqual(result, {'status': 'partial_known', 'findings': 2, 'errors': 1, 'inputs': 1, 'known_errors': 1})

    def test_changed_source_cannot_reuse_previous_acceptance(self):
        self.policy['accepted_parser_errors'] = [self.module.error_identity(self.error, self.root, self.policy)]
        (self.root / 'script.sh').write_text('echo changed\n')
        result = self.module.apply_known_gaps(self.summary, {'errors': [self.error]}, self.policy, self.root)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['known_errors'], 0)

    def test_timeout_is_never_an_accepted_parser_gap(self):
        self.error['type'] = 'Timeout'
        self.assertIsNone(self.module.error_identity(self.error, self.root, self.policy))

    def test_outside_path_is_not_accepted(self):
        self.error['path'] = str(self.root / '..' / 'outside.sh')
        self.assertIsNone(self.module.error_identity(self.error, self.root, self.policy))

    def test_new_error_keeps_partial_failure(self):
        self.policy['accepted_parser_errors'] = [self.module.error_identity(self.error, self.root, self.policy)]
        unknown = dict(self.error, type='Syntax error')
        result = self.module.apply_known_gaps(dict(self.summary, errors=2), {'errors': [self.error, unknown]}, self.policy, self.root)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['known_errors'], 1)

    def test_zero_scanned_inputs_cannot_be_accepted(self):
        self.policy['accepted_parser_errors'] = [self.module.error_identity(self.error, self.root, self.policy)]
        result = self.module.apply_known_gaps(dict(self.summary, inputs=0), {'errors': [self.error]}, self.policy, self.root)
        self.assertEqual(result['status'], 'partial')

    def test_changed_rule_pin_invalidates_policy(self):
        data = dict(self.policy, version=1)
        path = self.root / 'policy.json'
        path.write_text(json.dumps(data))
        pins = [{'tool': 'semgrep', 'version': '1.182.0'}, {'tool': 'semgrep-rules', 'sha256': 'b' * 64}]
        with self.assertRaises(ValueError):
            self.module.load_policy(path, pins)

    def test_arbitrary_text_is_not_a_baseline_identity(self):
        path = self.root / 'policy.json'
        path.write_text(json.dumps(dict(self.policy, version=1, accepted_parser_errors=['private source text'])))
        pins = [{'tool': 'semgrep', 'version': '1.182.0'}, {'tool': 'semgrep-rules', 'sha256': 'a' * 64}]
        with self.assertRaises(ValueError):
            self.module.load_policy(path, pins)

    def test_second_identical_error_requires_second_reviewed_record(self):
        self.policy['accepted_parser_errors'] = [self.module.error_identity(self.error, self.root, self.policy)]
        result = self.module.apply_known_gaps(dict(self.summary, errors=2), {'errors': [self.error, self.error]}, self.policy, self.root)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['known_errors'], 1)

    def test_different_error_location_is_not_accepted(self):
        self.error['spans'] = [{'start': {'line': 1, 'col': 1}, 'end': {'line': 1, 'col': 2}}]
        self.policy['accepted_parser_errors'] = [self.module.error_identity(self.error, self.root, self.policy)]
        changed = dict(self.error, spans=[{'start': {'line': 2, 'col': 1}, 'end': {'line': 2, 'col': 2}}])
        result = self.module.apply_known_gaps(self.summary, {'errors': [changed]}, self.policy, self.root)
        self.assertEqual(result['status'], 'partial')

    def test_pull_request_cannot_expand_its_own_policy(self):
        path = self.root / '.security-ci-baseline.json'
        base = dict(self.policy, version=1, accepted_parser_errors=['b' * 64])
        path.write_text(json.dumps(base))
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.root), '-c', 'core.hooksPath=/dev/null',
                                            '-c', 'commit.gpgSign=false', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args], stderr=subprocess.DEVNULL).decode().strip()
        git('init', '-q')
        git('add', '.security-ci-baseline.json')
        git('commit', '-qm', 'baseline fixture')
        sha = git('rev-parse', 'HEAD')
        path.write_text(json.dumps(dict(base, accepted_parser_errors=['c' * 64])))
        pins = [{'tool': 'semgrep', 'version': '1.182.0'}, {'tool': 'semgrep-rules', 'sha256': 'a' * 64}]
        result = self.module.load_source_policy(self.root, sha, pins)
        self.assertEqual(result['accepted_parser_errors'], ['b' * 64])


if __name__ == '__main__':
    unittest.main()
