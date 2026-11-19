"""Engine selection is explicit and parser acceptance stays engine-bound."""
import json
from pathlib import Path
import tempfile
import unittest

import baseline
import run as runner
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

    def test_self_audit_policy_accepts_the_real_opengrep_pin(self):
        # The checked-in workflow selects OpenGrep, outside the synthetic fixtures.
        here = Path(__file__).resolve().parent
        pins = json.loads((here / 'tools.json').read_text())
        try:
            policy = baseline.load_policy(here.parent.parent / '.security-ci-baseline.json',
                                          pins, engine='opengrep')
        except ValueError as error:
            self.fail(f'Self-audit rejects its pinned OpenGrep engine: {error}')
        self.assertEqual(policy['engine'], 'opengrep')
        self.assertEqual(policy['engine_version'], next(p['version'] for p in pins if p['tool'] == 'opengrep'))
        self.assertEqual(policy['accepted_parser_errors'], [])

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


class EngineRuleCompatibilityTests(unittest.TestCase):
    def rule(self):
        return {'id': '7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args',
                'options': {'symbolic_propagation': True},
                'mode': 'taint', 'pattern-sources': [{'pattern': 'os.environ'}],
                'pattern-sinks': [{'patterns': [{'pattern-either': [{'patterns': [
                    {'pattern-not': 'subprocess.$FUNC("...", ...)'},
                    {'pattern-not': 'subprocess.$FUNC(["...",...], ...)'},
                    {'pattern-not': 'subprocess.$FUNC(("...",...), ...)'},
                    {'pattern': 'subprocess.$FUNC($CMD, ...)'},
                ]}]}]}]}

    @staticmethod
    def sink_patterns(rule):
        return rule['pattern-sinks'][0]['patterns'][0]['pattern-either'][0]['patterns']

    def configure_many(self, rules, engine):
        try:
            return runner.configure_engine_rules(rules, engine)
        except AttributeError as error:
            self.fail(f'Explicit engine rule compatibility is unavailable: {error}')

    def configure(self, rule, engine):
        return self.configure_many([rule], engine)[0]

    def test_opengrep_keeps_aliased_shell_sinks_conservative(self):
        rule = self.rule()
        expected = self.rule()
        literal = '=~/(?s)^(?!.*(?:sh|bash|ksh|csh|tcsh|zsh|python)).*$/'
        for index in (1, 2):
            part = self.sink_patterns(expected)[index]
            part['pattern-not'] = part['pattern-not'].replace('"..."', f'"{literal}"')
        self.assertEqual(self.configure(rule, 'opengrep'), expected)

    def test_semgrep_rule_content_is_unchanged(self):
        self.assertEqual(self.configure(self.rule(), 'semgrep'), self.rule())

    def test_other_opengrep_rules_are_unchanged(self):
        rule = dict(self.rule(), id='another-rule')
        result = self.configure_many([self.rule(), rule], 'opengrep')
        self.assertEqual(result[1], dict(self.rule(), id='another-rule'))

    def test_shared_upstream_options_do_not_modify_another_rule(self):
        selected = self.rule()
        other = dict(self.rule(), id='another-rule', options=selected['options'])
        result = self.configure_many([selected, other], 'opengrep')
        self.assertTrue(result[0]['options']['symbolic_propagation'])
        self.assertTrue(result[1]['options']['symbolic_propagation'])

    def test_shared_sink_mappings_do_not_modify_another_rule(self):
        selected = self.rule()
        other = {**self.rule(), 'id': 'another-rule', 'pattern-sinks': selected['pattern-sinks']}
        result = self.configure_many([selected, other], 'opengrep')
        self.assertNotEqual(result[0]['pattern-sinks'], self.rule()['pattern-sinks'])
        self.assertEqual(result[1]['pattern-sinks'], self.rule()['pattern-sinks'])

    def test_interpreter_exclusion_drift_is_rejected(self):
        for malformed in ('missing', 'duplicate', 'shape'):
            with self.subTest(malformed=malformed):
                rule = self.rule()
                if malformed == 'missing':
                    self.sink_patterns(rule).pop(1)
                elif malformed == 'duplicate':
                    self.sink_patterns(rule).append(dict(self.sink_patterns(rule)[1]))
                else:
                    rule['pattern-sinks'] = []
                with self.assertRaises(ValueError):
                    self.configure(rule, 'opengrep')

    def test_missing_or_duplicate_upstream_rule_is_rejected(self):
        for rules in ([], [self.rule(), self.rule()]):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                self.configure_many(rules, 'opengrep')

    def test_unexpected_upstream_option_drift_is_rejected(self):
        rule = self.rule()
        rule['options']['symbolic_propagation'] = False
        with self.assertRaises(ValueError):
            self.configure(rule, 'opengrep')

    def test_unknown_engine_is_rejected(self):
        with self.assertRaises(ValueError):
            self.configure(self.rule(), 'another-engine')


if __name__ == '__main__':
    unittest.main()
