"""Authenticated development MVP API. No external AI requests."""
import hmac
import os
from pathlib import Path
import tempfile
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool
from .recordings import Library

MAX_UPLOAD=100*1024*1024
PAGE='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpenPlaud · Biblioteca</title><style>body{font:16px system-ui;max-width:850px;margin:auto;padding:24px;background:#111b24;color:#e5edf5}input,button{font:inherit;padding:12px;margin:6px 0;max-width:100%;box-sizing:border-box}button{background:#83e3bd;border:0;border-radius:8px;cursor:pointer}article{background:#1d2c39;padding:18px;margin:14px 0;border-radius:12px}label{display:block}audio{width:100%}</style><h1>OpenPlaud</h1><p>Sua biblioteca privada de áudio</p><label>Token <input id="token" type="password" autocomplete="off"></label><button id="login">Abrir biblioteca</button><label>Importar áudio (até 100 MiB) <input type="file" accept="audio/*" id="file"></label><button id="upload">Importar</button><p>Os arquivos permanecem locais. Transcrição ainda não ativada.</p><label>Buscar pelo nome <input id="query" maxlength="200"></label><button id="search">Buscar</button><p id="status" role="status"></p><main id="library"></main><script>
const $=id=>document.getElementById(id);let current=null;
async function req(path,options={}){let r=await fetch(path,{...options,headers:{Authorization:'Bearer '+$('token').value,...options.headers}});if(!r.ok)throw Error('Operação recusada: '+r.status);return r}
async function list(){try{let rows=await(await req('/api/recordings?q='+encodeURIComponent($('query').value))).json();$('library').replaceChildren();for(let row of rows){let a=document.createElement('article'),h=document.createElement('h2'),p=document.createElement('p'),b=document.createElement('button');h.textContent=row.name;p.textContent=(row.bytes/1048576).toFixed(1)+' MiB · '+row.privacy;b.textContent='Reproduzir';b.onclick=async()=>{try{let blob=await(await req('/api/recordings/'+row.id+'/audio')).blob();if(current){current.pause();URL.revokeObjectURL(current.src);current.remove()}current=document.createElement('audio');current.controls=true;current.src=URL.createObjectURL(blob);a.append(current);await current.play()}catch(e){$('status').textContent=e.message}};a.append(h,p,b);$('library').append(a)}$('status').textContent=rows.length+' gravações (máximo 100 por consulta)'}catch(e){$('status').textContent=e.message}}
$('login').onclick=list;$('search').onclick=list;$('upload').onclick=async()=>{let f=$('file').files[0];if(!f)return;if(f.size>104857600){$('status').textContent='Limite: 100 MiB';return}try{$('status').textContent='Importando…';await req('/api/recordings?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});await list()}catch(e){$('status').textContent=e.message}};
</script></html>'''

def create_app(root,token):
    if len(token)<32:raise ValueError('token must contain at least 32 characters')
    library=Library(root)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    def auth(authorization: str=Header(default='')):
        if not hmac.compare_digest(authorization,'Bearer '+token):raise HTTPException(401,'Unauthorized')
    @app.middleware('http')
    async def headers(request,call_next):
        if request.headers.get('sec-fetch-site')=='cross-site':
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Cross-site request denied'},status_code=403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; media-src blob:; frame-ancestors 'none'; base-uri 'none'"
        return response
    @app.get('/',response_class=HTMLResponse)
    def page():return PAGE
    @app.get('/api/recordings',dependencies=[Depends(auth)])
    def recordings(q: str=Query(default='',max_length=200)):return library.list(q)
    @app.post('/api/recordings',dependencies=[Depends(auth)],status_code=201)
    async def upload(request: Request,name: str=Query(min_length=1,max_length=255)):
        if request.headers.get('content-type')!='application/octet-stream':raise HTTPException(415,'Use raw audio bytes')
        if len(library.list())>=100:raise HTTPException(409,'Development library capacity reached')
        # TemporaryFile is private and unlinked automatically, including on disconnect/errors.
        with tempfile.TemporaryFile(dir=library.root) as stream:
            size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>MAX_UPLOAD:raise HTTPException(413,'Upload too large')
                stream.write(chunk)
            stream.seek(0);head=stream.read(16);stream.seek(0)
            recognized=(head.startswith((b'ID3',b'OggS',b'fLaC',b'\x1aE\xdf\xa3'))
                        or head[:4]==b'RIFF' and head[8:12]==b'WAVE'
                        or head[4:8]==b'ftyp'
                        or len(head)>1 and head[0]==255 and head[1]&224==224)
            if not recognized:raise HTTPException(422,'Unsupported audio container')
            try:key=await run_in_threadpool(library.ingest,stream,name,MAX_UPLOAD)
            except ValueError as e:raise HTTPException(422,str(e)) from e
        return {'id':key,'privacy':'local-only','processing':'QUEUED_NOT_CONFIGURED'}
    @app.get('/api/recordings/{key}/audio',dependencies=[Depends(auth)])
    def audio(key:str):
        try:path=library.audio_path(key)
        except ValueError:raise HTTPException(404,'Not found')
        if not path.is_file():raise HTTPException(404,'Not found')
        return FileResponse(path,media_type='application/octet-stream',filename='recording.audio',content_disposition_type='inline')
    return app

def factory():
    return create_app(Path(os.environ.get('OPENPLAUD_DATA','state/library')),os.environ.get('OPENPLAUD_API_TOKEN',''))
