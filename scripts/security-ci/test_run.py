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

    def run_audit(self, change=None, bootstrap_error=False, process_observer=None, engine="semgrep", interruption_tool=None, stage="all", runtime_seconds=None):
        import contextlib
        import io
        import json
        from unittest import mock

        marker = 'not-public-canary-text'
        self.last_all_commands = []
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
            step.touch()

            def download_fixture(pin, destination, **kwargs):
                AuditOutcomeTests.download_fixture(pin, destination, bootstrap_error)

            def scanner_boundary(args, log, **kwargs):
                self.last_all_commands.append(args)
                log.write_text(marker)
                name = Path(args[0]).name
                if name not in reports:
                    return 0  # No network/installation in a report-orchestration test.
                payload, code = reports[name]
                if name == interruption_tool:
                    kwargs.get('diagnostics', {}).update(status='cancelled', returncode=None, duration_ms=0)
                    raise SystemExit(143)
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
            audit_env = {'RUNNER_TEMP': str(state), 'GITHUB_STEP_SUMMARY': str(step), 'SECURITY_ENGINE': engine, 'SECURITY_STAGE': stage}
            audit_env['SECURITY_RUNTIME_SECONDS'] = '' if runtime_seconds is None else str(runtime_seconds)
            try:
                os.chdir(workspace)
                with mock.patch.dict(os.environ, audit_env, clear=True), \
                     mock.patch.object(self.module, 'download', side_effect=download_fixture), \
                     mock.patch.object(self.module, 'command', side_effect=scanner_boundary), \
                     contextlib.redirect_stdout(output):
                    code = AuditOutcomeTests.call_audit(self, allow_interrupt=interruption_tool is not None)
            finally:
                os.chdir(original)
                os.umask(mask)
            published = output.getvalue()
            self.assertNotIn(marker, published + step.read_text())
            self.assertNotIn('not-public-canary.py', published + step.read_text())
            self.last_checkpoints, final, result = AuditOutcomeTests.decode_output(published)
            self.assertIn(final.strip(), step.read_text())
            return code, result

    def test_independent_stages_run_only_the_selected_scanner(self):
        for stage, tool in [('sast', 'semgrep'), ('secrets', 'gitleaks'), ('dependencies', 'trivy')]:
            with self.subTest(stage=stage):
                code, result = self.run_audit(stage=stage)
                self.assertEqual(code, 0)
                self.assertEqual(set(result['scanners']), {tool})
                self.assertEqual(result['stage'], stage)
                downloaded = {pin['tool'] for pin in result['tools']}
                if stage != 'sast':
                    self.assertEqual(downloaded, {tool})
                    self.assertFalse(any('-m' in args and 'venv' in args for args in self.last_all_commands))
                    self.assertFalse(any('--pack' in args for args in self.last_all_commands))

    def test_sast_stage_keeps_selected_opengrep_and_no_other_scanners(self):
        code, result = self.run_audit(engine='opengrep', stage='sast')
        self.assertEqual(code, 0)
        self.assertEqual(set(result['scanners']), {'opengrep'})
        self.assertNotIn('trivy', {p['tool'] for p in result['tools']})
        self.assertNotIn('gitleaks', {p['tool'] for p in result['tools']})

    def test_non_sast_stage_does_not_consume_another_engines_parser_policy(self):
        from unittest import mock

        with mock.patch.object(self.module, 'load_source_policy',
                               side_effect=ValueError('unused parser policy')) as policy:
            code, result = self.run_audit(stage='secrets')
        self.assertEqual(code, 0)
        policy.assert_not_called()
        self.assertEqual(set(result['scanners']), {'gitleaks'})

    def test_unknown_stage_fails_closed_without_starting_a_scanner(self):
        code, result = self.run_audit(stage='not-public-canary-text')
        self.assertEqual(code, 1)
        self.assertEqual(result['scanners'], {})
        self.assertEqual(result['bootstrap_status'], 'tool_error')

    def test_sast_only_missing_report_remains_an_error(self):
        code, result = self.run_audit(stage='sast', change={'semgrep': ('missing', 0)})
        self.assertEqual(code, 1)
        self.assertEqual(set(result['scanners']), {'semgrep'})
        self.assertEqual(result['scanners']['semgrep']['status'], 'tool_error')

    @staticmethod
    def download_fixture(pin, destination, bootstrap_error):
        import io
        import tarfile

        if bootstrap_error:
            raise ValueError('not-public-canary-text')
        if pin['tool'] in ('gitleaks', 'trivy'):
            with tarfile.open(destination, 'w:gz') as archive:
                item = tarfile.TarInfo(pin['tool'])
                body = b'synthetic downloaded tool boundary'
                item.size = len(body)
                archive.addfile(item, io.BytesIO(body))
        else:
            destination.write_bytes(b'synthetic downloaded package boundary')

    def call_audit(self, allow_interrupt):
        try:
            return self.module.audit()
        except SystemExit as error:
            if not allow_interrupt:
                raise
            return error.code

    @staticmethod
    def decode_output(published):
        import json

        prefix = 'Security audit checkpoint: '
        checkpoints = [json.loads(line[len(prefix):]) for line in published.splitlines()
                       if line.startswith(prefix)]
        final = '\n'.join(line for line in published.splitlines() if not line.startswith(prefix))
        return checkpoints, final, json.loads(final) if final.strip() else {}

    def test_cancelled_later_scanner_keeps_completed_stage_checkpoint(self):
        code, result = self.run_audit(interruption_tool='trivy')
        self.assertEqual(code, 143)
        completed = [row for row in self.last_checkpoints
                     if row.get('phase') == 'gitleaks' and row.get('state') == 'finished']
        self.assertEqual(len(completed), 1, 'completed scanner observations were lost')
        self.assertEqual(completed[0]['scanners']['gitleaks']['errors'], 0)
        self.assertEqual(result.get('execution_status'), 'cancelled')
        self.assertEqual(result['scanners']['trivy']['execution']['status'], 'cancelled')
        self.assertEqual(result['scanners']['trivy']['status'], 'tool_error')

    def test_cancelled_engine_keeps_both_earlier_stage_checkpoints(self):
        code, result = self.run_audit(interruption_tool='semgrep')
        self.assertEqual(code, 143)
        completed = {row.get('phase') for row in self.last_checkpoints
                     if row.get('state') == 'finished'}
        self.assertTrue({'gitleaks', 'trivy'} <= completed)
        self.assertEqual(result.get('execution_status'), 'cancelled')
        self.assertEqual(result['scanners']['semgrep']['status'], 'tool_error')

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

    def test_claw_deadline_caps_scanner_and_reserves_cleanup(self):
        calls = {}
        def observe(name, args, kwargs):
            calls[name] = kwargs['timeout']
        code, result = self.run_audit(stage='sast', runtime_seconds=2700, process_observer=observe)
        self.assertEqual(code, 0)
        self.assertLessEqual(calls['semgrep'], 2680)
        self.assertEqual(result['scanners']['semgrep']['execution']['wall_limit_seconds'], calls['semgrep'])

    def test_selected_sast_with_zero_inputs_is_an_error(self):
        code, result = self.run_audit({'semgrep': ({'results': [], 'errors': [], 'paths': {'scanned': []}}, 0)}, stage='sast')
        self.assertEqual(code, 1)
        self.assertEqual(result['scanners']['semgrep']['status'], 'coverage_gap')

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
        self.assertIn('--jobs=1', args)
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
