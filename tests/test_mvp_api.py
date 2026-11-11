import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
from fastapi.testclient import TestClient
from openplaud.api import create_app
from openplaud.recordings import Library
from openplaud.worker import process
from openplaud.providers import Transcript,Segment

class Provider:
    external=False
    def transcribe(self,audio,language):return Transcript('pt',(Segment(0,1000,'Decidimos aprovar orçamento.'),Segment(1000,2500,'Vou enviar a proposta.')),'fixture')
class MVPAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=TestClient(create_app(self.tmp.name,'z'*40));self.lib=Library(self.tmp.name)
        self.header={'Authorization':'Bearer '+'z'*40}
        raw=io.BytesIO()
        with wave.open(raw,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*160)
        self.audio=raw.getvalue()
    def upload(self):
        r=self.client.post('/api/recordings?name=fixture.wav',headers={**self.header,'Content-Type':'application/octet-stream'},content=self.audio)
        self.assertEqual(r.status_code,201);return r.json()['id']
    def test_browser_session_range_and_logout(self):
        key=self.upload()
        r=self.client.post('/api/session',headers=self.header);self.assertEqual(r.status_code,200)
        self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=strict',r.headers['set-cookie'])
        r=self.client.get('/api/recordings/'+key+'/audio',headers={'Range':'bytes=0-8'})
        self.assertEqual(r.status_code,206);self.assertEqual(r.content,self.audio[:9])
        self.assertEqual(self.client.post('/api/logout').status_code,200)
        self.assertEqual(self.client.get('/api/recordings/'+key).status_code,401)
    def test_pipeline_to_detail_export_chat_and_action(self):
        key=self.upload();process(self.lib,self.lib.claim(),Provider())
        d=self.client.get('/api/recordings/'+key,headers=self.header).json()
        self.assertEqual(d['status'],'DONE');self.assertEqual(len(d['transcript']['segments']),2)
        r=self.client.post('/api/chat',headers=self.header,json={'question':'orcamento','recording_ids':[key]})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['citations'][0]['recording_id'],key)
        r=self.client.patch('/api/recordings/'+key+'/actions/0',headers=self.header,json={'confirmed':True})
        self.assertTrue(r.json()['analysis']['action_items'][0]['confirmed'])
        r=self.client.patch('/api/recordings/'+key+'/actions/0',headers=self.header,json={'owner_suggestion':'Responsável de teste','due_at':'2026-11-12','text':'Enviar proposta revisada'})
        task=r.json()['analysis']['action_items'][0]
        self.assertTrue(task['confirmed']);self.assertEqual(task['owner_suggestion'],'Responsável de teste');self.assertEqual(task['segment_index'],1)
        self.assertIn('WEBVTT',self.client.get('/api/recordings/'+key+'/export?format=vtt',headers=self.header).text)
        self.assertIn('Decidimos',self.client.get('/api/recordings/'+key+'/export?format=txt',headers=self.header).text)
    def test_retry_and_not_found(self):
        key=self.upload()
        self.assertEqual(self.client.post('/api/recordings/'+key+'/retry',headers=self.header).status_code,409)
        self.lib.fail(key,'fixture');self.assertEqual(self.client.post('/api/recordings/'+key+'/retry',headers=self.header).status_code,200)
        self.assertEqual(self.client.get('/api/recordings/'+'f'*64,headers=self.header).status_code,404)
    def test_assets_safe_and_oauth_gate(self):
        self.assertEqual(self.client.get('/assets/app.js').status_code,200)
        self.assertIn("script-src 'self'",self.client.get('/').headers['content-security-policy'])
        self.assertEqual(self.client.get('/assets/secrets.env').status_code,404)
        self.assertEqual(self.client.post('/api/calendar/google/connect?account=fixture',headers=self.header).status_code,409)
        self.assertEqual(self.client.get('/oauth/google/callback?state=bad&code=bad',headers={'Sec-Fetch-Site':'cross-site'}).status_code,400)
        with patch('openplaud.google_calendar.GoogleCalendar.callback',return_value='fixture'):
            self.assertEqual(self.client.get('/oauth/google/callback?state=fixture&code=fixture',headers={'Sec-Fetch-Site':'cross-site'},follow_redirects=False).status_code,303)
        self.assertEqual(self.client.get('/',headers={'Host':'untrusted.example'}).status_code,400)

    def test_chunked_json_limit(self):
        def stream():
            yield b'{"question":"'
            for _ in range(34):yield b'a'*65536
            yield b'"}'
        r=self.client.post('/api/chat',headers=self.header,content=stream())
        self.assertEqual(r.status_code,413)

    def test_speaker_queue_auth_export_and_preserved_analysis(self):
        key=self.upload();process(self.lib,self.lib.claim(),Provider())
        path='/api/recordings/'+key+'/speakers'
        self.assertEqual(self.client.post(path).status_code,401)
        self.assertEqual(self.client.post(path,headers=self.header).status_code,409)
        with patch.dict('os.environ',{'OPENPLAUD_DIARIZATION_ENABLED':'1'}):
            self.assertEqual(self.client.post(path,headers=self.header).json()['diarization']['state'],'QUEUED')
        original=self.lib.detail(key)['analysis']
        self.lib.save_speakers(key,{'turns':[{'start_ms':0,'end_ms':2500,'speaker':'Falante 1'}],'speaker_count':1})
        self.assertEqual(self.lib.detail(key)['analysis'],original)
        self.assertIn('Falante 1',self.client.get('/api/recordings/'+key+'/export?format=vtt',headers=self.header).text)
        with patch.dict('os.environ',{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate',return_value={'claims':[{'text':'Orçamento aprovado.','source_ids':[0]}]}):
            response=self.client.post('/api/chat',headers=self.header,json={'question':'orçamento','recording_ids':[key],'history':['O que foi discutido?']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['method'],'local-grounded-chat-v1')
        self.assertEqual(response.json()['citations'][0]['speaker'],'Falante 1')
