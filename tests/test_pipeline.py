import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from openplaud.recordings import Library
from openplaud.providers import Transcript,Segment
from openplaud.worker import process,import_inbox
from openplaud.analysis import answer
from openplaud.calendar import import_ics,match,review
from openplaud.google_calendar import GoogleCalendar,SCOPE
from openplaud.backup import backup,verify
from openplaud.llm import summarize

class FakeProvider:
    external=False
    def transcribe(self,audio,language):
        return Transcript('pt',(Segment(0,1200,'Decidimos aprovar o orçamento.'),Segment(1500,3000,'Vou enviar a proposta amanhã.')),'fixture')

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.lib=Library(self.root/'library');self.key=self.lib.ingest(io.BytesIO(b'synthetic audio'),'Fixture.wav')
    def test_complete_pipeline_search_evidence_and_review(self):
        process(self.lib,self.lib.claim(),FakeProvider())
        d=self.lib.detail(self.key);self.assertEqual(d['status'],'DONE')
        self.assertEqual(d['analysis']['decisions'][0]['segment_index'],0)
        self.assertEqual(d['analysis']['action_items'][0]['segment_index'],1)
        self.assertEqual(len(self.lib.list('orçamento')),1)
        response=answer(self.lib,'orcamento')
        self.assertEqual(response['citations'][0]['start_ms'],0)
        self.assertEqual(response['citations'][0]['recording_id'],self.key)
        self.lib.review_action(self.key,0,True)
        self.assertTrue(self.lib.detail(self.key)['analysis']['action_items'][0]['confirmed'])
        self.assertEqual(answer(self.lib,'orçamento',[])['citations'],[])
    def test_concurrent_audio_claim(self):
        results=[];threads=[threading.Thread(target=lambda:results.append(self.lib.claim())) for _ in range(6)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(x is not None for x in results),1)
    def test_restart_and_bounded_attempts(self):
        for _ in range(3):
            self.assertIsNotNone(self.lib.claim());self.lib.recover()
        self.assertEqual(self.lib.detail(self.key)['status'],'FAILED');self.assertIsNone(self.lib.claim())
        with self.assertRaises(ValueError):self.lib.retry(self.key)
    def test_analysis_failure_does_not_lose_transcript(self):
        job=self.lib.claim()
        with patch('openplaud.llm.summarize',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):process(self.lib,job,FakeProvider())
        self.lib.fail(self.key,'ANALYSIS_FAILED');self.assertIsNotNone(self.lib.detail(self.key)['transcript'])
        self.lib.retry(self.key);job=self.lib.claim()
        with patch.object(FakeProvider,'transcribe',side_effect=AssertionError('must reuse transcript')):process(self.lib,job,FakeProvider())
        self.assertEqual(self.lib.detail(self.key)['status'],'DONE')
    def test_inbox_stable_only_dedup_and_no_symlink(self):
        inbox=self.root/'inbox';inbox.mkdir();p=inbox/'recording.wav';p.write_bytes(b'fixture2')
        self.assertEqual(import_inbox(self.lib,inbox),0)
        os.utime(p,(time.time()-60,time.time()-60));(inbox/'link.wav').symlink_to(p)
        self.assertEqual(import_inbox(self.lib,inbox),1);import_inbox(self.lib,inbox)
        self.assertEqual(len(self.lib.list()),2)
    def test_old_database_preserved(self):
        # Existing V1 recordings are migrated in place without destructive DDL.
        old=self.root/'old';old.mkdir()
        with sqlite3.connect(old/'library.sqlite') as c:
            c.executescript("CREATE TABLE recordings(id TEXT PRIMARY KEY,name TEXT NOT NULL,bytes INTEGER NOT NULL,privacy TEXT DEFAULT 'local-only',created REAL NOT NULL);CREATE TABLE jobs(recording_id TEXT PRIMARY KEY,state TEXT DEFAULT 'QUEUED',attempts INTEGER DEFAULT 0,error TEXT);")
            c.execute('INSERT INTO recordings VALUES(?,?,?,?,?)',(self.key,'old.wav',12,'local-only',1));c.execute('INSERT INTO jobs(recording_id) VALUES(?)',(self.key,))
        migrated=Library(old);self.assertEqual(migrated.detail(self.key)['name'],'old.wav')
    def test_backup_restore_and_corruption(self):
        dest=self.root/'backup';self.assertEqual(backup(self.lib,dest),1)
        restored=Library(dest);self.assertEqual(restored.detail(self.key)['name'],'Fixture.wav')
        (dest/'audio'/self.key).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):verify(dest)
    def test_calendar_timezone_and_human_review(self):
        ics=b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:fixture\r\nDTSTART:20261110T150000Z\r\nDTEND:20261110T160000Z\r\nSUMMARY:Fixture meeting\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
        self.assertEqual(import_ics(self.lib,ics,'work')['imported'],1)
        self.lib.annotate(self.key,'2026-11-10T12:05:00-03:00','fixture')
        matches=match(self.lib,self.key);self.assertEqual(len(matches),1);self.assertEqual(matches[0]['state'],'SUGGESTED')
        review(self.lib,self.key,matches[0]['id'],'REJECTED');match(self.lib,self.key)
        self.assertEqual(self.lib.detail(self.key)['calendar_matches'][0]['state'],'REJECTED')
        self.lib.annotate(self.key,'2026-11-12T12:05:00-03:00','fixture');match(self.lib,self.key)
        self.assertEqual(self.lib.detail(self.key)['calendar_matches'][0]['state'],'REJECTED')
        with self.assertRaises(ValueError):self.lib.annotate(self.key,'2026-11-10T12:05:00')
    def test_invalid_llm_citation_falls_back(self):
        segments=[dict(index=0,start_ms=0,end_ms=1000,text='Literal evidence.')]
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://127.0.0.1:11434'}),patch('openplaud.llm.generate',return_value={'highlights':[{'text':'fabricated','segment_index':99}]}):
            result=summarize(segments)
        self.assertEqual(result['method'],'mixed-local');self.assertEqual(result['summary'],'Literal evidence.')

