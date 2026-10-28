"""Use claw's bounded host service, or direct execution on hosted runners."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

HERE=Path(__file__).resolve().parent
LAUNCHER=Path('/usr/local/lib/claw-memory/audit_launcher.py')


def main():
    if sys.argv[1:] == ['--finish']:
        if not LAUNCHER.is_file():return 0
        return subprocess.run(['/usr/bin/sudo','-n','/usr/bin/python3','-I',str(LAUNCHER),'finish'],timeout=40).returncode
    if sys.argv[1:]:raise SystemExit('unexpected entry arguments')
    if not LAUNCHER.is_file():
        if os.environ.get('RUNNER_ENVIRONMENT')=='self-hosted' and 'claw' in os.environ.get('RUNNER_NAME','').lower():
            raise SystemExit('Claw audit isolation is required but unavailable')
        os.execv(sys.executable,[sys.executable,'-E','-s',str(HERE/'run.py')])
    request={'workspace':str(Path.cwd().resolve()),'script':str(HERE/'run.py'),
             'summary':os.environ.get('GITHUB_STEP_SUMMARY',''),
             'engine':os.environ.get('SECURITY_ENGINE','semgrep'),
             'base_sha':os.environ.get('SECURITY_BASE_SHA','')}
    command=['/usr/bin/sudo','-n','/usr/bin/python3','-I',str(LAUNCHER)]
    def cancel(sig,frame):raise SystemExit(128+sig)
    previous={sig:signal.signal(sig,cancel) for sig in (signal.SIGTERM,signal.SIGINT)}
    process=None
    try:
        process=subprocess.Popen(command+['run'],stdin=subprocess.PIPE,text=True)
        process.communicate(json.dumps(request))
        return process.returncode
    finally:
        for sig in previous:signal.signal(sig,signal.SIG_IGN)
        # This separate request survives cancellation of the blocking launch call;
        # the job-completed hook and host deadline also cover SIGKILL of this entry.
        if process is None or process.returncode != 73:
            subprocess.run(command+['finish'],check=False,timeout=40)
        if process is not None:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.terminate()
        for sig,handler in previous.items():signal.signal(sig,handler)


if __name__=='__main__':sys.exit(main())
