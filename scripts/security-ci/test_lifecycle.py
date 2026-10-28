"""Exercise actual subprocess trees; no downloaded scanner or target code."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('audit_lifecycle',Path(__file__).with_name('run.py'))
        self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.child=self.root/'child.py';self.pidfile=self.root/'pid'
        self.child.write_text('import os,signal,time,pathlib\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\npathlib.Path('+repr(str(self.pidfile))+').write_text(str(os.getpid()))\nwhile True:time.sleep(.05)\n')
    def alive(self,pid):
        try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
        except FileNotFoundError:return False
    def args(self,hold):
        text='import subprocess,sys,time\np=subprocess.Popen([sys.executable,'+repr(str(self.child))+'])\nwhile not __import__("pathlib").Path('+repr(str(self.pidfile))+').exists():time.sleep(.01)\n'
        if hold:text+='time.sleep(60)\n'
        return [sys.executable,'-c',text]
    def assert_child_gone(self):
        pid=int(self.pidfile.read_text());self.addCleanup(lambda:os.kill(pid,signal.SIGKILL) if self.alive(pid) else None)
        deadline=time.monotonic()+1
        while self.alive(pid) and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.alive(pid),'scanner grandchild survived cleanup')
    def test_timeout_kills_term_ignoring_grandchild(self):
        with patch.object(self.mod,'STOP_GRACE_SECONDS',.15,create=True):
            self.assertEqual(self.mod.command(self.args(True),self.root/'log',timeout=.3),124)
        self.assert_child_gone()
    def test_success_collects_leftover_child(self):
        with patch.object(self.mod,'STOP_GRACE_SECONDS',.15,create=True):
            self.assertEqual(self.mod.command(self.args(False),self.root/'log',timeout=3),0)
        self.assert_child_gone()
    def test_term_cancellation_cleans_child_before_exit(self):
        script=self.root/'parent.py';script.write_text('import sys\nsys.path.insert(0,'+repr(str(Path(__file__).parent.resolve()))+')\nimport run\nrun.STOP_GRACE_SECONDS=.15\nrun.command('+repr(self.args(True))+','+'__import__("pathlib").Path('+repr(str(self.root/'log'))+'),timeout=60)\n')
        p=subprocess.Popen([sys.executable,str(script)])
        self.addCleanup(lambda:p.kill() if p.poll() is None else None)
        deadline=time.monotonic()+5
        while not self.pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(self.pidfile.exists());p.terminate();p.wait(timeout=4)
        self.assertNotEqual(p.returncode,0);self.assert_child_gone()
