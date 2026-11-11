import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from openplaud.api import create_app
class DomainTests(unittest.TestCase):
    def test_https_redirect_secure_session_and_origin(self):
        domain='conversas.ricardodoria.com.br'
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'OPENPLAUD_ALLOWED_HOSTS':domain,'OPENPLAUD_HTTPS_HOSTS':domain}):
            client=TestClient(create_app(root,'a'*40),base_url='http://'+domain)
            r=client.get('/',follow_redirects=False)
            self.assertEqual(r.status_code,308);self.assertEqual(r.headers['location'],'https://'+domain+'/')
            with TestClient(create_app(root,'a'*40),base_url='https://'+domain) as secure:
                r=secure.post('/api/session',headers={'Authorization':'Bearer '+'a'*40,'Origin':'https://'+domain})
                self.assertEqual(r.status_code,200);self.assertIn('Secure',r.headers['set-cookie'])
                self.assertIn('Strict-Transport-Security',r.headers)
                self.assertEqual(secure.get('/api/recordings').status_code,200)
                self.assertEqual(secure.post('/api/chat',json={'question':'test'},headers={'Origin':'https://untrusted.example'}).status_code,403)