class OAuthTests(unittest.TestCase):
    def test_oauth_pkce_encryption_and_state_replay(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OPENPLAUD_GOOGLE_CLIENT_ID':'fixture-id','OPENPLAUD_GOOGLE_CLIENT_SECRET':'fixture-secret','OPENPLAUD_GOOGLE_REDIRECT_URI':'http://localhost:8767/oauth/google/callback','OPENPLAUD_TOKEN_KEY':Fernet.generate_key().decode()}):
            from urllib.parse import urlparse,parse_qs
            lib=Library(tmp);g=GoogleCalendar(lib);url=g.authorize('fixture-account');query=parse_qs(urlparse(url).query)
            self.assertEqual(query['scope'],[SCOPE]);self.assertEqual(query['code_challenge_method'],['S256'])
            token={'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_in':3600}
            with patch.object(g,'exchange',return_value=token):self.assertEqual(g.callback(query['state'][0],'fixture-code'),'fixture-account')
            with lib.connect() as c:encrypted=c.execute('SELECT encrypted_token FROM calendar_connections').fetchone()[0]
            self.assertNotIn(b'synthetic-refresh',encrypted)
            with self.assertRaises(ValueError):g.callback(query['state'][0],'fixture-code')
            self.assertEqual(g.connections()[0]['account'],'fixture-account')

class SummaryCoverageTests(unittest.TestCase):
    def test_chunked_summary_preserves_global_evidence_indices(self):
        segments=[{'index':i,'start_ms':i*1000,'end_ms':i*1000+900,'text':('Palavras sintéticas de teste. '*100)} for i in range(7)]
        def generated(prompt,timeout,indices):
            return {'highlights':[{'text':'Resumo sintético','segment_index':indices[-1]}],'decisions':[],'action_items':[]}
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://127.0.0.1:11434'}),patch('openplaud.llm.generate',side_effect=generated) as gen:
            result=summarize(segments)
        self.assertGreater(gen.call_count,1);self.assertEqual(result['coverage'],'full')
        self.assertEqual(result['highlights'][-1]['segment_index'],6)
        self.assertTrue(all(x['segment_index'] in range(7) for x in result['highlights']))
