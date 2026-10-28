import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class EntryTests(unittest.TestCase):
    def test_duplicate_request_does_not_finish_original_audit(self):
        spec=importlib.util.spec_from_file_location('security_entry',Path(__file__).with_name('entry.py'))
        entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        process=SimpleNamespace(returncode=73,communicate=lambda data:None,wait=lambda timeout:73)
        with patch.object(entry.sys,'argv',['entry.py']),patch.object(entry.Path,'is_file',return_value=True),patch.object(entry.subprocess,'Popen',return_value=process),patch.object(entry.subprocess,'run') as finish:
            self.assertEqual(entry.main(),73)
            finish.assert_not_called()
