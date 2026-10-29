import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class ClawCheckpointTransportTests(unittest.TestCase):
    def invoke(self, records):
        spec = importlib.util.spec_from_file_location("checkpoint_entry", Path(__file__).with_name("entry.py"))
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "_runner_file_commands"
            root.mkdir()
            summary = root / "step_summary_probe"
            summary.write_text("".join("Security audit checkpoint: " + json.dumps(row) + "\n" for row in records))
            process = SimpleNamespace(returncode=0, communicate=lambda data: None, wait=lambda timeout: 0)
            output, errors = io.StringIO(), io.StringIO()
            with (
                patch.dict(os.environ, {"SECURITY_STAGE": "sast", "GITHUB_STEP_SUMMARY": str(summary)}, clear=True),
                patch.object(entry.sys, "argv", ["entry.py"]),
                patch.object(entry.Path, "is_file", return_value=True),
                patch.object(entry.subprocess, "Popen", return_value=process),
                patch.object(entry.subprocess, "run"),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
            ):
                status = entry.main()
            return status, output.getvalue(), errors.getvalue()

    @staticmethod
    def record():
        return {
            "version": 1,
            "phase": "semgrep",
            "state": "finished",
            "scanners": {
                "semgrep": {
                    "status": "completed",
                    "findings": 0,
                    "errors": 0,
                    "inputs": 1,
                    "timeouts": 0,
                    "known_errors": 0,
                    "execution": {"status": "exited", "returncode": 0, "duration_ms": 1, "wall_limit_seconds": 3600},
                    "report_state": "json",
                }
            },
        }

    def test_safe_completed_checkpoint_is_visible_in_the_actions_log(self):
        status, output, _ = self.invoke([self.record()])
        self.assertEqual(status, 0)
        self.assertIn("Security audit checkpoint: ", output)
        self.assertEqual(json.loads(output.split(": ", 1)[1])["scanners"]["semgrep"]["inputs"], 1)

    def test_root_success_without_report_is_not_completed_coverage(self):
        status, output, _ = self.invoke([])
        self.assertNotEqual(status, 0)
        self.assertEqual(output, "")

    def test_raw_canary_never_crosses_checkpoint_transport(self):
        for field in ("status", "report_state", "raw_message"):
            with self.subTest(field=field):
                record = self.record()
                record["scanners"]["semgrep"][field] = "private-source-canary"
                status, output, errors = self.invoke([record])
                self.assertNotEqual(status, 0)
                self.assertNotIn("private-source-canary", output + errors)

    def test_root_success_cannot_override_incomplete_or_failed_execution(self):
        for field, value in (
            ("status", "partial"),
            ("status", "tool_error"),
            ("report_state", "missing"),
            ("execution", None),
            ("execution", {"status": "timeout", "returncode": None, "duration_ms": 1}),
        ):
            with self.subTest(field=field, value=value):
                record = self.record()
                if value is None:
                    record["scanners"]["semgrep"].pop(field)
                else:
                    record["scanners"]["semgrep"][field] = value
                status, _, _ = self.invoke([record])
                self.assertNotEqual(status, 0)

    def test_started_record_cannot_replace_a_finished_scan(self):
        record = self.record()
        record["state"] = "started"
        status, _, _ = self.invoke([record])
        self.assertNotEqual(status, 0)

    def test_checkpoint_rejects_boolean_counters(self):
        record = self.record()
        record["scanners"]["semgrep"]["inputs"] = True
        status, output, _ = self.invoke([record])
        self.assertNotEqual(status, 0)
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
