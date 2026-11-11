"""Single-user authenticated local MVP API; no external inference APIs."""
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import time
from fastapi import Depends,FastAPI,Header,HTTPException,Query,Request,Response
from fastapi.responses import FileResponse,HTMLResponse,PlainTextResponse,RedirectResponse
from pydantic import BaseModel,Field
from starlette.concurrency import run_in_threadpool
from .recordings import Library

MAX_UPLOAD=100*1024*1024
WEB=Path(__file__).parent/'web'

class Annotation(BaseModel):
    started_at:str|None=None
    notes:str=Field(default='',max_length=4000)
class Review(BaseModel):
    confirmed:bool=False
    text:str|None=Field(default=None,min_length=1,max_length=1500)
    owner_suggestion:str|None=Field(default=None,max_length=200)
    due_at:str|None=Field(default=None,max_length=10)
class CalendarReview(BaseModel):
    state:str
class Question(BaseModel):
    question:str=Field(min_length=1,max_length=1000)
    recording_ids:list[str]|None=Field(default=None,max_length=100)
    history:list[str]=Field(default_factory=list,max_length=4)

async def bounded_body(request,maximum):
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>maximum:raise HTTPException(413,'Body too large')
        chunks.append(chunk)
    return b''.join(chunks)

def create_app(root,token):
    if len(token)<32:raise ValueError('token must contain at least 32 characters')
    library=Library(root);sessions={}
    from .google_calendar import GoogleCalendar
    google=GoogleCalendar(library)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    def authorized(header):return hmac.compare_digest(header.encode(),('Bearer '+token).encode())
    def auth(request:Request,authorization:str=Header(default='')):
        if authorized(authorization):return
        expiry=sessions.get(request.cookies.get('openplaud_session',''),0)
        if expiry<time.time():raise HTTPException(401,'Unauthorized')
    def detail(key):
        r=library.detail(key)
        if not r:raise HTTPException(404,'Not found')
        return r
    @app.middleware('http')
    async def headers(request,call_next):
        from fastapi.responses import JSONResponse
        from urllib.parse import urlparse
        https_hosts={x.strip() for x in os.environ.get('OPENPLAUD_HTTPS_HOSTS','').split(',') if x.strip()}
        if request.url.hostname in https_hosts and request.url.scheme!='https':
            return RedirectResponse(str(request.url.replace(scheme='https')),status_code=308)
        origin=request.headers.get('origin')
        oauth_callback=request.method=='GET' and request.url.path=='/oauth/google/callback'
        if not oauth_callback and (request.headers.get('sec-fetch-site')=='cross-site' or (origin and urlparse(origin).netloc!=request.headers.get('host'))):
            return JSONResponse({'detail':'Cross-site request denied'},status_code=403)
        if request.method in ('POST','PATCH','PUT') and request.url.path!='/api/recordings':
            # Enforce limits even before JSON/Pydantic parses an untrusted body.
            size=request.headers.get('content-length','0')
            if not size.isdigit() or int(size)>2*1024**2:return JSONResponse({'detail':'Body too large'},status_code=413)
        if request.url.path.startswith('/api/') and request.url.path!='/api/session':
            if not authorized(request.headers.get('authorization','')) and sessions.get(request.cookies.get('openplaud_session',''),0)<time.time():
                return JSONResponse({'detail':'Unauthorized'},status_code=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        if request.url.hostname in https_hosts and request.url.scheme=='https':
            response.headers['Strict-Transport-Security']='max-age=31536000'
        response.headers['Content-Security-Policy']="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self'; img-src 'self' data:; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response
    @app.get('/',response_class=HTMLResponse)
    def page():return (WEB/'index.html').read_text()
    @app.get('/assets/{name}')
    def asset(name:str):
        if name not in ('app.js','app.css','icon.svg','manifest.webmanifest'):raise HTTPException(404)
        types={'app.js':'text/javascript','app.css':'text/css','icon.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json'}
        return FileResponse(WEB/name,media_type=types[name])
    @app.get('/health')
    def health():return {'status':'ok','service':'openplaud'}
    @app.post('/api/session')
    def login(request:Request,response:Response,authorization:str=Header(default='')):
        if not authorized(authorization):raise HTTPException(401,'Unauthorized')
        for k,v in list(sessions.items()):
            if v<time.time():sessions.pop(k,None)
        if len(sessions)>=64:raise HTTPException(429,'Session limit')
        session=secrets.token_urlsafe(32);sessions[session]=time.time()+8*3600
        response.set_cookie('openplaud_session',session,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=8*3600)
        return {'ok':True}
    @app.post('/api/logout',dependencies=[Depends(auth)])
    def logout(request:Request,response:Response):
        sessions.pop(request.cookies.get('openplaud_session',''),None);response.delete_cookie('openplaud_session');return {'ok':True}
    @app.get('/api/recordings',dependencies=[Depends(auth)])
    def recordings(q:str=Query(default='',max_length=200),offset:int=Query(default=0,ge=0),limit:int=Query(default=100,ge=1,le=100)):
        return library.list(q,limit,offset)
    @app.post('/api/recordings',dependencies=[Depends(auth)],status_code=201)
    async def upload(request:Request,name:str=Query(min_length=1,max_length=255)):
        if request.headers.get('content-type')!='application/octet-stream':raise HTTPException(415,'Use raw audio bytes')
        if shutil.disk_usage(library.root).free<2*1024**3:raise HTTPException(507,'Less than 2 GiB free storage')
        with tempfile.TemporaryFile(dir=library.root) as stream:
            size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>MAX_UPLOAD:raise HTTPException(413,'Upload too large')
                stream.write(chunk)
            stream.seek(0);head=stream.read(16);stream.seek(0)
            recognized=(head.startswith((b'ID3',b'OggS',b'fLaC',b'\x1aE\xdf\xa3')) or head[:4]==b'RIFF' and head[8:12]==b'WAVE' or head[4:8]==b'ftyp' or len(head)>1 and head[0]==255 and head[1]&224==224)
            if not recognized:raise HTTPException(422,'Unsupported audio container')
            try:key=await run_in_threadpool(library.ingest,stream,name,MAX_UPLOAD)
            except ValueError as e:raise HTTPException(422,str(e)) from e
        return {'id':key,'privacy':'local-only','processing':detail(key)['status']}
    @app.get('/api/recordings/{key}',dependencies=[Depends(auth)])
    def recording(key:str):return detail(key)
    @app.patch('/api/recordings/{key}',dependencies=[Depends(auth)])
    def annotation(key:str,data:Annotation):
        previous=detail(key)
        fields=data.model_dump(exclude_unset=True)
        try:library.annotate(key,fields.get('started_at',previous.get('started_at')),fields.get('notes',previous.get('notes') or ''))
        except ValueError as e:raise HTTPException(422,str(e)) from e
        from .calendar import match
        match(library,key);return detail(key)
    @app.post('/api/recordings/{key}/retry',dependencies=[Depends(auth)])
    def retry(key:str):
        detail(key)
        try:library.retry(key)
        except ValueError as e:raise HTTPException(409,str(e)) from e
        return {'ok':True}
    @app.patch('/api/recordings/{key}/actions/{index}',dependencies=[Depends(auth)])
    def review_action(key:str,index:int,data:Review):
        detail(key)
        try:library.update_action(key,index,data.model_dump(exclude_unset=True))
        except ValueError as e:raise HTTPException(409,str(e)) from e
        return detail(key)
    @app.get('/api/recordings/{key}/audio',dependencies=[Depends(auth)])
    def audio(key:str):
        detail(key);path=library.audio_path(key)
        if not path.is_file():raise HTTPException(404,'Audio unavailable')
        with path.open('rb') as f:head=f.read(16)
        media='audio/mp4' if head[4:8]==b'ftyp' else 'audio/wav' if head[:4]==b'RIFF' else 'audio/ogg' if head[:4]==b'OggS' else 'audio/flac' if head[:4]==b'fLaC' else 'audio/webm' if head[:4]==b'\x1aE\xdf\xa3' else 'audio/mpeg'
        return FileResponse(path,media_type=media,content_disposition_type='inline')
    @app.get('/api/recordings/{key}/export',dependencies=[Depends(auth)])
    def export(key:str,format:str=Query(default='txt',pattern='^(txt|json|vtt)$')):
        r=detail(key);segments=(r['transcript'] or {}).get('segments',[])
        if format=='json':return r
        def clock(ms):
            seconds,milli=divmod(ms,1000);minutes,sec=divmod(seconds,60);hours,minute=divmod(minutes,60)
            return f'{hours:02}:{minute:02}:{sec:02}.{milli:03}'
        if format=='vtt':content='WEBVTT\n\n'+'\n\n'.join(f"{clock(s['start_ms'])} --> {clock(s['end_ms'])}\n{(s.get('speaker','') or '')+' · ' if s.get('speaker') else ''}{s['text'].replace('-->','→')}" for s in segments)
        else:content=r['name']+'\n\n'+(r['analysis'] or {}).get('summary','')+'\n\n'+'\n'.join(f"[{clock(s['start_ms'])}] {(s.get('speaker')+' · ') if s.get('speaker') else ''}{s['text']}" for s in segments)
        return PlainTextResponse(content,headers={'Content-Disposition':f'attachment; filename="openplaud.{format}"'})
    @app.post('/api/recordings/{key}/speakers',dependencies=[Depends(auth)])
    def speakers(key:str):
        detail(key)
        if not os.environ.get('OPENPLAUD_DIARIZATION_ENABLED'):raise HTTPException(409,'Speaker separation is not configured')
        library.queue_speakers(key)
        return detail(key)
    @app.post('/api/chat',dependencies=[Depends(auth)])
    def chat(data:Question):
        if data.recording_ids is not None:
            for key in data.recording_ids:detail(key)
        if any(len(q)>1000 for q in data.history):raise HTTPException(422,'History question too long')
        from .chat import answer
        return answer(library,data.question,data.recording_ids,data.history)
    @app.get('/api/calendar/google',dependencies=[Depends(auth)])
    def google_status():return {'configured':google.configured(),'connections':google.connections()}
    @app.post('/api/calendar/google/connect',dependencies=[Depends(auth)])
    def google_connect(account:str=Query(min_length=1,max_length=100)):
        try:return {'url':google.authorize(account)}
        except ValueError as e:raise HTTPException(409,'Configure Google OAuth and encryption key on server first') from e
    @app.get('/oauth/google/callback')
    def google_callback(state:str=Query(max_length=200),code:str=Query(max_length=4000)):
        try:google.callback(state,code)
        except Exception as e:raise HTTPException(400,'OAuth callback failed; reconnect from the calendar screen') from e
        return RedirectResponse('/#calendar',status_code=303)
    @app.post('/api/calendar/google/sync',dependencies=[Depends(auth)])
    def google_sync(account:str=Query(min_length=1,max_length=100)):
        try:result=google.sync(account)
        except Exception as e:raise HTTPException(502,'Calendar sync failed; check account authorization') from e
        from .calendar import match
        for r in library.list():match(library,r['id'])
        return result
    @app.get('/api/calendar',dependencies=[Depends(auth)])
    def calendars():
        with library.connect() as c:
            return [dict(r) for r in c.execute('SELECT account,count(*) AS events FROM calendar_events GROUP BY account')]
    @app.post('/api/calendar/import',dependencies=[Depends(auth)])
    async def import_calendar(request:Request,account:str=Query(min_length=1,max_length=100)):
        from .calendar import import_ics,match
        content=await bounded_body(request,2*1024**2)
        try:result=await run_in_threadpool(import_ics,library,content,account)
        except Exception as e:raise HTTPException(422,'Invalid calendar') from e
        for r in library.list():match(library,r['id'])
        return result
    @app.patch('/api/recordings/{key}/calendar/{event}',dependencies=[Depends(auth)])
    def review_match(key:str,event:str,data:CalendarReview):
        detail(key)
        from .calendar import review
        try:review(library,key,event,data.state)
        except ValueError as e:raise HTTPException(422,str(e)) from e
        return detail(key)
    from .http_limits import JSONBodyLimit
    app.add_middleware(JSONBodyLimit)
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.environ.get('OPENPLAUD_ALLOWED_HOSTS','127.0.0.1,localhost,testserver').split(','))
    return app

def factory():return create_app(Path(os.environ.get('OPENPLAUD_DATA','state/library')),os.environ.get('OPENPLAUD_API_TOKEN',''))
