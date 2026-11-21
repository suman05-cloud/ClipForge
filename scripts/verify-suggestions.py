"""Read-only verification against a saved project and the local Ollama model."""
import json, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import main

class DiagnosticClient(main.httpx.Client):
    def post(self,url,**kwargs):
        response=super().post(url,**kwargs)
        if url.endswith('/api/chat'):
            payload=response.json()
            content=payload.get('message',{}).get('content','')
            summary={'done_reason':payload.get('done_reason'),'output_chars':len(content),'eval_count':payload.get('eval_count')}
            try:
                parsed=json.loads(content)
                summary['keys']=list(parsed) if isinstance(parsed,dict) else type(parsed).__name__
                if isinstance(parsed,dict) and isinstance(parsed.get('clips'),list):
                    summary['rows']=[{k:v for k,v in row.items() if k in ('start','end')} for row in parsed['clips'] if isinstance(row,dict)]
                main.SuggestedMoments.model_validate_json(content)
            except Exception as exc:
                summary['validation_error']=type(exc).__name__
                if hasattr(exc,'errors'):
                    summary['issues']=[{'loc':e['loc'],'type':e['type']} for e in exc.errors()]
            print(json.dumps(summary),flush=True)
        return response

main.httpx.Client=DiagnosticClient

project=main.store.get(sys.argv[1])
if not project:
    raise SystemExit('Project not found')
started=time.monotonic()
clips,coverage=main.ollama_candidates(project,main.SuggestInput(provider='ollama',model='qwen2.5:7b',min_duration=15,max_duration=60,count=5))
print(json.dumps({'valid_clips':len(clips),'durations':[round(c['end']-c['start'],2) for c in clips],'elapsed_seconds':round(time.monotonic()-started,1),**coverage}))
