"""Exercise real Git worktree/checkpoint flow with a fake offline Codex executable."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from openplaud.control import Store
from openplaud.runner import tick
class RunnerTests(unittest.TestCase):
    def test_offline_execution_checkpoints_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();state=root/'state';state.mkdir()
            def git(*args):return subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True,text=True)
            git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            (repo/'tests').mkdir();(repo/'tests'/'test_example.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(1+1,2)\n')
            git('add','.');git('commit','-m','fixture')
            bin=root/'bin';bin.mkdir();codex=bin/'codex'
            codex.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nif sys.argv[1:]==["login","status"]: print("Logged in using ChatGPT")\nelse: Path("feature.txt").write_text("implemented")\n')
            codex.chmod(0o700)
            store=Store(state/'control.sqlite');store.seed([dict(id='test',title='fixture',phase=0,acceptance=['feature exists'])]);store.control('resume')
            config=dict(subscription_usage_authorized=True,isolated_account_verified=True,max_invocations=10,timeout_seconds=900)
            with patch.dict(os.environ,{'PATH':str(bin)+os.pathsep+os.environ['PATH']}), patch('openplaud.runner.shutil.disk_usage',return_value=SimpleNamespace(free=20*1024**3)):
                self.assertTrue(tick(store,repo,state,config))
            snap=store.snapshot();self.assertEqual(snap['tasks'][0]['state'],'REVIEW',snap)
            self.assertEqual(snap['tasks'][0]['attempts'],1)
            self.assertNotEqual(snap['runs'][0]['before_sha'],snap['runs'][0]['after_sha'])
            self.assertFalse((repo/'feature.txt').exists())
            self.assertEqual((state/'trees'/'1'/'feature.txt').read_text(),'implemented')
            self.assertIsNone(store.claim())

    def test_low_disk_blocks_before_auth_or_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=Store(root/'control.sqlite')
            store.seed([dict(id='disk',title='disk',phase=0,acceptance=['fixture'])]);store.control('resume')
            config=dict(subscription_usage_authorized=True,isolated_account_verified=True,max_invocations=10)
            with patch('openplaud.runner.shutil.disk_usage',return_value=SimpleNamespace(free=1024)), patch('openplaud.runner.subprocess.run') as proc:
                tick(store,root,root,config)
                proc.assert_not_called()
            self.assertEqual(store.snapshot()['tasks'][0]['state'],'BLOCKED')
            self.assertIn('10 GiB',store.snapshot()['tasks'][0]['error'])
