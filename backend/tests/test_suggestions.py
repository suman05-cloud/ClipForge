import json
import httpx
import pytest
from backend import main


def install_model(monkeypatch, replies):
    requests=[]
    def handle(request):
        if request.url.path=='/api/show':
            return httpx.Response(200,json={'details':{'parameter_size':'7.6B'}})
        data=json.loads(request.content)
        requests.append(data)
        content=replies.pop(0)
        return httpx.Response(200,json={'message':{'content':content}})
    real=httpx.Client
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handle)))
    return requests


PROJECT={'duration':100,'segments':[{'start':0,'end':25,'text':'A complete story.'},{'start':25,'end':50,'text':'A useful example.'}]}
VALID=json.dumps({'clips':[{'title':'A useful story','start':0,'end':25,'reason':'A clear example.'}]})


@pytest.mark.parametrize('bad',['{"clips": [', '{}', '{"clips":"wrong"}', '{"clips":[null]}'])
def test_schema_retry(monkeypatch,bad):
    requests=install_model(monkeypatch,[bad,VALID])
    clips,coverage=main.ollama_candidates(PROJECT,main.SuggestInput(count=5))
    assert clips[0]['end']==25
    assert len(requests)==2
    assert requests[0]['format']['required']==['clips']
    assert requests[0]['format']['properties']['clips']['maxItems']==5
    assert coverage['covered_segments']==2


def test_timestamp_rejection_and_retry_bound(monkeypatch):
    bad=json.dumps({'clips':[{'title':'Bad','start':80,'end':110,'reason':'Outside source.'}]})
    requests=install_model(monkeypatch,[bad,bad])
    with pytest.raises(ValueError,match='two attempts'):
        main.ollama_candidates(PROJECT,main.SuggestInput())
    assert len(requests)==2


def test_overlong_story_uses_real_caption_boundary(monkeypatch):
    long=json.dumps({'clips':[{'title':'Story','start':0,'end':50,'reason':'Clear sequence.'}]})
    install_model(monkeypatch,[long])
    clips,_=main.ollama_candidates(PROJECT,main.SuggestInput(min_duration=15,max_duration=30))
    assert clips[0]['end']==25
    assert 'Trimmed at a transcript boundary' in clips[0]['reason']
