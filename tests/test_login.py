import base64,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from openplaud.api import create_app
from openplaud.login import make_verifier,PasswordLogin,LoginBusy

def basic(user,password):return 'Basic '+base64.b64encode((user+':'+password).encode()).decode()
class LoginTests(unittest.TestCase):
    def test_password_session_logout_and_technical_key(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'login.json';path.write_text(json.dumps(make_verifier('fixture','sênha:fixture')))
            self.assertNotIn('sênha',path.read_text())
            with patch.dict(os.environ,{'OPENPLAUD_LOGIN_FILE':str(path),'OPENPLAUD_ALLOWED_HOSTS':'testserver'}):
                with TestClient(create_app(Path(root)/'library','a'*40)) as c:
                    self.assertEqual(c.get('/api/recordings').status_code,401)
                    self.assertEqual(c.post('/api/session',headers={'Authorization':basic('wrong','sênha:fixture')}).status_code,401)
                    self.assertEqual(c.post('/api/session',headers={'Authorization':basic('fixture','wrong')}).status_code,401)
                    r=c.post('/api/session',headers={'Authorization':basic('fixture','sênha:fixture')})
                    self.assertEqual(r.status_code,200);self.assertIn('HttpOnly',r.headers['set-cookie'])
                    self.assertEqual(c.get('/api/recordings').status_code,200)
                    self.assertEqual(c.post('/api/logout').status_code,200)
                    self.assertEqual(c.get('/api/recordings').status_code,401)
                    self.assertEqual(c.get('/api/recordings',headers={'Authorization':'Bearer '+'a'*40}).status_code,200)
                    self.assertEqual(c.get('/api/recordings',headers={'Authorization':basic('fixture','sênha:fixture')}).status_code,401)
    def test_rate_limit_malformed_and_config_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'login.json';path.write_text(json.dumps(make_verifier('fixture','fixture')))
            login=PasswordLogin(path)
            self.assertFalse(login.verify('Basic !!!','test'))
            for _ in range(9):self.assertFalse(login.verify('Basic !!!','test'))
            with self.assertRaises(LoginBusy):login.verify(basic('fixture','fixture'),'test')
            self.assertTrue(login.verify(basic('fixture','fixture'),'other'))
            path.write_text('{}')
            with self.assertRaises(ValueError):PasswordLogin(path)
            self.assertFalse(PasswordLogin().verify(basic('fixture','fixture'),'test'))
