"""Google Recorder cloud source. Independent implementation; read-only remote operations.

The web protocol is unofficial. A dedicated interactive login is required; no
existing general browser profile, anti-detection flags or sandbox bypasses are used.
"""
import argparse
import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import urlencode,urlparse,parse_qs
import urllib.request
import urllib.error
import uuid
from cryptography.fernet import Fernet

ORIGIN='https://recorder.google.com'
RPC='https://pixelrecorder-pa.clients6.google.com/$rpc/java.com.google.wireless.android.pixel.recorder.protos.PlaybackService/GetRecordingList'
AUDIO='https://usercontent.recorder.google.com/download/playback/'
MAX_AUDIO=100*1024**2

class SourceError(Exception):pass
class AuthRequired(SourceError):pass

@dataclass(frozen=True)
class CloudRecording:
    id:str
    title:str
    started_at:str
    duration_seconds:int


def parse_recordings(data):
    if not isinstance(data,list) or not data or data[0] is not None and not isinstance(data[0],list):
        raise SourceError('UNEXPECTED_LIST_SCHEMA')
    records=[]
    for item in data[0] or []:
        try:
            identifier=str(uuid.UUID(item[13] or item[0]))
            moment=datetime.fromtimestamp(int(item[2][0])+int(item[2][1] or 0)/1e9,tz=timezone.utc)
            title=item[1] if isinstance(item[1],str) and item[1].strip() else 'Gravação Google'
            records.append(CloudRecording(identifier,title[:240],moment.isoformat(),int(item[3][0])))
        except (ValueError,TypeError,IndexError,OverflowError):continue
    if data[0] and not records:raise SourceError('UNEXPECTED_RECORD_METADATA')
    return records,bool(len(data)>1 and data[1])


