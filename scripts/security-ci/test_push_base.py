import importlib.util
from pathlib import Path
import unittest
import os
import subprocess
import tempfile


class PushBaseTests(unittest.TestCase):
    def test_resolver_contract(self):
        path = Path(__file__).with_name('push_base.py')
        self.assertTrue(path.exists(), 'push resolver must exist')

    def test_bootstrap_projects_unique_merge_base_and_rejects_unrelated_history(self):
        path = Path(__file__).with_name('push_base.py')
        spec = importlib.util.spec_from_file_location('push_base_git', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(['git', '-C', directory, *args], check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            git('commit', '--allow-empty', '-qm', 'common')
            common = git('rev-parse', 'HEAD')
            git('checkout', '-qb', 'bootstrap')
            git('commit', '--allow-empty', '-qm', 'full audit')
            audited = git('rev-parse', 'HEAD')
            git('checkout', '-qb', 'branch', common)
            git('commit', '--allow-empty', '-qm', 'branch change')
            head = git('rev-parse', 'HEAD')
            git('checkout', '--orphan', 'unrelated')
            git('commit', '--allow-empty', '-qm', 'unrelated')
            unrelated = git('rev-parse', 'HEAD')
            old = os.getcwd()
            try:
                os.chdir(directory)
                self.assertEqual(module.project_bootstrap(audited, head), common)
                self.assertIsNone(module.project_bootstrap(unrelated, head))
            finally:
                os.chdir(old)

    def test_verified_ancestor_and_failure_cases(self):
        path = Path(__file__).with_name('push_base.py')
        if not path.exists():
            self.skipTest('resolver not implemented')
        spec = importlib.util.spec_from_file_location('push_base', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        repo = {'full_name': 'owner/repo'}
        def run(number, sha, **overrides):
            return dict({'id': number, 'run_number': number, 'run_attempt': 1, 'workflow_id': 7,
                         'path': '.github/workflows/security-audit.yml', 'event': 'push',
                         'status': 'completed', 'conclusion': 'success', 'head_branch': 'main',
                         'head_sha': sha, 'repository': repo, 'head_repository': repo}, **overrides)
        current = run(10, 'c' * 40)
        older = run(4, 'a' * 40)
        newer = run(9, 'b' * 40, conclusion='cancelled')
        job = {'name': 'audit', 'conclusion': 'success', 'status': 'completed',
               'steps': [{'name': 'Run Gitleaks push range', 'conclusion': 'success', 'status': 'completed'}]}
        def api(path):
            if path == '/actions/runs/10': return current
            if path.startswith('/actions/workflows/7/runs?'): return [newer, older]
            if path == '/actions/runs/4': return older
            if path.startswith(('/actions/runs/4/attempts/1/jobs?', '/actions/runs/5/attempts/1/jobs?')): return [job]
            raise AssertionError(path)
        context = {'repository': 'owner/repo', 'run_id': 10, 'sha': 'c' * 40, 'branch': 'main'}
        resolve = lambda: module.resolve(context, api, lambda sha: sha == 'a' * 40, 4)
        self.assertEqual(resolve(), 'a' * 40)
        for field, value in [('workflow_id', 8), ('event', 'pull_request'),
                             ('repository', {'full_name': 'foreign/repo'}), ('head_repository', {'full_name': 'foreign/repo'})]:
            with self.subTest(field=field):
                old = older[field]; older[field] = value
                with self.assertRaises(ValueError): resolve()
                older[field] = old
        for field, value in [('path', '.github/workflows/other.yml'),
                             ('head_branch', 'other'), ('head_sha', 'e' * 40),
                             ('event', 'pull_request')]:
            with self.subTest(current_field=field):
                old = current[field]; current[field] = value
                with self.assertRaises(ValueError): resolve()
                current[field] = old
        # A receipt from another branch must not suppress scanning; the explicit
        # full-history bootstrap is used even when the other receipt is newer.
        older['head_branch'] = 'other'
        job['steps'][0]['name'] = 'Run pinned source audit'
        self.assertEqual(resolve(), 'a' * 40)
        job['steps'][0]['name'] = 'Run Gitleaks push range'
        with self.assertRaises(ValueError): resolve()
        older['head_branch'] = 'main'
        job['conclusion'] = 'skipped'
        with self.assertRaises(ValueError): resolve()
        job['conclusion'] = 'success'
        job['steps'][0]['conclusion'] = 'skipped'
        with self.assertRaises(ValueError): resolve()
        job['steps'][0]['conclusion'] = 'success'
        with self.assertRaises(ValueError): module.resolve(context, api, lambda sha: False, 4)
        job['steps'][0]['name'] = 'Run pinned source audit'
        self.assertEqual(resolve(), 'a' * 40)
        job['steps'].append({'name': 'Run Gitleaks on automatic events',
                             'conclusion': 'skipped', 'status': 'completed'})
        self.assertEqual(resolve(), 'a' * 40)
        job['steps'].pop()
        self.assertEqual(module.resolve(context, api, lambda sha: False, 4,
                                        lambda sha: 'd' * 40), 'd' * 40)
        with self.assertRaises(ValueError):
            module.resolve(context, api, lambda sha: False, 4, lambda sha: None)
        older['id'] = 5
        with self.assertRaises(ValueError): resolve()
        older['id'] = 4
        job['steps'][0]['conclusion'] = 'failure'
        with self.assertRaises(ValueError): resolve()
