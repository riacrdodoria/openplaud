"""Consistent non-destructive backup and checksum verification for the local adapter."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sqlite3
from .recordings import Library

def verify(path):
    path=Path(path)
    with sqlite3.connect(path/'library.sqlite') as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('invalid database')
        ids=[r[0] for r in c.execute('SELECT id FROM recordings')]
    for key in ids:
        if not Library.valid_key(key):raise ValueError('invalid object id')
        digest=hashlib.sha256()
        with (path/'audio'/key).open('rb') as f:
            while chunk:=f.read(1024*1024):digest.update(chunk)
        if digest.hexdigest()!=key:raise ValueError('audio checksum mismatch')
    return len(ids)

def backup(library,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False,mode=0o700)
    (destination/'audio').mkdir(mode=0o700)
    with library.connect() as source,sqlite3.connect(destination/'library.sqlite') as target:source.backup(target)
    with sqlite3.connect(destination/'library.sqlite') as c:ids=[r[0] for r in c.execute('SELECT id FROM recordings')]
    for key in ids:shutil.copyfile(library.audio_path(key),destination/'audio'/key)
    return verify(destination)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('state/library'));p.add_argument('--dest',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
    count=verify(a.dest) if a.verify else backup(Library(a.root),a.dest)
    print(f'Verified {count} immutable audio objects')
if __name__=='__main__':main()
