"""Use claw's bounded host service, or direct execution on hosted runners."""

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

from summary import safe_checkpoint

HERE = Path(__file__).resolve().parent
LAUNCHER = Path("/usr/local/lib/claw-memory/audit_launcher.py")
CHECKPOINT_PREFIX = "Security audit checkpoint: "
SUMMARY_LIMIT = 65_536


def read_step_checkpoints():
    """Read only the bounded, owned GitHub file; never relay arbitrary text."""
    path = Path(os.environ.get("GITHUB_STEP_SUMMARY", ""))
    if not path.name.startswith("step_summary_") or path.parent.name != "_runner_file_commands":
        return None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags)) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > SUMMARY_LIMIT:
                return None
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                return None
            text = stream.read(SUMMARY_LIMIT + 1)
        if len(text) > SUMMARY_LIMIT:
            return None
        records = [
            json.loads(line[len(CHECKPOINT_PREFIX) :])
            for line in text.splitlines()
            if line.startswith(CHECKPOINT_PREFIX)
        ]
        return records if all(safe_checkpoint(row) for row in records) else None
    except (OSError, ValueError, TypeError, RecursionError):
        return None


def forward_checkpoints(stage, engine):
    records = read_step_checkpoints()
    if records is None:
        return False
    for row in records:
        print(CHECKPOINT_PREFIX + json.dumps(row, sort_keys=True), flush=True)
    expected = {
        "all": {"gitleaks", "trivy", engine},
        "sast": {engine},
        "secrets": {"gitleaks"},
        "dependencies": {"trivy"},
    }[stage]
    return any(
        row["state"] == "finished"
        and row["phase"] in expected
        and set(row["scanners"]) == expected
        and all(
            scanner.get("report_state") == "json"
            and scanner["status"] not in {"tool_error", "partial"}
            and scanner.get("execution", {}).get("status") == "exited"
            and scanner["execution"].get("returncode") in ({0, 10} if name == "gitleaks" else {0})
            for name, scanner in row["scanners"].items()
        )
        for row in records
    )


def main():
    if sys.argv[1:] == ["--finish"]:
        if not LAUNCHER.is_file():
            return 0
        return subprocess.run(
            ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", str(LAUNCHER), "finish"], timeout=40
        ).returncode
    if sys.argv[1:]:
        raise SystemExit("unexpected entry arguments")
    stage = os.environ.get("SECURITY_STAGE", "all")
    if stage not in {"all", "sast", "secrets", "dependencies"}:
        raise SystemExit("unsupported audit stage")
    if not LAUNCHER.is_file():
        if (
            os.environ.get("RUNNER_ENVIRONMENT") == "self-hosted"
            and "claw" in os.environ.get("RUNNER_NAME", "").lower()
        ):
            raise SystemExit("Claw audit isolation is required but unavailable")
        os.execv(sys.executable, [sys.executable, "-E", "-s", str(HERE / "run.py")])
    return run_on_claw(stage)


def run_on_claw(stage):
    request = {
        "workspace": str(Path.cwd().resolve()),
        "script": str(HERE / "run.py"),
        "summary": os.environ.get("GITHUB_STEP_SUMMARY", ""),
        "engine": os.environ.get("SECURITY_ENGINE", "semgrep"),
        "base_sha": os.environ.get("SECURITY_BASE_SHA", ""),
    }
    if stage != "all":
        request["stage"] = stage
    command = ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", str(LAUNCHER)]

    def cancel(sig, frame):
        raise SystemExit(128 + sig)

    previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}
    process = None
    outcome, transported = None, False
    try:
        process = subprocess.Popen(command + ["run"], stdin=subprocess.PIPE, text=True)
        process.communicate(json.dumps(request))
        outcome = process.returncode
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        # This separate request survives cancellation of the blocking launch call;
        # the job-completed hook and host deadline also cover SIGKILL of this entry.
        if process is None or process.returncode != 73:
            subprocess.run(command + ["finish"], check=False, timeout=40)
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
            if process.returncode != 73:
                transported = forward_checkpoints(stage, request["engine"])
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if outcome == 0 and not transported:
        print("claw-audit: missing or incomplete safe checkpoints", file=sys.stderr)
        return 1
    return outcome if outcome is not None else 1


if __name__ == "__main__":
    sys.exit(main())
