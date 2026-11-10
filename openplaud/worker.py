"""Persistent, single-process, bounded audio worker. No background coding agent."""
import argparse
import fcntl
import json
import logging
import multiprocessing
import os
from pathlib import Path
import shutil
import stat
import time
from dataclasses import asdict
from .recordings import Library
from .providers import Segment,Transcript,transcribe
from .analysis import analyze

log=logging.getLogger('openplaud.worker')

class WhisperProvider:
    external=False
    def __init__(self,model_path):self.model_path=model_path
    def transcribe(self,audio,language):
        from faster_whisper import WhisperModel
        # Offline only: provisioning is a separate deliberate operation.
        model=WhisperModel(str(self.model_path),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
        segments,info=model.transcribe(str(audio),language=None if language=='auto' else language,
                                      beam_size=3,vad_filter=True,condition_on_previous_text=False)
        result=tuple(Segment(max(0,round(s.start*1000)),max(1,round(s.end*1000)),s.text.strip()) for s in segments if s.text.strip())
        manifest=self.model_path/'openplaud-model.json'
        identity=json.loads(manifest.read_text()) if manifest.exists() else {'repository':self.model_path.name,'revision':'local'}
        return Transcript(info.language,result,'faster-whisper:'+identity['repository']+'@'+identity['revision'][:12]+':int8')


def process(library,job,provider,language='auto'):
    existing=library.detail(job['id'])['transcript']
    if existing:
        segments=existing['segments']
    else:
        transcript=transcribe(provider,library.audio_path(job['id']),language,job['privacy'])
        library.save_transcript(job['id'],transcript)
        segments=library.detail(job['id'])['transcript']['segments']
    from .llm import summarize
    library.save_analysis(job['id'],summarize(segments))


def child(root,job,model,language):
    try:process(Library(root),job,WhisperProvider(model),language)
    except Exception as error:
        # Never emit audio/transcription/private provider errors into logs.
        Library(root).fail(job['id'],'NO_SPEECH_DETECTED' if isinstance(error,ValueError) and str(error)=='empty transcript' else 'TRANSCRIPTION_OR_ANALYSIS_FAILED')
        raise SystemExit(1)


def import_inbox(library,inbox,stable_seconds=15):
    imported=0
    if not inbox or not inbox.is_dir():return imported
    for path in sorted(inbox.iterdir()):
        try:
            if _import_file(library,path,stable_seconds):imported+=1
        except (OSError,ValueError):
            log.warning('Inbox entry skipped; invalid metadata, concurrent modification or access denied')
        if imported>=20:break
    return imported


def _import_file(library,path,stable_seconds):
    if path.suffix.lower() not in ('.wav','.mp3','.m4a','.ogg','.flac','.webm','.aac'):return False
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size==0 or before.st_size>100*1024**2 or time.time()-before.st_mtime<stable_seconds:return False
    resolved=str(path.absolute())
    with library.connect() as c:
        seen=c.execute('SELECT size,mtime_ns FROM inbox_seen WHERE path=?',(resolved,)).fetchone()
    if seen and tuple(seen)==(before.st_size,before.st_mtime_ns):return False
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):return False
        import tempfile
        with tempfile.TemporaryFile(dir=library.root) as copy:
            size=0
            while block:=stream.read(65536):
                size+=len(block)
                if size>100*1024**2:return False
                copy.write(block)
            after=os.fstat(stream.fileno())
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):return False
            copy.seek(0);key=library.ingest(copy,path.name)
            with library.connect() as c:c.execute('INSERT OR REPLACE INTO inbox_seen VALUES(?,?,?,?)',(resolved,before.st_size,before.st_mtime_ns,key))
    return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('state/library'))
    p.add_argument('--model',type=Path,required=True);p.add_argument('--inbox',type=Path)
    p.add_argument('--language',choices=['auto','pt','en'],default='auto');p.add_argument('--once',action='store_true')
    a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True,mode=0o700);os.umask(0o077)
    if not (a.model/'model.bin').is_file():p.error('Provision a local faster-whisper model before starting worker')
    with (a.root/'worker.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        library=Library(a.root);library.recover()
        while True:
            if shutil.disk_usage(a.root).free<2*1024**3:
                log.warning('Worker paused: less than 2 GiB free')
                if a.once:break
                time.sleep(30);continue
            import_inbox(library,a.inbox)
            job=library.claim()
            if job:
                # A process boundary releases native model memory and bounds each attempt.
                proc=multiprocessing.get_context('spawn').Process(target=child,args=(a.root,job,a.model,a.language))
                proc.start()
                try:proc.join(1800)
                finally:
                    if proc.is_alive():proc.terminate();proc.join(5)
                    if proc.is_alive():proc.kill();proc.join()
                status=library.detail(job['id'])['status']
                if status in ('TRANSCRIBING','ANALYZING'):library.fail(job['id'],'WORKER_TIMEOUT_OR_CRASH')
            if a.once:break
            time.sleep(2 if job else 5)

if __name__=='__main__':main()
