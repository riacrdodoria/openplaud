"""Read-only calendar import and reviewable temporal matching."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
from icalendar import Calendar

def aware(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('timezone required')
    return d

def import_events(library,events,account):
    if not account or len(account)>100 or len(events)>5000:raise ValueError('invalid account or event count')
    rows=[]
    for e in events:
        start=aware(e['starts']);end=aware(e['ends'])
        if end<=start:raise ValueError('invalid event interval')
        title=str(e['title'])[:500];uid=str(e['id'])[:1000]
        key=hashlib.sha256((account+'\0'+uid).encode()).hexdigest()
        participants=e.get('participants',[])
        if not isinstance(participants,list) or len(participants)>500:raise ValueError('invalid participants')
        rows.append((key,account,title,start.isoformat(),end.isoformat(),json.dumps(participants)))
    with library.connect() as c:
        c.executemany('INSERT OR REPLACE INTO calendar_events VALUES(?,?,?,?,?,?)',rows)
    return len(rows)

def import_ics(library,content,account):
    if len(content)>2*1024**2:raise ValueError('calendar too large')
    events=[];skipped=0
    for component in Calendar.from_ical(content).walk('VEVENT'):
        start=component.get('dtstart');end=component.get('dtend')
        # Floating/all-day/recurring events require explicit expansion; do not guess timezone.
        if not start or not end or not isinstance(start.dt,datetime) or not isinstance(end.dt,datetime) or start.dt.tzinfo is None or 'rrule' in component:
            skipped+=1;continue
        events.append({'id':str(component.get('uid',''))+'@'+start.dt.isoformat(),
            'title':str(component.get('summary','Sem título')),'starts':start.dt.isoformat(),
            'ends':end.dt.isoformat(),'participants':[]})
    return {'imported':import_events(library,events,account),'skipped':skipped}

def match(library,key):
    detail=library.detail(key)
    if not detail:return []
    with library.connect() as c:c.execute("DELETE FROM calendar_matches WHERE recording_id=? AND state='SUGGESTED'",(key,))
    if not detail.get('started_at'):return library.detail(key)['calendar_matches']
    start=aware(detail['started_at']);segments=(detail.get('transcript') or {}).get('segments',[])
    end=start+timedelta(milliseconds=segments[-1]['end_ms'] if segments else 0)
    with library.connect() as c:
        events=c.execute('SELECT * FROM calendar_events').fetchall()
        for e in events:
            es,ee=aware(e['starts']),aware(e['ends'])
            if start<=ee+timedelta(minutes=10) and end>=es-timedelta(minutes=10):
                gap=abs((start-es).total_seconds());score=max(0.1,1-min(gap/7200,0.9))
                c.execute('''INSERT INTO calendar_matches(recording_id,event_id,score) VALUES(?,?,?)
                ON CONFLICT(recording_id,event_id) DO UPDATE SET score=excluded.score''',(key,e['id'],score))
    return library.detail(key)['calendar_matches']

def review(library,key,event,state):
    if state not in ('CONFIRMED','REJECTED'):raise ValueError('invalid review')
    with library.connect() as c:
        changed=c.execute('UPDATE calendar_matches SET state=? WHERE recording_id=? AND event_id=?',(state,key,event)).rowcount
        if not changed:raise ValueError('match unavailable')
