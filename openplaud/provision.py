"""Deliberate public-model provisioning; never run from an audio request."""
import argparse
import json
from pathlib import Path
import shutil

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',choices=['base','small'],default='small');p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    a.destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    if shutil.disk_usage(a.destination).free<5*1024**3:p.error('At least 5 GiB free required for provisioning')
    from huggingface_hub import HfApi,snapshot_download
    repo='Systran/faster-whisper-'+a.model;revision=HfApi().model_info(repo).sha
    snapshot_download(repo,revision=revision,local_dir=a.destination,allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*'])
    (a.destination/'openplaud-model.json').write_text(json.dumps({'repository':repo,'revision':revision,'license':'MIT'}))
    print('Public model provisioned; runtime loads locally only')
if __name__=='__main__':main()
