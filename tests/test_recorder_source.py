from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from urllib.request import Request
from openplaud.recorder_source import State,CloudRecording,parse_recordings,sync_once,AuthRequired,SourceError,GoogleOnlyRedirects,LocalLibrary
ID='11111111-2222-4333-8444-555555555555'
SECOND='21111111-2222-4333-8444-555555555555'
class FakeSource:
    downloads=0
    def list(self):return [CloudRecording(ID,'Same title','2026-11-10T20:00:00+00:00',20),CloudRecording(SECOND,'Same title','2026-11-10T21:00:00+00:00',30)],False
    def download(self,record,path):self.downloads+=1;path.write_bytes(record.id.encode())
class FakeLibrary:
    def __init__(self):self.calls=[]
    def upload(self,path,record):self.calls.append((path.name,record.title,record.started_at));return 'a'*64
class RecorderSourceTests(unittest.TestCase):
    def test_metadata_uses_web_id_and_utc(self):
        item=[None]*14;item[0]=ID;item[1]='Synthetic title';item[2]=['1762804800',0];item[3]=['20',0];item[13]=SECOND
        rows,partial=parse_recordings([[item],'next'])
        self.assertEqual(rows[0].id,SECOND);self.assertTrue(rows[0].started_at.endswith('+00:00'));self.assertTrue(partial)
        with self.assertRaises(SourceError):parse_recordings({'unexpected':'schema'})
        broken=list(item);broken[13]='../../outside'
        with self.assertRaises(SourceError):parse_recordings([[broken]])
    def test_encrypted_session_and_missing_login(self):
        with tempfile.TemporaryDirectory() as root:
            s=State(root)
            with self.assertRaises(AuthRequired):s.auth()
            s.save_auth({'sapisid':'synthetic-secret','api_key':'synthetic-key'})
            self.assertEqual(s.auth()['sapisid'],'synthetic-secret')
            self.assertNotIn(b'synthetic-secret',(Path(root)/'auth.enc').read_bytes())
            self.assertEqual((Path(root)/'auth.key').stat().st_mode & 0o777,0o600)
    def test_same_titles_do_not_collide_and_repeated_sync_skips(self):
        with tempfile.TemporaryDirectory() as root:
            s=State(root);s.set_status('READY');source=FakeSource();library=FakeLibrary()
            self.assertEqual(sync_once(s,source,library)['imported'],2)
            sync_once(s,source,library);self.assertEqual(source.downloads,2)
            self.assertNotEqual(library.calls[0][0],library.calls[1][0])
            self.assertEqual(library.calls[0][1],library.calls[1][1])
    def test_auth_expiry_stops_future_attempts(self):
        class Expired(FakeSource):
            calls=0
            def list(self):self.calls+=1;raise AuthRequired()
        with tempfile.TemporaryDirectory() as root:
            s=State(root);s.set_status('READY');source=Expired();library=FakeLibrary()
            self.assertEqual(sync_once(s,source,library)['mode'],'AUTH_REQUIRED')
            sync_once(s,source,library);self.assertEqual(source.calls,1)
    def test_attempt_limits_and_remote_absence_never_delete(self):
        class Failed(FakeSource):
            def download(self,record,path):raise SourceError('fixture')
        with tempfile.TemporaryDirectory() as root:
            s=State(root);s.set_status('READY');source=Failed();library=FakeLibrary()
            for _ in range(5):sync_once(s,source,library)
            with s.db() as c:self.assertEqual(c.execute('SELECT max(attempts) FROM imports').fetchone()[0],3)
            for _ in range(5):s.failure()
            self.assertEqual(s.status()['mode'],'PAUSED')
            self.assertEqual(sync_once(s,source,library)['mode'],'PAUSED')
    def test_redirect_cannot_leak_google_cookies(self):
        policy=GoogleOnlyRedirects();request=Request('https://usercontent.recorder.google.com/file',headers={'Cookie':'synthetic-cookie'})
        with self.assertRaises(SourceError):policy.redirect_request(request,None,302,'',{},'https://attacker.example/file')
        with self.assertRaises(AuthRequired):policy.redirect_request(request,None,302,'',{},'https://accounts.google.com/')
        forwarded=policy.redirect_request(request,None,302,'',{},'https://blob.googleusercontent.com/file')
        self.assertIsNone(forwarded.get_header('Cookie'))
    def test_local_upload_target_restriction(self):
        for url in ('https://attacker.example','http://169.254.169.254','http://127.0.0.1/other'):
            with self.assertRaises(ValueError):LocalLibrary(url,'synthetic')
