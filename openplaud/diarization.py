"""Offline anonymous speaker turns. No voice enrollment or remote inference."""
import hashlib
import json
import math
from pathlib import Path


def assign_speakers(segments, turns):
    result=[]
    for source in segments:
        s=dict(source);scores={};overlap=False
        active=[]
        for turn in turns:
            start=max(s['start_ms'],turn['start_ms']);end=min(s['end_ms'],turn['end_ms'])
            if end<=start:continue
            scores[turn['speaker']]=scores.get(turn['speaker'],0)+end-start
            for a,b,speaker in active:
                if speaker!=turn['speaker'] and min(b,end)>max(a,start):overlap=True
            active.append((start,end,turn['speaker']))
        ranked=sorted(scores,key=scores.get,reverse=True)
        total=sum(scores.values());best=scores[ranked[0]] if ranked else 0
        # Avoid asserting one speaker for mixed speech or poorly aligned segments.
        confident=bool(ranked) and not overlap and best>=0.8*total and best>=0.5*(s['end_ms']-s['start_ms'])
        s['speaker']=ranked[0] if confident else None
        s['speaker_ambiguous']=not confident
        result.append(s)
    return result


def diarize(audio,model_dir,max_seconds=1800,cluster_threshold=0.9):
    import numpy as np
    import sherpa_onnx
    root=Path(model_dir)
    manifest=json.loads((root/'manifest.json').read_text())
    for name in ('segmentation.onnx','embedding.onnx'):
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=manifest['sha256'][name]:
            raise ValueError('DIARIZATION_MODEL_CHECKSUM')
    config=sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(root/'segmentation.onnx')),
            num_threads=2,provider='cpu'),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(root/'embedding.onnx'),num_threads=2,provider='cpu'),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1,threshold=cluster_threshold),
        min_duration_on=0.3,min_duration_off=0.5)
    if not config.validate():raise ValueError('DIARIZATION_CONFIG')
    engine=sherpa_onnx.OfflineSpeakerDiarization(config)
    # Header metadata is not trusted; decoded allocation is bounded by frame iteration.
    import av
    parts=[];count=0
    with av.open(str(audio)) as container:
        resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
        for frame in container.decode(audio=0):
            for f in resampler.resample(frame):
                data=f.to_ndarray().reshape(-1);count+=len(data)
                if count>max_seconds*16000:raise ValueError('DIARIZATION_DURATION_LIMIT')
                parts.append(data)
        for f in resampler.resample(None):
            data=f.to_ndarray().reshape(-1);count+=len(data)
            if count>max_seconds*16000:raise ValueError('DIARIZATION_DURATION_LIMIT')
            parts.append(data)
    if not count:raise ValueError('DIARIZATION_EMPTY')
    samples=np.concatenate(parts).astype(np.float32,copy=False);del parts
    raw=engine.process(samples).sort_by_start_time()
    labels={};turns=[]
    for r in raw:
        if not math.isfinite(r.start) or not math.isfinite(r.end) or r.end<=r.start:continue
        label=labels.setdefault(r.speaker,'Falante '+str(len(labels)+1))
        turns.append({'start_ms':max(0,round(r.start*1000)),'end_ms':min(round(r.end*1000),round(count/16)), 'speaker':label})
    if not turns:raise ValueError('DIARIZATION_NO_SPEECH')
    return {'method':'sherpa-onnx-pyannote3-eres2net','turns':turns,'speaker_count':len(labels),
            'model_sha256':manifest['sha256'],'cluster_threshold':cluster_threshold,'notice':'Falantes estimados por áudio, válidos somente nesta gravação. Revise; não identificam pessoas pelo nome.'}


def process_speakers(library,key,model_dir):
    try:
        data=diarize(library.audio_path(key),model_dir)
        library.save_speakers(key,data)
    except Exception:
        library.fail_speakers(key,'DIARIZATION_FAILED')


def child(root,key,model_dir):
    from .recordings import Library
    process_speakers(Library(root),key,model_dir)
