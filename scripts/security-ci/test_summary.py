import importlib.util
from pathlib import Path
import unittest


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('summary', Path(__file__).with_name('summary.py'))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_failed_scanner_cannot_report_clean_or_disclose_output(self):
        result = self.module.summarize('gitleaks', {'Secret': 'DO_NOT_DISCLOSE'}, 2)
        self.assertEqual(result['status'], 'tool_error')
        self.assertIsNone(result['findings'])
        self.assertNotIn('DO_NOT_DISCLOSE', str(result))

    def test_secret_findings_expose_only_count(self):
        result = self.module.summarize('gitleaks', [{'Secret': 'DO_NOT_DISCLOSE', 'File': 'private.env'}], 10)
        self.assertEqual(result, {'status': 'findings', 'findings': 1, 'errors': 0, 'inputs': None})

    def test_no_dependency_graph_is_partial_not_zero_vulnerabilities(self):
        result = self.module.summarize('trivy', {'SchemaVersion': 2, 'Results': []}, 0)
        self.assertEqual(result['status'], 'coverage_gap')
        self.assertIsNone(result['findings'])

    def test_trivy_counts_actual_packages_and_vulnerabilities(self):
        result = self.module.summarize('trivy', {'SchemaVersion': 2, 'Results': [{'Packages': [{'Name': 'x'}], 'Vulnerabilities': [{'Severity': 'HIGH', 'Description': 'DO_NOT_DISCLOSE'}]}]}, 0)
        self.assertEqual(result, {'status': 'findings', 'findings': 1, 'errors': 0, 'inputs': 1})

    def test_semgrep_parser_failure_is_partial_with_positive_findings(self):
        result = self.module.summarize('semgrep', {'results': [{}], 'errors': [{}], 'paths': {'scanned': ['private.py']}}, 0)
        self.assertEqual(result, {'status': 'partial', 'findings': 1, 'errors': 1, 'inputs': 1, 'timeouts': 0})
        self.assertEqual(result.get('timeouts'), 0)

    def test_malformed_schema_is_error(self):
        for tool in ('gitleaks', 'semgrep', 'trivy'):
            self.assertEqual(self.module.summarize(tool, {'results': 'bad'}, 0)['status'], 'tool_error')

    def test_falsy_invalid_trivy_array_is_not_a_coverage_gap(self):
        self.assertEqual(self.module.summarize('trivy', {'SchemaVersion': 2, 'Results': ''}, 0)['status'], 'tool_error')


    def test_fixpoint_timeout_is_partial_even_without_top_level_errors(self):
        payload = {'results': [{}], 'errors': [], 'paths': {'scanned': ['private.py']},
                   'time': {'fixpoint_timeouts': [{'message': 'DO_NOT_DISCLOSE', 'location': {'path': 'private.py'}}]}}
        result = self.module.summarize('semgrep', payload, 0)
        self.assertEqual(result, {'status': 'partial', 'findings': 1, 'errors': 1, 'inputs': 1, 'timeouts': 1})
        self.assertEqual(result.get('timeouts'), 1)
        self.assertNotIn('DO_NOT_DISCLOSE', str(result))
        self.assertNotIn('private.py', str(result))

    def test_fixpoint_timeout_counts_in_addition_to_parser_errors(self):
        payload = {'results': [{}], 'errors': [{}], 'paths': {'scanned': ['private.py']},
                   'time': {'fixpoint_timeouts': [{}]}}
        self.assertEqual(self.module.summarize('semgrep', payload, 0)['errors'], 2)

    def test_malformed_fixpoint_timeout_list_cannot_be_clean(self):
        for invalid in ('', None, {}):
            with self.subTest(invalid=invalid):
                payload = {'results': [], 'errors': [], 'paths': {'scanned': ['x.py']},
                           'time': {'fixpoint_timeouts': invalid}}
                self.assertEqual(self.module.summarize('semgrep', payload, 0)['status'], 'tool_error')


if __name__ == '__main__':
    unittest.main()
