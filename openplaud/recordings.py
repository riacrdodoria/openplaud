"""Immutable local ingestion with hash deduplication and transactional jobs."""
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import time

class Library:
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        (self.root/'audio').mkdir(exist_ok=True,mode=0o700)
        self.db=self.root/'library.sqlite'
        with sqlite3.connect(self.db) as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS recordings(id TEXT PRIMARY KEY,name TEXT NOT NULL,
            bytes INTEGER NOT NULL,privacy TEXT DEFAULT 'local-only',created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(recording_id TEXT PRIMARY KEY,state TEXT DEFAULT 'QUEUED',
            attempts INTEGER DEFAULT 0,error TEXT);''')
    def ingest(self, stream, name, max_bytes=100*1024*1024):
        if not isinstance(name,str) or not 1<=len(name)<=255 or any(ord(x)<32 for x in name):
            raise ValueError('invalid name')
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
            key=digest.hexdigest();target=self.root/'audio'/key
            try:os.link(tmp,target)
            except FileExistsError:pass
            directory=os.open(self.root/'audio',os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
            with sqlite3.connect(self.db,timeout=10) as c:
                c.execute('INSERT OR IGNORE INTO recordings VALUES(?,?,?,\'local-only\',?)',(key,name,size,time.time()))
                c.execute('INSERT OR IGNORE INTO jobs(recording_id) VALUES(?)',(key,))
            return key
        finally:Path(tmp).unlink(missing_ok=True)
    def list(self,query='',limit=100):
        if not 1<=limit<=100:raise ValueError('invalid limit')
        with sqlite3.connect(self.db) as c:
            c.row_factory=sqlite3.Row
            return [dict(r) for r in c.execute('SELECT * FROM recordings WHERE instr(lower(name),lower(?))>0 ORDER BY created DESC LIMIT ?',(query,limit))]
    def audio_path(self,key):
        if len(key)!=64 or any(x not in '0123456789abcdef' for x in key):raise ValueError('invalid id')
        return self.root/'audio'/key
