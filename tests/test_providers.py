from pathlib import Path
import tempfile
import unittest
from openplaud.providers import Segment,Transcript,transcribe,PrivacyError
class Fake:
    external=True
    calls=0
    result=Transcript('pt',(Segment(0,1000,'Texto sintético'),),'fixture')
    def transcribe(self,audio,language):self.calls+=1;return self.result
class ProviderTests(unittest.TestCase):
    def test_cloud_never_called_without_both_consents(self):
        f=Fake()
        for privacy,authorized in [('local-only',False),('local-only',True),('cloud-approved',False)]:
            with self.assertRaises(PrivacyError):transcribe(f,Path('/not/read'),privacy=privacy,cloud_authorized=authorized)
        self.assertEqual(f.calls,0)
    def test_local_and_external_authorized(self):
        with tempfile.NamedTemporaryFile() as file:
            f=Fake();f.external=False
            self.assertEqual(transcribe(f,Path(file.name)).language,'pt')
            f.external=True
            self.assertEqual(transcribe(f,Path(file.name),privacy='cloud-approved',cloud_authorized=True).provider,'fixture')
    def test_bad_timestamps_and_failure_preserve_file(self):
        with tempfile.NamedTemporaryFile() as file:
            f=Fake();f.external=False;f.result=Transcript('pt',(Segment(100,0,'bad'),),'fixture')
            with self.assertRaises(ValueError):transcribe(f,Path(file.name))
            self.assertTrue(Path(file.name).exists())
    def test_no_implicit_fallback(self):
        class Failing(Fake):
            external=False
            def transcribe(self,audio,language):raise TimeoutError('fixture timeout')
        with tempfile.NamedTemporaryFile() as file:
            with self.assertRaises(TimeoutError):transcribe(Failing(),Path(file.name))
            self.assertTrue(Path(file.name).exists())
