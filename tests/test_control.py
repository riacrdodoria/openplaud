import io
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from openplaud.control import Store
from openplaud.recordings import Library
from openplaud.runner import tick,command
TASKS=[dict(id='one',title='One',phase=0,deps=[],acceptance=['evidence']),dict(id='two',title='Two',phase=1,deps=['one'],acceptance=['evidence'])]
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root/'db');self.store.seed(TASKS)
    def test_dependencies_and_review(self):
        self.assertIsNone(self.store.claim());self.store.control('resume')
        t,r=self.store.claim();self.assertEqual(t['id'],'one');self.assertIsNone(self.store.claim())
        self.store.finish('one',r,'REVIEW');self.assertIsNone(self.store.claim())
        self.store.control('review','one','approve');self.assertEqual(self.store.claim()[0]['id'],'two')
    def test_concurrent_claim(self):
        self.store.control('resume');results=[]
        ts=[threading.Thread(target=lambda:results.append(self.store.claim())) for _ in range(8)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(sum(r is not None for r in results),1)
    def test_restart_after_abrupt_exit(self):
        self.store.control('resume')
        script='from openplaud.control import Store; import os; Store('+repr(str(self.root/'db'))+').claim();os._exit(9)'
        self.assertEqual(subprocess.run([sys.executable,'-c',script]).returncode,9)
        fresh=Store(self.root/'db');fresh.recover();s=fresh.snapshot()
        self.assertEqual(s['tasks'][0]['state'],'BLOCKED');self.assertEqual(s['runs'][0]['status'],'INTERRUPTED')
        self.assertIsNone(fresh.claim())
    def test_authorization_gate(self):
        self.store.control('resume');tick(self.store,self.root,self.root,{})
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'BLOCKED')
        self.assertEqual(len(self.store.snapshot()['approvals']),1)
    def test_forbidden_actions(self):
        for action in ['shell','exec','approve-sensitive']:
            with self.assertRaises(ValueError):self.store.control(action,value='id')
        with self.assertRaises(ValueError):self.store.control('review','one','approve')
        with self.assertRaises(ValueError):self.store.control('priority','one',1000)
    def test_cycles(self):
        with self.assertRaises(ValueError):self.store.seed([dict(TASKS[0],deps=['one'])])
    def test_seed_idempotent(self):
        self.store.control('resume');self.store.claim();self.store.seed(TASKS)
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)
    def test_timeout(self):
        with self.assertRaises(subprocess.TimeoutExpired):command([sys.executable,'-c','import time;time.sleep(30)'],self.root,self.root/'log',0.1)
    def test_ingest_dedup_privacy(self):
        lib=Library(self.root/'library');a=lib.ingest(io.BytesIO(b'audio'),'../meeting.wav')
        self.assertEqual(a,lib.ingest(io.BytesIO(b'audio'),'other.wav'))
        self.assertEqual(len(lib.list()),1);self.assertEqual(lib.list()[0]['privacy'],'local-only')
        self.assertEqual(lib.audio_path(a).read_bytes(),b'audio')
    def test_ingest_limits_search_traversal(self):
        lib=Library(self.root/'library')
        for content in [b'',b'12345']:
            with self.assertRaises(ValueError):lib.ingest(io.BytesIO(content),'a',4)
        self.assertEqual(list((lib.root/'audio').iterdir()),[])
        with self.assertRaises(ValueError):lib.audio_path('../secrets')
        lib.ingest(io.BytesIO(b'1'),'Meeting.wav')
        self.assertEqual(len(lib.list('meeting')),1);self.assertEqual(len(lib.list("' OR 1=1 --")),0)
