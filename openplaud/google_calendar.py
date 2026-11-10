"""Optional Google Calendar OAuth: read-only scope, PKCE, one-time state, encrypted tokens."""
import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode,urlparse
import urllib.request
from cryptography.fernet import Fernet
from .calendar import import_events
SCOPE='https://www.googleapis.com/auth/calendar.events.readonly'

class GoogleCalendar:
    def __init__(self,library):
        self.library=library
        with library.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS oauth_states(state_hash TEXT PRIMARY KEY,
              account TEXT NOT NULL,verifier TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS calendar_connections(account TEXT PRIMARY KEY,
              encrypted_token BLOB NOT NULL,updated REAL NOT NULL);''')
    def configured(self):
        return all(os.environ.get(x) for x in ('OPENPLAUD_GOOGLE_CLIENT_ID','OPENPLAUD_GOOGLE_CLIENT_SECRET','OPENPLAUD_GOOGLE_REDIRECT_URI','OPENPLAUD_TOKEN_KEY'))
    def cipher(self):return Fernet(os.environ['OPENPLAUD_TOKEN_KEY'].encode())
    def redirect_uri(self):
        value=os.environ['OPENPLAUD_GOOGLE_REDIRECT_URI'];u=urlparse(value)
        if not (u.scheme=='https' or u.scheme=='http' and u.hostname in ('localhost','127.0.0.1')) or u.username or u.fragment or u.query:
            raise ValueError('OAuth callback requires HTTPS or loopback HTTP')
        return value
    def authorize(self,account):
        if not self.configured():raise ValueError('Google OAuth not configured')
        self.cipher();redirect=self.redirect_uri()
        if not account or len(account)>100:raise ValueError('invalid account')
        state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.library.connect() as c:
            c.execute('DELETE FROM oauth_states WHERE expires<?',(time.time(),))
            c.execute('INSERT INTO oauth_states VALUES(?,?,?,?)',(hashlib.sha256(state.encode()).hexdigest(),account,verifier,time.time()+600))
        return 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':os.environ['OPENPLAUD_GOOGLE_CLIENT_ID'],
            'redirect_uri':redirect,'response_type':'code','scope':SCOPE,'state':state,'access_type':'offline',
            'prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256'})
    @staticmethod
    def exchange(fields):
        req=urllib.request.Request('https://oauth2.googleapis.com/token',data=urlencode(fields).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read(1024*1024))
    def callback(self,state,code):
        if not self.configured() or len(state)>200 or len(code)>4000:raise ValueError('invalid callback')
        hashed=hashlib.sha256(state.encode()).hexdigest()
        with self.library.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM oauth_states WHERE state_hash=? AND expires>?',(hashed,time.time())).fetchone()
            if not row:raise ValueError('invalid or expired OAuth state')
            c.execute('DELETE FROM oauth_states WHERE state_hash=?',(hashed,))
        token=self.exchange({'client_id':os.environ['OPENPLAUD_GOOGLE_CLIENT_ID'],'client_secret':os.environ['OPENPLAUD_GOOGLE_CLIENT_SECRET'],
            'redirect_uri':self.redirect_uri(),'code':code,'code_verifier':row['verifier'],'grant_type':'authorization_code'})
        if not token.get('refresh_token') or not token.get('access_token'):raise ValueError('offline authorization required')
        token['expires_at']=time.time()+int(token.get('expires_in',3600));self.save(row['account'],token)
        return row['account']
    def save(self,account,token):
        encrypted=self.cipher().encrypt(json.dumps(token).encode())
        with self.library.connect() as c:c.execute('INSERT OR REPLACE INTO calendar_connections VALUES(?,?,?)',(account,encrypted,time.time()))
    def connections(self):
        with self.library.connect() as c:return [dict(r) for r in c.execute('SELECT account,updated FROM calendar_connections')]
    def sync(self,account):
        with self.library.connect() as c:row=c.execute('SELECT encrypted_token FROM calendar_connections WHERE account=?',(account,)).fetchone()
        if not row:raise ValueError('connection unavailable')
        token=json.loads(self.cipher().decrypt(row[0]))
        if token.get('expires_at',0)<time.time()+60:
            fresh=self.exchange({'client_id':os.environ['OPENPLAUD_GOOGLE_CLIENT_ID'],'client_secret':os.environ['OPENPLAUD_GOOGLE_CLIENT_SECRET'],
                'refresh_token':token['refresh_token'],'grant_type':'refresh_token'})
            if not fresh.get('access_token'):raise ValueError('reauthorization required')
            token.update(fresh);token['expires_at']=time.time()+int(fresh.get('expires_in',3600));self.save(account,token)
        now=datetime.now(timezone.utc);events=[];page=None
        for _ in range(10):
            params={'timeMin':(now-timedelta(days=30)).isoformat(),'timeMax':(now+timedelta(days=30)).isoformat(),
                'singleEvents':'true','maxResults':250,'orderBy':'startTime'}
            if page:params['pageToken']=page
            req=urllib.request.Request('https://www.googleapis.com/calendar/v3/calendars/primary/events?'+urlencode(params),headers={'Authorization':'Bearer '+token['access_token']})
            with urllib.request.urlopen(req,timeout=20) as r:data=json.loads(r.read(4*1024*1024))
            for item in data.get('items',[]):
                if item.get('status')=='cancelled' or 'dateTime' not in item.get('start',{}) or 'dateTime' not in item.get('end',{}):continue
                events.append({'id':item['id'],'title':item.get('summary','Sem título'),'starts':item['start']['dateTime'],
                    'ends':item['end']['dateTime'],'participants':[a.get('displayName') or a.get('email','') for a in item.get('attendees',[])]})
            page=data.get('nextPageToken')
            if not page:break
        return {'imported':import_events(self.library,events,account),'truncated':bool(page)}
