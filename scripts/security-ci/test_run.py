import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


class RunnerIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('security_runner', Path(__file__).with_name('run.py'))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_bootstrap_module_search_cannot_execute_target_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, private = root / 'project', root / 'private'
            project.mkdir()
            private.mkdir()
            marker = project / 'executed.marker'
            (project / 'json.py').write_text(
                'from pathlib import Path\n'
                'Path(__file__).with_name("executed.marker").write_text("executed")\n'
            )
            original = Path.cwd()
            try:
                os.chdir(project)
                result = self.module.command(
                    [sys.executable, '-m', 'json.tool', '--help'], private / 'command.log',
                    timeout=10, env={'PATH': os.environ.get('PATH', ''), 'HOME': str(private)},
                )
                self.assertFalse(marker.exists(), 'Target source ran during a tool bootstrap')
                self.assertEqual(result, 0)
                self.assertEqual(Path.cwd(), project)
            finally:
                os.chdir(original)


class AuditOutcomeTests(unittest.TestCase):
    """Keep process exit status and safe output tied to real report parsing."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('security_audit_outcomes', Path(__file__).with_name('run.py'))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def run_audit(self, change=None, bootstrap_error=False):
        import contextlib
        import io
        import json
        import tarfile
        from unittest import mock

        marker = 'not-public-canary-text'
        reports = {
            'gitleaks': ([], 0),
            'trivy': ({'SchemaVersion': 2, 'Results': [{'Packages': [{'Name': 'sample'}], 'Vulnerabilities': []}]}, 0),
            'semgrep': ({'results': [], 'errors': [], 'paths': {'scanned': ['not-public-canary.py']}}, 0),
        }
        if change:
            reports.update(change)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, state = root / 'workspace', root / 'state'
            workspace.mkdir()
            state.mkdir()
            step = root / 'step-summary.md'

            def download_fixture(pin, destination):
                if bootstrap_error:
                    raise ValueError(marker)
                if pin['tool'] in ('gitleaks', 'trivy'):
                    with tarfile.open(destination, 'w:gz') as archive:
                        item = tarfile.TarInfo(pin['tool'])
                        body = b'synthetic downloaded tool boundary'
                        item.size = len(body)
                        archive.addfile(item, io.BytesIO(body))
                else:
                    destination.write_bytes(b'synthetic downloaded package boundary')

            def scanner_boundary(args, log, **kwargs):
                log.write_text(marker)
                name = Path(args[0]).name
                if name not in reports:
                    return 0  # No network/installation in a report-orchestration test.
                payload, code = reports[name]
                output = log.with_suffix('.json')
                if payload != 'missing':
                    output.write_text('{' if payload == 'malformed' else json.dumps(payload))
                return code

            original = Path.cwd()
            mask = os.umask(0o077)
            output = io.StringIO()
            try:
                os.chdir(workspace)
                with mock.patch.dict(os.environ, {'RUNNER_TEMP': str(state), 'GITHUB_STEP_SUMMARY': str(step)}, clear=True), \
                     mock.patch.object(self.module, 'download', side_effect=download_fixture), \
                     mock.patch.object(self.module, 'command', side_effect=scanner_boundary), \
                     contextlib.redirect_stdout(output):
                    code = self.module.audit()
            finally:
                os.chdir(original)
                os.umask(mask)
            published = output.getvalue()
            self.assertNotIn(marker, published + step.read_text())
            self.assertNotIn('not-public-canary.py', published + step.read_text())
            self.assertIn(published.strip(), step.read_text())
            return code, json.loads(published)

    def test_advisory_findings_keep_success_without_raw_evidence(self):
        code, result = self.run_audit({
            'gitleaks': ([{'message': 'not-public-canary-text'}], 10),
            'trivy': ({'SchemaVersion': 2, 'Results': [{'Packages': [{'Name': 'sample'}], 'Vulnerabilities': [{'Severity': 'HIGH', 'Description': 'not-public-canary-text'}]}]}, 0),
            'semgrep': ({'results': [{'message': 'not-public-canary-text'}], 'errors': [], 'paths': {'scanned': ['not-public-canary.py']}}, 0),
        })
        self.assertEqual(code, 0)
        self.assertTrue(all(r['findings'] == 1 for r in result['scanners'].values()))

    def test_tool_exit_failure_is_nonzero(self):
        code, result = self.run_audit({'gitleaks': ([], 2)})
        self.assertNotEqual(code, 0)
        self.assertEqual(result['scanners']['gitleaks']['status'], 'tool_error')

    def test_malformed_reports_fail_for_every_tool(self):
        for tool in ('gitleaks', 'trivy', 'semgrep'):
            with self.subTest(tool=tool):
                code, result = self.run_audit({tool: ('malformed', 0)})
                self.assertNotEqual(code, 0)
                self.assertEqual(result['scanners'][tool]['status'], 'tool_error')

    def test_missing_reports_fail_for_every_tool(self):
        for tool in ('gitleaks', 'trivy', 'semgrep'):
            with self.subTest(tool=tool):
                code, result = self.run_audit({tool: ('missing', 0)})
                self.assertNotEqual(code, 0)
                self.assertEqual(result['scanners'][tool]['status'], 'tool_error')

    def test_parser_error_is_nonzero_and_preserves_error_count(self):
        code, result = self.run_audit({'semgrep': ({'results': [], 'errors': [{'message': 'not-public-canary-text'}], 'paths': {'scanned': ['not-public-canary.py']}}, 0)})
        self.assertNotEqual(code, 0)
        self.assertEqual(result['scanners']['semgrep']['errors'], 1)
        self.assertEqual(result['scanners']['semgrep']['status'], 'partial')

    def test_fixpoint_timeout_is_nonzero_and_separately_counted(self):
        code, result = self.run_audit({'semgrep': ({'results': [], 'errors': [], 'paths': {'scanned': ['not-public-canary.py']}, 'time': {'fixpoint_timeouts': [{'message': 'not-public-canary-text'}]}}, 0)})
        self.assertNotEqual(code, 0)
        self.assertEqual(result['scanners']['semgrep']['errors'], 1)
        self.assertEqual(result['scanners']['semgrep']['timeouts'], 1)

    def test_bootstrap_exception_fails_without_disclosing_message(self):
        code, result = self.run_audit(bootstrap_error=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(result['bootstrap_status'], 'tool_error')


if __name__ == '__main__':
    unittest.main()
