"""Durable roadmap state. No commands can be supplied through the web API."""
import contextlib
import json
import sqlite3
import time
from pathlib import Path

STATES = ('BACKLOG', 'READY', 'RUNNING', 'TESTING', 'REVIEW', 'DONE', 'BLOCKED', 'FAILED')

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, phase INTEGER NOT NULL,
              state TEXT NOT NULL DEFAULT 'BACKLOG', priority INTEGER DEFAULT 0,
              deps TEXT NOT NULL DEFAULT '[]', acceptance TEXT NOT NULL,
              attempts INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 2,
              error TEXT, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
              id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, started REAL NOT NULL,
              ended REAL, status TEXT NOT NULL, before_sha TEXT, after_sha TEXT,
              log TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO settings VALUES ('mode','paused');
            CREATE TABLE IF NOT EXISTS approvals (
              id INTEGER PRIMARY KEY, task_id TEXT, action TEXT NOT NULL,
              state TEXT DEFAULT 'PENDING', created REAL NOT NULL, resolved REAL);
            ''')
    @contextlib.contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()
    def event(self, c, kind, payload):
        c.execute('INSERT INTO events(at,kind,payload) VALUES(?,?,?)',
                  (time.time(), kind, json.dumps(payload, ensure_ascii=False)))
    def seed(self, tasks):
        ids = {t['id'] for t in tasks}
        if len(ids) != len(tasks):
            raise ValueError('duplicate task ids')
        graph = {t['id']: t.get('deps', []) for t in tasks}
        def visit(key, trail):
            if key not in ids or key in trail:
                raise ValueError('missing or cyclic dependency')
            for dep in graph[key]:
                visit(dep, trail | {key})
        for key in ids:
            visit(key, set())
        with self.db() as c:
            for t in tasks:
                c.execute('''INSERT OR IGNORE INTO tasks
                (id,title,phase,state,deps,acceptance,updated) VALUES(?,?,?,?,?,?,?)''',
                (t['id'], t['title'], t['phase'], 'BACKLOG',
                 json.dumps(t.get('deps', [])), json.dumps(t['acceptance']), time.time()))
    def snapshot(self):
        with self.db() as c:
            return { 'tasks': [dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY priority DESC,phase,id')],
                'runs': [dict(r) for r in c.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 100')],
                'events': [dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100')],
                'approvals': [dict(r) for r in c.execute('SELECT * FROM approvals ORDER BY id DESC')],
                'mode': c.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0] }
    def control(self, action, task_id=None, value=None):
        if not isinstance(action,str): raise ValueError('invalid action')
        with self.db() as c:
            if action in ('pause', 'resume', 'stop'):
                mode = {'pause':'paused','resume':'running','stop':'stopping'}[action]
                c.execute("UPDATE settings SET value=? WHERE key='mode'", (mode,))
            elif action == 'priority':
                if not isinstance(value, int) or not -100 <= value <= 100:
                    raise ValueError('priority must be -100..100')
                changed = c.execute("UPDATE tasks SET priority=? WHERE id=? AND state IN ('BACKLOG','READY')", (value,task_id)).rowcount
                if not changed: raise ValueError('task not pending')
            elif action == 'instruction':
                if not isinstance(value, str) or not 1 <= len(value) <= 4000:
                    raise ValueError('instruction must be 1..4000 characters')
                # Instructions are audit data, never shell input or automatic permission.
            elif action == 'review':
                if value not in ('approve', 'reject'): raise ValueError('invalid review')
                state = 'DONE' if value == 'approve' else 'FAILED'
                changed = c.execute("UPDATE tasks SET state=?,updated=? WHERE id=? AND state='REVIEW'", (state,time.time(),task_id)).rowcount
                if not changed: raise ValueError('task not awaiting review')
            else:
                raise ValueError('unsupported action')
            self.event(c, action, {'task_id':task_id,'value':value})
    def recover(self):
        # Call only while holding the OS executor lock.
        with self.db() as c:
            c.execute("UPDATE runs SET status='INTERRUPTED',ended=? WHERE ended IS NULL", (time.time(),))
            c.execute("UPDATE tasks SET state='BLOCKED',error='Interrupted; inspect checkpoint before retry',updated=? WHERE state IN ('RUNNING','TESTING')", (time.time(),))
    def claim(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0] != 'running':
                return None
            done = {r[0] for r in c.execute("SELECT id FROM tasks WHERE state='DONE'")}
            for r in c.execute("SELECT * FROM tasks WHERE state IN ('BACKLOG','READY') AND attempts<max_attempts ORDER BY priority DESC,phase,id").fetchall():
                if not set(json.loads(r['deps'])) <= done: continue
                c.execute("UPDATE tasks SET state='RUNNING',attempts=attempts+1,updated=? WHERE id=?", (time.time(),r['id']))
                run = c.execute("INSERT INTO runs(task_id,started,status) VALUES(?,?,'RUNNING')", (r['id'],time.time())).lastrowid
                self.event(c, 'claimed', {'task_id':r['id'],'run_id':run})
                return dict(r), run
    def finish(self, task, run, state, error=None, before=None, after=None, log=None):
        if state not in ('REVIEW','BLOCKED','FAILED'): raise ValueError('invalid completion')
        with self.db() as c:
            c.execute('UPDATE tasks SET state=?,error=?,updated=? WHERE id=?', (state,error,time.time(),task))
            c.execute('UPDATE runs SET ended=?,status=?,error=?,before_sha=?,after_sha=?,log=? WHERE id=?',
                      (time.time(),state,error,before,after,log,run))
            self.event(c,'finished',{'task_id':task,'state':state,'error':error})
    def block(self, task, run, reason):
        self.finish(task,run,'BLOCKED',reason)
        with self.db() as c:
            c.execute('INSERT INTO approvals(task_id,action,created) VALUES(?,?,?)',(task,reason,time.time()))
