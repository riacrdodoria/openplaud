"""Evidence-preserving local analysis and retrieval. No outbound inference calls."""
import re

def analyze(segments):
    # These are literal candidate excerpts, never assertions of model understanding.
    decisions=[];actions=[]
    for s in segments:
        text=s['text'].strip()
        evidence={'segment_index':s['index'],'start_ms':s['start_ms'],'end_ms':s['end_ms']}
        if re.search(r'\b(decidimos|decidido|ficou definido|aprovamos|decisão|we decided|agreed|decision)\b',text,re.I):
            decisions.append({'text':text,**evidence,'confirmed':False})
        if re.search(r'\b(vou|vamos|precisamos|deverá|responsável|enviar|entregar|we will|i will|need to|action item)\b',text,re.I):
            actions.append({'text':text,**evidence,'owner_suggestion':None,'due_at':None,'confirmed':False})
    highlights=[{'text':s['text'], 'segment_index':s['index'],'start_ms':s['start_ms']} for s in segments[:5]]
    return {'method':'extractive-v1','summary':' '.join(s['text'] for s in segments[:5]),
            'highlights':highlights,'decisions':decisions,'action_items':actions,
            'notice':'Resumo extrativo. Decisões e tarefas são trechos candidatos para revisão; responsáveis não são inferidos.'}


def answer(library,question,keys=None):
    hits=library.search_segments(question,keys)
    citations=[]
    for hit in hits:
        recording=library.detail(hit['recording_id'])
        segment=recording['transcript']['segments'][int(hit['segment_index'])]
        citations.append({'recording_id':hit['recording_id'],'name':hit['name'],**segment})
    return {'answer':'\n'.join(s['text'] for s in citations) if citations else 'Não encontrei trechos correspondentes nas gravações selecionadas.',
            'citations':citations,'method':'local-retrieval-v1',
            'notice':'Resposta por recuperação de trechos; não é uma resposta gerada por LLM.'}
