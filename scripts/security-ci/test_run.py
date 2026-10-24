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


if __name__ == '__main__':
    unittest.main()