class State:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.db() as c:c.executescript('''CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,
        state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,local_id TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS status(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
    @contextlib.contextmanager
    def db(self):
        c=sqlite3.connect(self.path/'source.sqlite',timeout=10)
        try:
            with c:yield c
        finally:c.close()
    def set_status(self,mode):
        with self.db() as c:c.execute('INSERT OR REPLACE INTO status VALUES(?,?)',('mode',mode))
    def failure(self):
        with self.db() as c:
            r=c.execute("SELECT value FROM status WHERE key='failures'").fetchone()
            count=int(r[0]) + 1 if r else 1
            c.execute('INSERT OR REPLACE INTO status VALUES(?,?)',('failures',str(count)))
        self.set_status('PAUSED' if count>=5 else 'RETRY_PENDING')
    def reset_failures(self):
        with self.db() as c:c.execute("DELETE FROM status WHERE key='failures'")
    def status(self):
        with self.db() as c:
            r=c.execute("SELECT value FROM status WHERE key='mode'").fetchone()
            return {'mode':r[0] if r else 'AUTH_REQUIRED','imported':c.execute("SELECT count(*) FROM imports WHERE state='IMPORTED'").fetchone()[0],
                    'failed':c.execute("SELECT count(*) FROM imports WHERE state='FAILED'").fetchone()[0]}
    def claim(self,key):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("INSERT OR IGNORE INTO imports(id,state) VALUES(?,'PENDING')",(key,))
            return bool(c.execute("UPDATE imports SET state='DOWNLOADING',attempts=attempts+1 WHERE id=? AND state!='IMPORTED' AND attempts<3",(key,)).rowcount)
    def finish(self,key,local_id=None,error=None):
        with self.db() as c:c.execute('UPDATE imports SET state=?,local_id=?,error=? WHERE id=?',('IMPORTED' if local_id else 'FAILED',local_id,error,key))
    def save_auth(self,data):
        keyfile=self.path/'auth.key'
        if not keyfile.exists():
            fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        encrypted=Fernet(keyfile.read_bytes()).encrypt(json.dumps(data).encode())
        temporary=self.path/'auth.tmp'
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'wb') as f:f.write(encrypted);f.flush();os.fsync(f.fileno())
        os.replace(temporary,self.path/'auth.enc');self.reset_failures();self.set_status('READY')
    def auth(self):
        try:return json.loads(Fernet((self.path/'auth.key').read_bytes()).decrypt((self.path/'auth.enc').read_bytes()))
        except Exception as e:raise AuthRequired('LOGIN_REQUIRED') from e


class NoRPCredirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise AuthRequired('LOGIN_REQUIRED')


class GoogleOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        target=urlparse(newurl)
        if target.hostname=='accounts.google.com':raise AuthRequired('LOGIN_REQUIRED')
        if target.scheme!='https' or not (target.hostname=='usercontent.recorder.google.com' or (target.hostname or '').endswith('.googleusercontent.com')):
            raise SourceError('UNEXPECTED_DOWNLOAD_REDIRECT')
        result=super().redirect_request(req,fp,code,msg,headers,newurl)
        if result and target.hostname!=urlparse(req.full_url).hostname:
            result.remove_header('Cookie');result.remove_header('Authorization')
        return result


class RecorderCloud:
    def __init__(self,state):self.credentials=state.auth()
    def list(self):
        auth=self.credentials;stamp=int(time.time())
        digest=hashlib.sha1(f"{stamp} {auth['sapisid']} {ORIGIN}".encode()).hexdigest()
        req=urllib.request.Request(RPC,data=json.dumps([[{'1':stamp}],100]).encode(),headers={
            'Content-Type':'application/json+protobuf','X-Goog-Api-Key':auth['api_key'],
            'Authorization':f'SAPISIDHASH {stamp}_{digest}','X-Goog-AuthUser':str(auth['authuser']),
            'Origin':ORIGIN,'Referer':ORIGIN+'/','Cookie':auth['rpc_cookies']})
        try:
            with urllib.request.build_opener(NoRPCredirects()).open(req,timeout=30) as r:raw=r.read(10*1024**2+1)
        except urllib.error.HTTPError as e:
            if e.code in (401,403):raise AuthRequired('LOGIN_REQUIRED') from e
            raise SourceError('LIST_HTTP_ERROR') from e
        if len(raw)>10*1024**2:raise SourceError('LIST_TOO_LARGE')
        try:return parse_recordings(json.loads(raw))
        except (ValueError,TypeError) as e:raise SourceError('UNEXPECTED_LIST_SCHEMA') from e
    def download(self,record,destination):
        # IDs, not recording titles, determine paths and request URLs.
        identifier=str(uuid.UUID(record.id));auth=self.credentials
        req=urllib.request.Request(AUDIO+identifier+'?'+urlencode({'authuser':auth['authuser'],'download':'true'}),
            headers={'Cookie':auth['audio_cookies'],'Referer':ORIGIN+'/'})
        opener=urllib.request.build_opener(GoogleOnlyRedirects())
        deadline=time.monotonic()+180;size=0
        try:
            with opener.open(req,timeout=30) as response,Path(destination).open('wb') as out:
                length=response.headers.get('Content-Length')
                if length and int(length)>MAX_AUDIO:raise SourceError('AUDIO_TOO_LARGE')
                if 'text/html' in response.headers.get('Content-Type',''):raise AuthRequired('LOGIN_REQUIRED')
                while block:=response.read(65536):
                    size+=len(block)
                    if size>MAX_AUDIO or time.monotonic()>deadline:raise SourceError('DOWNLOAD_LIMIT')
                    out.write(block)
        except urllib.error.HTTPError as e:
            if e.code in (401,403,404):raise AuthRequired('LOGIN_REQUIRED') from e
            raise SourceError('AUDIO_HTTP_ERROR') from e
        if not size:raise SourceError('EMPTY_AUDIO')


class LocalLibrary:
    def __init__(self,url,token):
        import ipaddress
        parsed=urlparse(url)
        try:ip=ipaddress.ip_address(parsed.hostname)
        except ValueError:raise ValueError('API target must be local or Tailscale')
        if parsed.scheme!='http' or not (ip.is_loopback or ip in ipaddress.ip_network('100.64.0.0/10')) or parsed.username or parsed.path not in ('','/') or parsed.query:
            raise ValueError('API target must be local or Tailscale')
        self.url=url.rstrip('/');self.token=token
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def upload(self,path,record):
        name=''.join(c if ord(c)>=32 else ' ' for c in record.title)[:235]+'.m4a'
        with Path(path).open('rb') as f:
            request=urllib.request.Request(self.url+'/api/recordings?'+urlencode({'name':name}),data=f,
                headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/octet-stream','Content-Length':str(Path(path).stat().st_size)},method='POST')
            with self.opener.open(request,timeout=180) as response:result=json.load(response)
        key=result['id']
        if not re.fullmatch('[a-f0-9]{64}',key):raise SourceError('INVALID_LIBRARY_RESPONSE')
        req=urllib.request.Request(self.url+'/api/recordings/'+key,headers={'Authorization':'Bearer '+self.token})
        with self.opener.open(req,timeout=15) as response:existing=json.load(response)
        if not existing.get('started_at'):
            req=urllib.request.Request(self.url+'/api/recordings/'+key,data=json.dumps({'started_at':record.started_at}).encode(),method='PATCH',
                headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
            with self.opener.open(req,timeout=15) as response:response.read()
        return key


def sync_once(state,source,library,max_items=5):
    if state.status()['mode'] in ('AUTH_REQUIRED','PAUSED'):return state.status()
    try:records,more=source.list()
    except AuthRequired:state.set_status('AUTH_REQUIRED');return state.status()
    count=0
    for record in records:
        if count>=max_items:break
        if not state.claim(record.id):continue
        count+=1
        try:
            with tempfile.TemporaryDirectory(dir=state.path) as tmp:
                audio=Path(tmp)/(str(uuid.UUID(record.id))+'.m4a');source.download(record,audio)
                state.finish(record.id,local_id=library.upload(audio,record))
        except AuthRequired:
            state.finish(record.id,error='AUTH_REQUIRED');state.set_status('AUTH_REQUIRED');return state.status()
        except Exception:state.finish(record.id,error='IMPORT_FAILED')
    state.reset_failures();state.set_status('PARTIAL_HISTORY' if more else 'READY')
    return state.status()


async def login(state):
    """User logs in directly to Google in their own isolated Chrome window."""
    from playwright.async_api import async_playwright
    chrome=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not chrome:raise SourceError('CHROME_NOT_INSTALLED')
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):raise SourceError('DESKTOP_SESSION_REQUIRED')
    profile=state.path/'chrome-profile';profile.mkdir(exist_ok=True,mode=0o700)
    active=profile/'DevToolsActivePort';active.unlink(missing_ok=True)
    proc=subprocess.Popen([chrome,'--user-data-dir='+str(profile.resolve()),'--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--no-first-run',ORIGIN],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    browser=None
    try:
        for _ in range(100):
            if proc.poll() is not None:raise SourceError('CHROME_START_FAILED')
            if active.is_file():break
            await asyncio.sleep(.1)
        else:raise SourceError('CHROME_START_TIMEOUT')
        port=int(active.read_text().splitlines()[0])
        async with async_playwright() as playwright:
            browser=await playwright.chromium.connect_over_cdp('http://127.0.0.1:'+str(port))
            context=browser.contexts[0];page=context.pages[0] if context.pages else await context.new_page()
            future=asyncio.get_running_loop().create_future()
            async def capture(response):
                if response.url.split('?')[0]!=RPC or response.status!=200 or future.done():return
                try:
                    data=await response.json();parse_recordings(data)
                    headers=await response.request.all_headers()
                    cookies=await context.cookies([RPC]);cookie_map={c['name']:c['value'] for c in cookies}
                    sapisid=cookie_map.get('SAPISID')
                    key=headers.get('x-goog-api-key') or parse_qs(urlparse(response.url).query).get('key',[''])[0]
                    audio=await context.cookies([AUDIO])
                    if not sapisid or not key:raise AuthRequired('SESSION_FIELDS_UNAVAILABLE')
                    payload={'sapisid':sapisid,'api_key':key,'authuser':int(headers.get('x-goog-authuser','0')),
                        'rpc_cookies':headers.get('cookie') or '; '.join(c['name']+'='+c['value'] for c in cookies),
                        'audio_cookies':'; '.join(c['name']+'='+c['value'] for c in audio)}
                    state.save_auth(payload);state.set_status('VERIFYING')
                    try:
                        await asyncio.to_thread(RecorderCloud(state).list)
                    except AuthRequired:
                        state.set_status('AUTH_REQUIRED');raise
                    except Exception:
                        state.set_status('PAUSED');raise
                    state.set_status('READY')
                    if not future.done():future.set_result(True)
                except Exception as e:
                    if not future.done():future.set_exception(SourceError(type(e).__name__))
            page.on('response',capture)
            await page.goto(ORIGIN,wait_until='domcontentloaded',timeout=60000)
            await page.bring_to_front()
            print('Complete the Google login in the dedicated Chrome window. Maximum wait: 10 minutes.',flush=True)
            await asyncio.wait_for(future,600)
            await browser.close();browser=None
    finally:
        if browser:
            with contextlib.suppress(Exception):await browser.close()
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['login','status','sync']);p.add_argument('--state',type=Path,default=Path('state/google-recorder'))
    p.add_argument('--api-url',default='http://100.120.232.65:8767');p.add_argument('--api-env',type=Path,default=Path('state/product.env'));a=p.parse_args()
    os.umask(0o077);state=State(a.state)
    if a.command=='status':print(json.dumps(state.status()));return
    with (a.state/'source.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            if a.command=='login':asyncio.run(login(state))
            elif a.command=='sync' and state.status()['mode'] not in ('AUTH_REQUIRED','PAUSED'):
                env=dict(x.split('=',1) for x in a.api_env.read_text().splitlines() if x and not x.startswith('#'))
                sync_once(state,RecorderCloud(state),LocalLibrary(a.api_url,env['OPENPLAUD_API_TOKEN']))
            print(json.dumps(state.status()))
        except AuthRequired:state.set_status('AUTH_REQUIRED');print(json.dumps(state.status()));raise SystemExit(2)
        except Exception as e:
            if a.command=='sync':state.failure()
            # Never print Google response bodies, titles, cookies or session material.
            print(json.dumps({'mode':'ERROR','error_code':str(e) if isinstance(e,SourceError) else type(e).__name__}));raise SystemExit(1)

if __name__=='__main__':main()
