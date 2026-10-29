import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class EntryTests(unittest.TestCase):
    def test_duplicate_request_does_not_finish_original_audit(self):
        spec = importlib.util.spec_from_file_location("security_entry", Path(__file__).with_name("entry.py"))
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        process = SimpleNamespace(returncode=73, communicate=lambda data: None, wait=lambda timeout: 73)
        with (
            patch.object(entry.sys, "argv", ["entry.py"]),
            patch.object(entry.Path, "is_file", return_value=True),
            patch.object(entry.subprocess, "Popen", return_value=process),
            patch.object(entry.subprocess, "run") as finish,
        ):
            self.assertEqual(entry.main(), 73)
            finish.assert_not_called()


class StageForwardingTests(unittest.TestCase):
    def test_selected_stage_is_forwarded_but_default_keeps_legacy_request(self):
        import json

        for stage in ("all", "sast", "secrets", "dependencies"):
            with self.subTest(stage=stage):
                spec = importlib.util.spec_from_file_location("stage_entry", Path(__file__).with_name("entry.py"))
                entry = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(entry)
                requests = []
                process = SimpleNamespace(
                    returncode=0,
                    communicate=lambda data, captured=requests: captured.append(json.loads(data)),
                    wait=lambda timeout: 0,
                )
                with tempfile.TemporaryDirectory() as directory:
                    summary_dir = Path(directory) / "_runner_file_commands"
                    summary_dir.mkdir()
                    summary = summary_dir / "step_summary_stage"
                    names = {
                        "all": ("gitleaks", "trivy", "semgrep"),
                        "sast": ("semgrep",),
                        "secrets": ("gitleaks",),
                        "dependencies": ("trivy",),
                    }[stage]
                    record = {
                        "version": 1,
                        "phase": names[-1],
                        "state": "finished",
                        "scanners": {
                            name: {
                                "status": "completed",
                                "findings": 0,
                                "errors": 0,
                                "inputs": 1,
                                "execution": {"status": "exited", "returncode": 0, "duration_ms": 1},
                                "report_state": "json",
                            }
                            for name in names
                        },
                    }
                    summary.write_text("Security audit checkpoint: " + json.dumps(record) + "\n")
                    self.invoke_entry(entry, process, stage, summary)
                self.assertEqual(len(requests), 1)
                if stage == "all":
                    self.assertNotIn("stage", requests[0])
                else:
                    self.assertEqual(requests[0].get("stage"), stage)

    def invoke_entry(self, entry, process, stage, summary):
        import os

        with (
            patch.object(entry.sys, "argv", ["entry.py"]),
            patch.object(entry.Path, "is_file", return_value=True),
            patch.object(entry.subprocess, "Popen", return_value=process),
            patch.object(entry.subprocess, "run"),
            patch.dict(os.environ, {"SECURITY_STAGE": stage, "GITHUB_STEP_SUMMARY": str(summary)}, clear=True),
        ):
            self.assertEqual(entry.main(), 0)

    def test_invalid_stage_never_launches_or_finishes_an_existing_job(self):
        import os

        spec = importlib.util.spec_from_file_location("invalid_stage_entry", Path(__file__).with_name("entry.py"))
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        with (
            patch.object(entry.sys, "argv", ["entry.py"]),
            patch.dict(os.environ, {"SECURITY_STAGE": "invalid-private-value"}, clear=True),
            patch.object(entry.Path, "is_file", return_value=True),
            patch.object(entry.subprocess, "Popen") as launch,
            patch.object(entry.subprocess, "run") as finish,
        ):
            with self.assertRaises(SystemExit) as result:
                entry.main()
        self.assertEqual(str(result.exception), "unsupported audit stage")
        launch.assert_not_called()
        finish.assert_not_called()
