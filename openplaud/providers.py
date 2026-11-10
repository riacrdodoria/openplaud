"""Provider boundary: privacy checks precede any call, no default cloud fallback."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None

@dataclass(frozen=True)
class Transcript:
    language: str
    segments: tuple[Segment,...]
    provider: str

class TranscriptionProvider(Protocol):
    external: bool
    def transcribe(self,audio:Path,language:str) -> Transcript: ...

class PrivacyError(PermissionError):pass


def transcribe(provider:TranscriptionProvider,audio:Path,language='pt',privacy='local-only',cloud_authorized=False):
    if privacy not in ('local-only','cloud-approved'):raise ValueError('unknown privacy policy')
    if language not in ('pt','en','auto'):raise ValueError('unsupported language')
    # cloud-approved is necessary but not sufficient: an applicable usage authorization is required.
    if provider.external and (privacy!='cloud-approved' or not cloud_authorized):
        raise PrivacyError('External transcription is not authorized')
    if not audio.is_file():raise FileNotFoundError('audio unavailable')
    result=provider.transcribe(audio,language)
    if not isinstance(result,Transcript) or result.language not in ('pt','en') or not result.provider:
        raise ValueError('invalid transcript metadata')
    previous=0
    for s in result.segments:
        if not isinstance(s,Segment) or type(s.start_ms) is not int or type(s.end_ms) is not int:
            raise ValueError('invalid segment')
        if s.start_ms<previous or s.end_ms<=s.start_ms or not s.text.strip():
            raise ValueError('invalid timestamp or text')
        previous=s.start_ms  # overlaps are allowed for simultaneous speakers
    if not result.segments:raise ValueError('empty transcript')
    return result
