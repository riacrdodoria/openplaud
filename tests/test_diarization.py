import io
import tempfile
import unittest
from unittest.mock import patch
from openplaud.diarization import assign_speakers,process_speakers
from openplaud.recordings import Library
from openplaud.providers import Transcript,Segment

class SpeakerTests(unittest.TestCase):
    def test_turn_alignment_mixed_overlap_and_silence(self):
        segments=[{'start_ms':i*1000,'end_ms':(i+1)*1000,'text':'fixture','index':i} for i in range(4)]
        turns=[{'start_ms':0,'end_ms':1000,'speaker':'Falante 1'},
               {'start_ms':1000,'end_ms':1500,'speaker':'Falante 1'},
               {'start_ms':1500,'end_ms':2000,'speaker':'Falante 2'},
               {'start_ms':2000,'end_ms':3000,'speaker':'Falante 1'},
               {'start_ms':2200,'end_ms':2400,'speaker':'Falante 2'}]
        out=assign_speakers(segments,turns)
        self.assertEqual(out[0]['speaker'],'Falante 1')
        self.assertTrue(all(s['speaker'] is None for s in out[1:]))
        self.assertNotIn('speaker',segments[0])
    def test_durable_queue_and_failure_preserve_reviewed_analysis(self):
        with tempfile.TemporaryDirectory() as root:
            lib=Library(root);key=lib.ingest(io.BytesIO(b'fixture'),'fixture.wav')
            lib.save_transcript(key,Transcript('pt',(Segment(0,1000,'fixture'),),'fixture'))
            analysis={'summary':'reviewed','action_items':[{'confirmed':True,'owner_suggestion':'fixture'}]}
            lib.save_analysis(key,analysis);lib.queue_speakers(key);lib.queue_speakers(key)
            self.assertEqual(lib.claim_speakers(),key);self.assertIsNone(lib.claim_speakers())
            with patch('openplaud.diarization.diarize',side_effect=ValueError('private error')):process_speakers(lib,key,'fixture')
            self.assertEqual(lib.detail(key)['analysis'],analysis)
            self.assertEqual(lib.detail(key)['status'],'DONE')
            self.assertEqual(lib.detail(key)['diarization']['error'],'DIARIZATION_FAILED')
            lib.queue_speakers(key);lib.claim_speakers()
            data={'turns':[{'start_ms':0,'end_ms':1000,'speaker':'Falante 1'}],'speaker_count':1}
            with patch('openplaud.diarization.diarize',return_value=data):process_speakers(lib,key,'fixture')
            lib.queue_speakers(key);self.assertIsNone(lib.claim_speakers())
            self.assertEqual(lib.detail(key)['transcript']['segments'][0]['speaker'],'Falante 1')
            self.assertEqual(lib.detail(key)['analysis'],analysis)
