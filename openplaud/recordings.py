"""Single-user local library. SQLite transactions are the job/metadata boundary."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

class Library:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        (self.root/'audio').mkdir(exist_ok=True,mode=0o700)
        self.db=self.root/'library.sqlite'
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS recordings(id TEXT PRIMARY KEY,name TEXT NOT NULL,
              bytes INTEGER NOT NULL,privacy TEXT DEFAULT 'local-only',created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(recording_id TEXT PRIMARY KEY,state TEXT DEFAULT 'QUEUED',
              attempts INTEGER DEFAULT 0,error TEXT);
            CREATE TABLE IF NOT EXISTS transcripts(recording_id TEXT PRIMARY KEY,language TEXT NOT NULL,
              provider TEXT NOT NULL,segments TEXT NOT NULL,updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS analyses(recording_id TEXT PRIMARY KEY,content TEXT NOT NULL,updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS annotations(recording_id TEXT PRIMARY KEY,started_at TEXT,notes TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS calendar_events(id TEXT PRIMARY KEY,account TEXT NOT NULL,title TEXT NOT NULL,
              starts TEXT NOT NULL,ends TEXT NOT NULL,participants TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calendar_matches(recording_id TEXT NOT NULL,event_id TEXT NOT NULL,
              state TEXT NOT NULL DEFAULT 'SUGGESTED',score REAL NOT NULL,PRIMARY KEY(recording_id,event_id));
            CREATE VIRTUAL TABLE IF NOT EXISTS segment_search USING fts5(recording_id UNINDEXED,
              segment_index UNINDEXED,text,tokenize='unicode61 remove_diacritics 2');
            CREATE TABLE IF NOT EXISTS inbox_seen(path TEXT PRIMARY KEY,size INTEGER NOT NULL,mtime_ns INTEGER NOT NULL,recording_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS diarizations(recording_id TEXT PRIMARY KEY,state TEXT NOT NULL,content TEXT,error TEXT,updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied REAL NOT NULL);
            INSERT OR IGNORE INTO schema_migrations VALUES(1,strftime('%s','now'));
            ''')
    @contextlib.contextmanager
    def connect(self):
        c=sqlite3.connect(self.db,timeout=15);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:yield c
        finally:c.close()
    @staticmethod
    def valid_key(key):return isinstance(key,str) and len(key)==64 and all(x in '0123456789abcdef' for x in key)
    def audio_path(self,key):
        if not self.valid_key(key):raise ValueError('invalid id')
        return self.root/'audio'/key
    def ingest(self,stream,name,max_bytes=100*1024*1024):
        if not isinstance(name,str) or not 1<=len(name)<=255 or any(ord(x)<32 for x in name):raise ValueError('invalid name')
        digest=hashlib.sha256();size=0
        fd,tmp=tempfile.mkstemp(dir=self.root/'audio')
        try:
            with os.fdopen(fd,'wb') as out:
                while block:=stream.read(65536):
                    size+=len(block)
                    if size>max_bytes:raise ValueError('file too large')
                    digest.update(block);out.write(block)
                if not size:raise ValueError('empty file')
                out.flush();os.fsync(out.fileno())
            key=digest.hexdigest();target=self.audio_path(key)
            try:os.link(tmp,target)
            except FileExistsError:pass
            directory=os.open(self.root/'audio',os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
            with self.connect() as c:
                c.execute('INSERT OR IGNORE INTO recordings VALUES(?,?,?,\'local-only\',?)',(key,name,size,time.time()))
                c.execute('INSERT OR IGNORE INTO jobs(recording_id) VALUES(?)',(key,))
            return key
        finally:Path(tmp).unlink(missing_ok=True)
    def list(self,query='',limit=100,offset=0):
        if not 1<=limit<=100 or offset<0:raise ValueError('invalid pagination')
        with self.connect() as c:
            return [dict(r) for r in c.execute('''SELECT r.*,j.state AS status,j.attempts,j.error,
            a.started_at FROM recordings r JOIN jobs j ON j.recording_id=r.id
            LEFT JOIN annotations a ON a.recording_id=r.id
            WHERE instr(lower(r.name),lower(?))>0 OR EXISTS(SELECT 1 FROM segment_search s
            WHERE s.recording_id=r.id AND instr(lower(s.text),lower(?))>0)
            ORDER BY r.created DESC LIMIT ? OFFSET ?''',(query,query,limit,offset))]
    def detail(self,key):
        if not self.valid_key(key):return None
        with self.connect() as c:
            r=c.execute('''SELECT r.*,j.state AS status,j.attempts,j.error,a.started_at,a.notes
            FROM recordings r JOIN jobs j ON j.recording_id=r.id
            LEFT JOIN annotations a ON a.recording_id=r.id WHERE r.id=?''',(key,)).fetchone()
            if not r:return None
            result=dict(r)
            t=c.execute('SELECT * FROM transcripts WHERE recording_id=?',(key,)).fetchone()
            result['transcript']={'language':t['language'],'provider':t['provider'],'segments':json.loads(t['segments'])} if t else None
            a=c.execute('SELECT content FROM analyses WHERE recording_id=?',(key,)).fetchone()
            result['analysis']=json.loads(a[0]) if a else None
            speaker=c.execute('SELECT state,content,error FROM diarizations WHERE recording_id=?',(key,)).fetchone()
            result['diarization']={'state':speaker['state'],'error':speaker['error'],**(json.loads(speaker['content']) if speaker['content'] else {})} if speaker else {'state':'NOT_REQUESTED'}
            if speaker and speaker['state']=='DONE' and result['transcript']:
                from .diarization import assign_speakers
                result['transcript']['segments']=assign_speakers(result['transcript']['segments'],result['diarization']['turns'])
            result['calendar_matches']=[dict(e) for e in c.execute('''SELECT e.*,m.state,m.score FROM calendar_matches m
            JOIN calendar_events e ON e.id=m.event_id WHERE m.recording_id=? ORDER BY m.score DESC''',(key,))]
            return result
    def claim(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute("SELECT r.* FROM jobs j JOIN recordings r ON r.id=j.recording_id WHERE j.state='QUEUED' AND j.attempts<3 ORDER BY r.created LIMIT 1").fetchone()
            if row:
                c.execute("UPDATE jobs SET state='TRANSCRIBING',attempts=attempts+1,error=NULL WHERE recording_id=?",(row['id'],))
                return dict(row)
    def recover(self):
        # Only while holding the single worker OS lock; never run from API startup.
        with self.connect() as c:
            c.execute("UPDATE diarizations SET state='FAILED',error='DIARIZATION_INTERRUPTED' WHERE state='RUNNING'")
            c.execute("UPDATE jobs SET state=CASE WHEN attempts<3 THEN 'QUEUED' ELSE 'FAILED' END,error='Processing interrupted' WHERE state IN ('TRANSCRIBING','ANALYZING')")
    def save_transcript(self,key,transcript):
        from dataclasses import asdict
        segments=[dict(asdict(s),index=i) for i,s in enumerate(transcript.segments)]
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO transcripts VALUES(?,?,?,?,?)',(key,transcript.language,transcript.provider,json.dumps(segments,ensure_ascii=False),time.time()))
            c.execute('DELETE FROM segment_search WHERE recording_id=?',(key,))
            c.executemany('INSERT INTO segment_search(recording_id,segment_index,text) VALUES(?,?,?)',[(key,i,s['text']) for i,s in enumerate(segments)])
            c.execute("UPDATE jobs SET state='ANALYZING' WHERE recording_id=?",(key,))
    def save_analysis(self,key,analysis):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO analyses VALUES(?,?,?)',(key,json.dumps(analysis,ensure_ascii=False),time.time()))
            c.execute("UPDATE jobs SET state='DONE',error=NULL WHERE recording_id=?",(key,))
    def fail(self,key,error):
        # Persist a safe error code, never raw provider exception text or transcript.
        with self.connect() as c:c.execute("UPDATE jobs SET state='FAILED',error=? WHERE recording_id=?",(error,key))
    def retry(self,key):
        with self.connect() as c:
            changed=c.execute("UPDATE jobs SET state='QUEUED',error=NULL WHERE recording_id=? AND state='FAILED' AND attempts<3",(key,)).rowcount
            if not changed:raise ValueError('not failed or attempt limit reached')
    def annotate(self,key,started_at=None,notes=''):
        from datetime import datetime
        if started_at:
            d=datetime.fromisoformat(started_at.replace('Z','+00:00'))
            if d.tzinfo is None:raise ValueError('timezone required')
        if len(notes)>4000:raise ValueError('notes too long')
        if not self.detail(key):raise ValueError('not found')
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO annotations VALUES(?,?,?)',(key,started_at,notes))
    def search_segments(self,query,keys=None,limit=12):
        words=re.findall(r'\w+',query,flags=re.UNICODE)[:30]
        if not words:return []
        match=' OR '.join('"'+w.replace('"','""')+'"' for w in words)
        params=[match];scope=''
        if keys is not None:
            if not keys:return []
            scope=' AND s.recording_id IN ('+','.join('?' for _ in keys)+')';params.extend(keys)
        params.append(limit)
        with self.connect() as c:
            return [dict(r) for r in c.execute('''SELECT s.recording_id,s.segment_index,s.text,r.name
            FROM segment_search s JOIN recordings r ON r.id=s.recording_id
            WHERE segment_search MATCH ?'''+scope+' ORDER BY rank LIMIT ?',params)]
    def review_action(self,key,index,confirmed):
        return self.update_action(key,index,{'confirmed':confirmed})
    def update_action(self,key,index,changes):
        if not set(changes)<= {'confirmed','text','owner_suggestion','due_at'}:raise ValueError('invalid action fields')
        if 'confirmed' in changes and type(changes['confirmed']) is not bool:raise ValueError('invalid confirmation')
        if 'text' in changes and (not isinstance(changes['text'],str) or not 1<=len(changes['text'])<=1500):raise ValueError('invalid task text')
        if changes.get('owner_suggestion') is not None and (not isinstance(changes['owner_suggestion'],str) or len(changes['owner_suggestion'])>200):raise ValueError('invalid owner')
        if changes.get('due_at'):
            from datetime import date
            date.fromisoformat(changes['due_at'])
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT content FROM analyses WHERE recording_id=?',(key,)).fetchone()
            if not row:raise ValueError('analysis unavailable')
            data=json.loads(row[0]);actions=data.get('action_items',[])
            if not 0<=index<len(actions):raise ValueError('action unavailable')
            actions[index].update(changes)
            c.execute('UPDATE analyses SET content=?,updated=? WHERE recording_id=?',(json.dumps(data,ensure_ascii=False),time.time(),key))

    def queue_speakers(self,key):
        if not self.detail(key):raise ValueError('not found')
        with self.connect() as c:
            c.execute("INSERT INTO diarizations(recording_id,state,updated) VALUES(?,'QUEUED',?) ON CONFLICT(recording_id) DO UPDATE SET state='QUEUED',error=NULL,updated=excluded.updated WHERE diarizations.state IN ('FAILED','NOT_REQUESTED')",(key,time.time()))
    def claim_speakers(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute("SELECT d.recording_id FROM diarizations d JOIN transcripts t ON t.recording_id=d.recording_id WHERE d.state='QUEUED' ORDER BY d.updated LIMIT 1").fetchone()
            if row:
                c.execute("UPDATE diarizations SET state='RUNNING',updated=? WHERE recording_id=?",(time.time(),row[0]))
                return row[0]
    def save_speakers(self,key,data):
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO diarizations VALUES(?,'DONE',?,NULL,?)",(key,json.dumps(data,ensure_ascii=False),time.time()))
    def fail_speakers(self,key,error):
        with self.connect() as c:
            c.execute("UPDATE diarizations SET state='FAILED',error=?,updated=? WHERE recording_id=?",(error,time.time(),key))
