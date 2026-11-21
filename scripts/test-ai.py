"""Real local-model smoke test; never downloads weights. Run against test server."""
import json, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=60)
def wait(job):
    deadline = time.monotonic()+240
    while time.monotonic()<deadline:
        data=client.get('/api/jobs/'+job['id']).json()
        if data['status'] in ('completed','failed'):
            assert data['status']=='completed', data
            return data
        time.sleep(1)
    raise AssertionError('Timed out waiting for local AI')

with (ROOT/'test-output/speech.mp4').open('rb') as f:
    response=client.post('/api/projects',files={'file':('speech.mp4',f,'video/mp4')},data={'title':'AI verification'})
response.raise_for_status()
p=response.json(); path='/api/projects/'+p['id']
t=client.post(path+'/transcribe',json={'model':'base.en','language':'en','allow_download':False})
t.raise_for_status(); transcription=wait(t.json())
assert len(transcription['result']['segments'])>0
suggest=client.post(path+'/suggest',json={'provider':'ollama','model':'qwen2.5:7b','min_duration':3,'max_duration':30,'count':2})
suggest.raise_for_status(); suggestions=wait(suggest.json())
assert suggestions['result']['clips']
report={'project_id':p['id'],'transcription':transcription,'suggestions':suggestions}
(ROOT/'test-output/ai-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'transcription':'passed','segments':len(transcription['result']['segments']),'ollama':'passed','clips':len(suggestions['result']['clips'])}))
