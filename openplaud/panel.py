"""Private authenticated control UI. Bind loopback or explicit Tailscale IPv4 only."""
import argparse
import hmac
import ipaddress
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .control import Store

HTML = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpenPlaud · Desenvolvimento</title>
<style>body{font:16px system-ui;background:#111b24;color:#e5edf5;max-width:950px;margin:auto;padding:24px}button,input{font:inherit;padding:12px;margin:5px;border-radius:8px}button{background:#83e3bd;border:0;cursor:pointer}article{background:#1d2c39;padding:16px;margin:12px 0;border-radius:12px}small{color:#a7bdcd}pre{white-space:pre-wrap;overflow-wrap:anywhere}label{display:block}</style>
<h1>OpenPlaud</h1><p>Controle privado de desenvolvimento</p><label>Token de acesso <input id="token" type="password" autocomplete="off"></label><button id="connect">Conectar</button><p id="status" role="status">Desconectado</p>
<nav><button data-action="pause">Pausar</button><button data-action="resume">Retomar</button><button data-action="stop">Parada segura</button></nav><label>Instrução para revisão <input id="instruction" maxlength="4000"></label><button id="send">Registrar instrução</button><main id="tasks"></main><details><summary>Execuções e eventos</summary><pre id="history"></pre></details>
<script>
let active=false;const $=id=>document.getElementById(id);
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+$('token').value,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});if(!r.ok)throw Error('Acesso ou operação recusada ('+r.status+')');return r.json()}
async function refresh(){try{let d=await api('/api/state');$('status').textContent=d.mode+' · '+d.tasks.filter(t=>t.state==='DONE').length+'/'+d.tasks.length+' concluídas';$('tasks').replaceChildren();for(const t of d.tasks){let a=document.createElement('article'),h=document.createElement('h2'),s=document.createElement('small'),p=document.createElement('p');h.textContent=t.id+' · '+t.title;s.textContent=t.state+' · tentativa '+t.attempts+'/'+t.max_attempts;p.textContent=JSON.parse(t.acceptance).join(' · ');a.append(h,s,p);if(t.error){let e=document.createElement('p');e.textContent=t.error;a.append(e)}if(['BACKLOG','READY'].includes(t.state)){let i=document.createElement('input');i.type='number';i.min=-100;i.max=100;i.value=t.priority;i.setAttribute('aria-label','Prioridade de '+t.id);let b=document.createElement('button');b.textContent='Priorizar';b.onclick=()=>act('priority',t.id,Number(i.value));a.append(i,b)}if(t.state==='REVIEW'){let b=document.createElement('button');b.textContent='Aceitar critérios verificados';b.onclick=()=>act('review',t.id,'approve');a.append(b)}$('tasks').append(a)}$('history').textContent=JSON.stringify({runs:d.runs,events:d.events,approvals:d.approvals},null,2)}catch(e){$('status').textContent=e.message;active=false}}
async function act(action,task_id,value){try{await api('/api/control',{action,task_id,value});await refresh()}catch(e){$('status').textContent=e.message}}
$('connect').onclick=()=>{active=true;refresh()};document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>act(b.dataset.action));$('send').onclick=()=>act('instruction',null,$('instruction').value);setInterval(()=>{if(active)refresh()},5000);
</script></html>'''


def handler(store, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # Never log auth headers or request bodies.
        def reply(self,status,data,html=False):
            raw=data.encode() if html else json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(raw)
        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization','').encode(),('Bearer '+token).encode())
        def do_GET(self):
            if self.path=='/': return self.reply(200,HTML,True)
            if not self.authorized(): return self.reply(401,{'error':'unauthorized'})
            if self.path=='/api/state': return self.reply(200,store.snapshot())
            return self.reply(404,{'error':'not found'})
        def do_POST(self):
            if not self.authorized(): return self.reply(401,{'error':'unauthorized'})
            # Authorization bearer is not ambient browser auth. Cross-site fetch needs preflight,
            # which this server rejects; enforce JSON and reject cross-site requests as well.
            if self.headers.get('Sec-Fetch-Site')=='cross-site': return self.reply(403,{'error':'cross-site'})
            if self.path!='/api/control': return self.reply(404,{'error':'not found'})
            if self.headers.get('Content-Type')!='application/json': return self.reply(415,{'error':'JSON required'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=8192: raise ValueError('invalid body size')
                d=json.loads(self.rfile.read(n))
                store.control(d.get('action'),d.get('task_id'),d.get('value'))
                self.reply(200,{'ok':True})
            except (ValueError,TypeError,AttributeError): self.reply(400,{'error':'invalid operation'})
    return Handler


def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True)
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8766)
    a=p.parse_args(); ip=ipaddress.ip_address(a.host)
    container_listener = a.host == '0.0.0.0' and os.environ.get('OPENPLAUD_CONTAINER_LISTENER') == '1'
    if not (ip.is_loopback or ip in ipaddress.ip_network('100.64.0.0/10') or container_listener):
        p.error('bind must be loopback or Tailscale IPv4')
    token=os.environ.get('OPENPLAUD_PANEL_TOKEN','')
    if len(token)<32: p.error('OPENPLAUD_PANEL_TOKEN must contain at least 32 characters')
    server=ThreadingHTTPServer((a.host,a.port),handler(Store(a.state/'control.sqlite'),token))
    server.timeout=10;server.serve_forever()

if __name__=='__main__': main()
