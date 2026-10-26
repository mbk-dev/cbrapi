"""Engine selection is explicit and parser acceptance stays engine-bound."""
import json
from pathlib import Path
import tempfile
import unittest

import baseline
import summary


class EnginePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'source.py').write_text('x = 1\n')
        self.pins = [{'tool': 'semgrep', 'version': '1.182.0'},
                     {'tool': 'opengrep', 'version': '1.32.0'},
                     {'tool': 'semgrep-rules', 'sha256': 'a' * 64}]
        self.policy = {'version': 2, 'engine': 'opengrep', 'engine_version': '1.32.0',
                       'rules_sha256': 'a' * 64, 'accepted_parser_errors': []}
        self.path = self.root / '.security-ci-baseline.json'
        self.path.write_text(json.dumps(self.policy))
        self.error = {'code': 3, 'type': 'PartialParsing', 'path': 'source.py'}

    def test_opengrep_policy_is_bound_to_explicit_selected_engine(self):
        self.assertEqual(baseline.load_policy(self.path, self.pins, engine='opengrep'), self.policy)
        with self.assertRaises(ValueError):
            baseline.load_policy(self.path, self.pins)

    def test_wrong_opengrep_version_is_rejected(self):
        self.path.write_text(json.dumps(dict(self.policy, engine_version='1.31.0')))
        with self.assertRaises(ValueError):
            baseline.load_policy(self.path, self.pins, engine='opengrep')

    def test_semgrep_acceptance_cannot_be_reused_by_opengrep(self):
        old = {'version': 1, 'semgrep_version': '1.182.0', 'rules_sha256': 'a' * 64,
               'accepted_parser_errors': []}
        self.path.write_text(json.dumps(old))
        with self.assertRaises(ValueError):
            baseline.load_policy(self.path, self.pins, engine='opengrep')
        self.assertEqual(baseline.load_policy(self.path, self.pins), old)

    def test_error_identity_changes_with_engine_and_source(self):
        identity = baseline.error_identity(self.error, self.root, self.policy)
        self.assertIsNotNone(identity)
        changed = dict(self.policy, engine='semgrep', engine_version='1.182.0')
        self.assertNotEqual(identity, baseline.error_identity(self.error, self.root, changed))
        (self.root / 'source.py').write_text('x = 2\n')
        self.assertNotEqual(identity, baseline.error_identity(self.error, self.root, self.policy))

    def test_opengrep_timeout_is_counted_and_keeps_failure(self):
        payload = {'results': [], 'errors': [self.error], 'paths': {'scanned': ['source.py']},
                   'time': {'fixpoint_timeouts': [{'untrusted': 'not-public'}]}}
        result = summary.summarize('opengrep', payload, 0)
        self.assertEqual((result['status'], result['errors'], result['timeouts']), ('partial', 2, 1))
        self.policy['accepted_parser_errors'] = [baseline.error_identity(self.error, self.root, self.policy)]
        result = baseline.apply_known_gaps(result, payload, self.policy, self.root)
        self.assertEqual(result['known_errors'], 1)
        self.assertEqual(result['status'], 'partial')
        self.assertNotIn('not-public', json.dumps(result))

    def test_new_policy_rejects_unbound_extra_fields(self):
        self.path.write_text(json.dumps(dict(self.policy, allow_timeouts=True)))
        with self.assertRaises(ValueError):
            baseline.load_policy(self.path, self.pins, engine='opengrep')

    def test_empty_opengrep_policy_does_not_inherit_semgrep_acceptance(self):
        self.path.unlink()
        result = baseline.load_policy(self.path, self.pins, engine='opengrep')
        self.assertEqual(result, self.policy)

    def test_unknown_engine_is_rejected(self):
        with self.assertRaises(ValueError):
            baseline.load_policy(self.path, self.pins, engine='other')


if __name__ == '__main__':
    unittest.main()
