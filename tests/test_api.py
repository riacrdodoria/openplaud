import io
from pathlib import Path
import tempfile
import unittest
import wave
from fastapi.testclient import TestClient
from openplaud.api import create_app
class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.headers={'Authorization':'Bearer '+'x'*40,'Content-Type':'application/octet-stream'}
        self.client=TestClient(create_app(self.tmp.name,'x'*40))
        audio=io.BytesIO()
        with wave.open(audio,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x00\x00'*160)
        self.audio=audio.getvalue()
    def test_auth(self):
        self.assertEqual(self.client.get('/api/recordings').status_code,401)
        self.assertEqual(self.client.get('/api/recordings',headers={b'Authorization':b'Bearer caf\xe9'}).status_code,401)
        self.assertEqual(self.client.post('/api/recordings?name=a',content=self.audio).status_code,401)
    def test_upload_search_dedup_range(self):
        ids=[]
        for _ in range(2):
            r=self.client.post('/api/recordings?name=Meeting.wav',content=self.audio,headers=self.headers)
            self.assertEqual(r.status_code,201);ids.append(r.json()['id'])
        self.assertEqual(ids[0],ids[1])
        rows=self.client.get('/api/recordings?q=meeting',headers=self.headers).json()
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['privacy'],'local-only')
        r=self.client.get('/api/recordings/'+ids[0]+'/audio',headers={**self.headers,'Range':'bytes=0-9'})
        self.assertEqual(r.status_code,206);self.assertEqual(r.content,self.audio[:10])
        self.assertEqual(self.client.get('/api/recordings/'+ids[0]+'/audio').status_code,401)
    def test_bad_format_and_crosssite(self):
        r=self.client.post('/api/recordings?name=a',content=b'not audio',headers=self.headers)
        self.assertEqual(r.status_code,422)
        self.assertEqual(self.client.get('/api/recordings',headers={**self.headers,'Sec-Fetch-Site':'cross-site'}).status_code,403)
        self.assertEqual(list((Path(self.tmp.name)/'audio').iterdir()),[])
    def test_token_required(self):
        with self.assertRaises(ValueError):create_app(self.tmp.name,'short')
