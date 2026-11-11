import io
import os
import tempfile
import unittest
from unittest.mock import patch
from openplaud.recordings import Library
from openplaud.providers import Transcript,Segment
from openplaud.chat import answer,context

class ChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.lib=Library(self.tmp.name)
        self.keys=[]
        for i,text in enumerate(('Decidimos aprovar o orçamento de dez reais.','O orçamento mudou para vinte reais.')):
            key=self.lib.ingest(io.BytesIO(str(i).encode()),str(i)+'.wav');self.keys.append(key)
            self.lib.save_transcript(key,Transcript('pt',(Segment(1000,3000,text),),'fixture'))
    def test_multi_recording_citations_and_scope(self):
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate',return_value={'claims':[{'text':'Orçamento mudou de dez para vinte.','source_ids':[0,1]}]}):
            r=answer(self.lib,'Como mudou o orçamento?',self.keys)
        self.assertEqual(r['method'],'local-grounded-chat-v1');self.assertEqual({x['recording_id'] for x in r['citations']},set(self.keys))
        refs,total=context(self.lib,'orçamento',[self.keys[0]],[])
        self.assertEqual({r['recording_id'] for r in refs},{self.keys[0]})
        self.assertEqual(answer(self.lib,'orçamento',[])['citations'],[])
    def test_invalid_citation_or_provider_failure_returns_literal_excerpts(self):
        for data in ({'claims':[{'text':'invented','source_ids':[99]}]}, {'claims':[{'text':'invented','source_ids':[True]}]}):
            with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate',return_value=data):r=answer(self.lib,'orçamento',self.keys)
            self.assertEqual(r['method'],'local-excerpts');self.assertNotIn('invented',r['answer'])
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate',side_effect=TimeoutError()):r=answer(self.lib,'orçamento',self.keys)
        self.assertEqual(r['method'],'local-excerpts');self.assertTrue(r['citations'])
    def test_abstention(self):
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate',return_value={'claims':[]}):r=answer(self.lib,'Quem venceu a eleição?',self.keys)
        self.assertEqual(r['method'],'insufficient-evidence');self.assertEqual(r['citations'],[])

    def test_unmatched_question_never_invokes_model_with_unrelated_evidence(self):
        with patch.dict(os.environ,{'OPENPLAUD_OLLAMA_URL':'http://ollama:11434'}),patch('openplaud.chat.generate') as model:
            r=answer(self.lib,'Qual é o nome do fornecedor contratado?',self.keys)
            model.assert_not_called()
        self.assertEqual(r['method'],'insufficient-evidence')
        refs,total=context(self.lib,'Resuma as gravações',self.keys,[])
        self.assertEqual({r['recording_id'] for r in refs},set(self.keys))
