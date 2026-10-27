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

    def run_audit(self, change=None, bootstrap_error=False, process_observer=None, engine="semgrep"):
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
        if engine == "opengrep":
            reports["opengrep"] = reports.pop("semgrep")
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
                if process_observer is not None:
                    process_observer(name, args, kwargs)
                if 'diagnostics' in kwargs:
                    kwargs['diagnostics'].update(status='exited', returncode=code, duration_ms=0)
                output = log.with_suffix('.json')
                if payload != 'missing':
                    output.write_text('{' if payload == 'malformed' else json.dumps(payload))
                return code

            original = Path.cwd()
            mask = os.umask(0o077)
            output = io.StringIO()
            try:
                os.chdir(workspace)
                with mock.patch.dict(os.environ, {'RUNNER_TEMP': str(state), 'GITHUB_STEP_SUMMARY': str(step), 'SECURITY_ENGINE': engine}, clear=True), \
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

    def test_explicit_opengrep_runs_pinned_binary_with_private_reports(self):
        commands = []
        def observe(name, args, kwargs):
            commands.append((name, args))
        code, result = self.run_audit(engine='opengrep', process_observer=observe)
        self.assertEqual(code, 0)
        self.assertEqual(set(result['scanners']), {'gitleaks', 'trivy', 'opengrep'})
        args = next(args for name, args in commands if name == 'opengrep')
        self.assertIn('--x-ignore-semgrepignore-files', args)
        self.assertIn('--disable-nosem', args)
        self.assertIn('--timeout=20', args)
        self.assertNotIn('--metrics=off', args)
        self.assertTrue(any(pin['tool'] == 'opengrep' for pin in result['tools']))

    def test_opengrep_timeout_fails_without_engine_fallback(self):
        payload = {'results': [], 'errors': [], 'paths': {'scanned': ['not-public-canary.py']},
                   'time': {'fixpoint_timeouts': [{'message': 'not-public-canary-text'}]}}
        code, result = self.run_audit(engine='opengrep', change={'opengrep': (payload, 0)})
        self.assertEqual(code, 1)
        self.assertEqual(result['scanners']['opengrep']['timeouts'], 1)
        self.assertEqual(result['scanners']['opengrep']['status'], 'partial')
        self.assertNotIn('semgrep', result['scanners'])

    def test_invalid_engine_fails_before_scanning(self):
        code, result = self.run_audit(engine='unexpected')
        self.assertEqual(code, 1)
        self.assertEqual(result['bootstrap_status'], 'tool_error')
        self.assertEqual(result['scanners'], {})

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


class CommandDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('command_diagnostics', Path(__file__).with_name('run.py'))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def execute(self, args, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            details = {}
            code = self.module.command(args, Path(directory) / 'private-canary.log',
                                       timeout=timeout, diagnostics=details)
            self.assertEqual(set(details), {'status', 'returncode', 'duration_ms'})
            self.assertIsInstance(details['duration_ms'], int)
            self.assertGreaterEqual(details['duration_ms'], 0)
            self.assertNotIn('private-canary', str(details))
            return code, details

    def test_actual_nonzero_exit_is_distinct_from_wall_timeout(self):
        code, details = self.execute([sys.executable, '-c', 'raise SystemExit(124)'])
        self.assertEqual(code, 124)
        self.assertEqual(details['status'], 'exited')
        self.assertEqual(details['returncode'], 124)

    def test_actual_wall_timeout_is_explicit_without_exception_text(self):
        code, details = self.execute([sys.executable, '-c', 'while True: pass'], timeout=0.05)
        self.assertEqual(code, 124)
        self.assertEqual(details['status'], 'timeout')
        self.assertIsNone(details['returncode'])

    def test_actual_launch_error_is_distinct_from_timeout(self):
        code, details = self.execute(['/no-such-private-canary-scanner'])
        self.assertEqual(code, 124)
        self.assertEqual(details['status'], 'launch_error')
        self.assertIsNone(details['returncode'])


class AuditDiagnosticsTests(unittest.TestCase):
    setUpClass = classmethod(AuditOutcomeTests.setUpClass.__func__)
    run_audit = AuditOutcomeTests.run_audit

    def test_missing_json_and_failure_keep_safe_execution_metadata(self):
        code, payload = self.run_audit({'semgrep': ('missing', 124)})
        self.assertEqual(code, 1)
        scanner = payload['scanners']['semgrep']
        self.assertEqual(scanner['status'], 'tool_error')
        self.assertIsNone(scanner['findings'])
        self.assertEqual(scanner['report_state'], 'missing')
        self.assertEqual(scanner['execution']['status'], 'exited')
        self.assertEqual(scanner['execution']['returncode'], 124)
        self.assertNotIn('not-public-canary', str(payload))

    def test_invalid_json_is_distinct_from_missing_report(self):
        code, payload = self.run_audit({'semgrep': ('malformed', 0)})
        self.assertEqual(code, 1)
        self.assertEqual(payload['scanners']['semgrep']['report_state'], 'invalid_json')

    def test_parsed_json_is_not_a_claim_of_schema_validity(self):
        code, payload = self.run_audit({'semgrep': ({}, 0)})
        self.assertEqual(code, 1)
        self.assertEqual(payload['scanners']['semgrep']['report_state'], 'json')
        self.assertEqual(payload['scanners']['semgrep']['status'], 'tool_error')


class ScannerBudgetTests(unittest.TestCase):
    setUpClass = classmethod(AuditOutcomeTests.setUpClass.__func__)
    run_audit = AuditOutcomeTests.run_audit

    def test_extended_semgrep_budget_is_used_by_the_actual_process_boundary(self):
        calls = {}
        def observe(name, args, kwargs):
            calls[name] = (args, kwargs.get('timeout', 600), Path.cwd())
        code, result = self.run_audit(process_observer=observe)
        self.assertEqual(code, 0)
        self.assertEqual(calls['semgrep'][1], 3600)
        self.assertEqual(calls['gitleaks'][1], 600)
        self.assertEqual(calls['trivy'][1], 600)
        self.assertEqual(result['scanners']['semgrep']['execution']['wall_limit_seconds'], 3600)
        args = calls['semgrep'][0]
        self.assertEqual(Path(args[-1]), calls['semgrep'][2])
        self.assertIn('--timeout=20', args)
        self.assertIn('--jobs=2', args)
        self.assertIn('--max-memory=512', args)
        self.assertEqual([a for a in args if a.startswith('--exclude=')],
                         ['--exclude=.git', '--exclude=node_modules', '--exclude=.venv', '--exclude=tmp'])

    def test_longer_deadline_does_not_make_a_missing_report_successful(self):
        code, result = self.run_audit({'semgrep': ('missing', 124)})
        scanner = result['scanners']['semgrep']
        self.assertEqual(code, 1)
        self.assertEqual(scanner['status'], 'tool_error')
        self.assertIsNone(scanner['findings'])
        self.assertIsNone(scanner['inputs'])
        self.assertEqual(scanner['report_state'], 'missing')
        self.assertEqual(scanner['execution']['wall_limit_seconds'], 3600)

    def test_shared_source_workflow_has_room_for_scanner_and_other_phases(self):
        import re
        workflow = Path(__file__).resolve().parents[2] / '.github/workflows/security-audit.yml'
        matches = re.findall(r'(?m)^    timeout-minutes: (\d+)\s*$', workflow.read_text())
        self.assertEqual(len(matches), 1)
        # Every configured cap plus a 10-minute setup reserve must fit the job.
        self.assertGreaterEqual(int(matches[0]) * 60, 3600 + 600 + 600 + 600)
