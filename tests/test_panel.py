from http.server import ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from openplaud.control import Store
from openplaud.panel import handler
class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'db');self.token='t'*40
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store,self.token))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,body=None,token=None,extra=None):
        c=http.client.HTTPConnection(*self.server.server_address,timeout=3)
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        headers.update(extra or {})
        c.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
        r=c.getresponse();data=r.read();c.close();return r.status,data
    def test_auth_control(self):
        self.assertEqual(self.request('/api/state')[0],401)
        self.assertEqual(self.request('/api/state',token='wrong')[0],401)
        self.assertEqual(self.request('/api/state',token='café')[0],401)
        self.assertEqual(self.request('/api/state',token=self.token)[0],200)
        self.assertEqual(self.request('/api/control',{'action':'resume'},self.token)[0],200)
        self.assertEqual(self.store.snapshot()['mode'],'running')
    def test_shell_crosssite(self):
        self.assertEqual(self.request('/api/control',{'action':'resume'},self.token,{'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/api/control',{'action':'shell','value':'id'},self.token)[0],400)
    def test_xss(self):
        self.store.control('instruction',value='<script>alert(1)</script>')
        status,body=self.request('/');self.assertEqual(status,200)
        self.assertNotIn(b'innerHTML',body);self.assertNotIn(b'alert(1)',body)
