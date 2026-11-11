"""Optional username/password verifier; never stores plaintext credentials."""
import base64
import binascii
from collections import OrderedDict,deque
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
import time

ITERATIONS=600000

def make_verifier(username,password):
    salt=secrets.token_bytes(32)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS)
    return {'version':1,'username':username,'iterations':ITERATIONS,'salt':salt.hex(),'digest':digest.hex()}

class PasswordLogin:
    def __init__(self,path=None):
        self.verifier=None;self.attempts=OrderedDict();self.lock=threading.Lock();self.slots=threading.BoundedSemaphore(2)
        if path:
            data=json.loads(Path(path).read_text())
            if data.get('version')!=1 or data.get('iterations')!=ITERATIONS or not isinstance(data.get('username'),str):raise ValueError('invalid login configuration')
            if len(bytes.fromhex(data['salt']))!=32 or len(bytes.fromhex(data['digest']))!=32:raise ValueError('invalid login verifier')
            self.verifier=data
    def verify(self,header,client):
        if not self.verifier or not header.startswith('Basic '):return False
        if len(header)>6000:return False
        with self.lock:
            now=time.monotonic();attempts=self.attempts.setdefault(client,deque())
            self.attempts.move_to_end(client)
            while attempts and attempts[0]<now-300:attempts.popleft()
            if len(attempts)>=10:raise LoginBusy()
            attempts.append(now)
            while len(self.attempts)>1024:self.attempts.popitem(last=False)
        if not self.slots.acquire(blocking=False):raise LoginBusy()
        try:
            try:
                username,password=base64.b64decode(header[6:],validate=True).decode('utf-8').split(':',1)
            except (ValueError,UnicodeError,binascii.Error):return False
            if len(username)>200 or len(password)>1024:return False
            v=self.verifier
            digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(v['salt']),v['iterations'])
            valid_user=hmac.compare_digest(username.encode(),v['username'].encode())
            return hmac.compare_digest(digest,bytes.fromhex(v['digest'])) and valid_user
        finally:self.slots.release()

class LoginBusy(Exception):pass
