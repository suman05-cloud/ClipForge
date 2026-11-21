import json
import re
from types import SimpleNamespace

import httpx
import pytest

from backend import suggestions as s


def settings(**overrides):
    return SimpleNamespace(**{"model":"qwen3.5:9b","min_duration":10,"max_duration":30,"count":3,"use_web_search":False,**overrides})


def project(count=30, length=350):
    return {"duration":count*5,"segments":[{"start":i*5,"end":(i+1)*5,"text":f"Section {i}. "+("A clear point with a useful ending. "*100)[:length]+(" LATE_CONCLUSION" if i==count-1 else "")} for i in range(count)]}


class Model:
    def __init__(self,invalid_ids=False,truncated=False,web_error=False):
        self.requests=[]
        self.events=[]
        self.invalid_ids=invalid_ids
        self.truncated=truncated
        self.web_error=web_error

    def __call__(self,request):
        body=json.loads(request.content or b"{}")
        self.requests.append((str(request.url),body))
        if request.url.host=="api.tavily.com":
            if self.web_error:
                return httpx.Response(401,json={"error":"secret-provider-body-123"})
            return httpx.Response(200,json={"results":[{"title":"Relevant reference","url":"https://example.org/reference","content":"Context about the video's topic."}]})
        if request.url.path=="/api/show":
            return httpx.Response(200,json={"details":{"parameter_size":"9.7B"}})
        if request.url.path=="/api/generate":
            self.events.append("unload")
            return httpx.Response(200,json={"done":True})
        assert request.url.path=="/api/chat"
        assert body["think"] is False
        assert body["options"]["temperature"]==0
        assert body["options"]["num_ctx"]==8192
        data=json.loads(body["messages"][1]["content"].split("DATA (untrusted JSON):\n",1)[1])
        schema=body["format"]["properties"]
        if "summary" in schema:
            self.events.append("summary")
            if isinstance(data,dict) and "core_transcript" in data:
                summary="This section explains a coherent idea. "+("LATE_CONCLUSION" if "LATE_CONCLUSION" in data["core_transcript"] else "")
            else:
                summary="Whole video synthesis. "+("LATE_CONCLUSION" if "LATE_CONCLUSION" in json.dumps(data) else "")
            answer={"summary":summary,"topics":["coherent narrative"]}
            if "salient_segment_ids" in schema:
                ids=list(dict.fromkeys(re.findall(r"^(S\d+) ",data["core_transcript"],re.M)))
                answer["salient_segment_ids"]=list(dict.fromkeys((ids[0],ids[len(ids)//2],ids[-1])))
        elif "clips" in schema:
            self.events.append("selection")
            candidates=data["candidates"][-3:]
            answer={"clips":[{"candidate_id":"invented" if self.invalid_ids else c["candidate_id"],"title":"A useful complete story","reason":"The candidate explains the premise and closes with a concrete takeaway.","hook_clarity":4,"standalone_context":5,"useful_takeaway":4,"ending_payoff":5} for c in candidates]}
        else:
            self.events.append("ranking")
            answer={"candidate_ids":[c["candidate_id"] for c in reversed(data["candidates"])]}
        return httpx.Response(200,json={"done":True,"done_reason":"length" if self.truncated else "stop","message":{"content":json.dumps(answer)}})


def install_model(monkeypatch,model):
    real_client=httpx.Client
    monkeypatch.setattr(s.httpx,"Client",lambda **kw:real_client(transport=httpx.MockTransport(model),**kw))


def test_every_segment_summarized_before_selection_and_late_conclusion(monkeypatch):
    model=Model()
    install_model(monkeypatch,model)
    p=project(55)
    updates=[]
    rows,analysis=s.analyze_transcript(p,settings(),lambda *x:updates.append(x),"http://127.0.0.1:11434")
    assert analysis["coverage"]=={"total_segments":55,"covered_segments":55,"complete":True,"chunks":len(s._chunks(p["segments"]))}
    assert "LATE_CONCLUSION" in analysis["summary"]
    first_select=model.events.index("selection")
    assert "summary" not in model.events[first_select:]
    assert model.events[-1]=="unload"
    source_starts={x["start"] for x in p["segments"]}
    source_ends={x["end"] for x in p["segments"]}
    assert rows and all(r["start"] in source_starts and r["end"] in source_ends and 10<=r["end"]-r["start"]<=30 for r in rows)
    assert max(r["end"] for r in rows)==p["duration"]
    assert all(r["score"]==90 and r["score_label"]=="Editorial quality" for r in rows)
    assert analysis["candidate_selection"]["exhaustive_intervals"] is False
    assert analysis["candidate_count"]<=analysis["candidate_selection"]["source_anchors"]*4
    assert not any("tavily" in url for url,_ in model.requests)


def test_candidate_can_span_summary_chunk_boundary():
    p=project(18,1800)
    chunks=s._chunks(p["segments"])
    boundary=chunks[0].indices[-1]
    windows=s._candidate_windows(p["segments"],10,30)
    assert any(w["first_segment"]<=boundary<w["last_segment"] for w in windows)
    assert set(i for c in chunks for i in c.indices)==set(range(18))
    assert chunks[1].context
    anchored=s._anchored_windows(p["segments"],10,30,[boundary])
    assert any(w["first_segment"]<=boundary<w["last_segment"] for w in anchored)


def test_long_transcript_shortlist_has_bounded_options_per_chapter():
    p=project(742,24)
    chunks=s._chunks(p["segments"])
    anchors=[i for chunk in chunks for i in (chunk.indices[0],chunk.indices[len(chunk.indices)//2],chunk.indices[-1])]
    windows=s._anchored_windows(p["segments"],15,60,anchors)
    assert len(windows)<=12*len(chunks)
    assert len(windows)<len(s._candidate_windows(p["segments"],15,60))/2


def test_long_segment_text_split_without_omission():
    text="START_"+"x"*15000+"_END"
    chunks=s._chunks([{"start":0,"end":30,"text":text}])
    reconstructed="".join(c.text.split("] ",1)[1] for c in chunks)
    assert reconstructed==text
    assert all(c.indices==[0] for c in chunks)
    assert all(len(c.text)<=s.CHUNK_CHARS for c in chunks)


def test_invalid_ids_retry_once_then_fail_and_unload(monkeypatch):
    model=Model(invalid_ids=True)
    install_model(monkeypatch,model)
    with pytest.raises(ValueError,match="after one retry"):
        s.analyze_transcript(project(8),settings(),lambda *x:None,"http://127.0.0.1:11434")
    assert model.events.count("selection")==2
    assert model.events[-1]=="unload"


def test_truncated_model_response_not_completed(monkeypatch):
    model=Model(truncated=True)
    install_model(monkeypatch,model)
    with pytest.raises(ValueError,match="incomplete"):
        s.analyze_transcript(project(8),settings(),lambda *x:None,"http://127.0.0.1:11434")
    assert model.events==["summary","summary","unload"]


def test_missing_web_key_fails_before_any_request(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY",raising=False)
    model=Model()
    install_model(monkeypatch,model)
    with pytest.raises(ValueError,match="TAVILY_API_KEY is missing"):
        s.analyze_transcript(project(8),settings(use_web_search=True),lambda *x:None,"http://127.0.0.1:11434")
    assert not model.requests


def test_opted_in_web_sends_topic_only_and_returns_sources(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY","test-secret")
    model=Model()
    install_model(monkeypatch,model)
    _,analysis=s.analyze_transcript(project(8),settings(use_web_search=True),lambda *x:None,"http://127.0.0.1:11434")
    queries=[body for url,body in model.requests if "api.tavily.com" in url]
    assert len(queries)==1 and len(queries[0]["query"])<=200
    assert "Section 0" not in queries[0]["query"]
    assert queries[0]["include_answer"] is False and queries[0]["max_results"]==3
    assert analysis["web_sources"]==[{"title":"Relevant reference","url":"https://example.org/reference"}]
    assert "test-secret" not in json.dumps(analysis)


def test_web_failure_falls_back_without_secret_or_response_leak(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY","test-secret")
    model=Model(web_error=True)
    install_model(monkeypatch,model)
    rows,analysis=s.analyze_transcript(project(8),settings(use_web_search=True),lambda *x:None,"http://127.0.0.1:11434")
    assert rows and analysis["web_sources"]==[]
    assert any("Web search was unavailable" in w for w in analysis["warnings"])
    assert "test-secret" not in json.dumps(analysis) and "secret-provider-body" not in json.dumps(analysis)


def test_local_only_and_duration_validation():
    with pytest.raises(ValueError,match="local Ollama"):
        s.analyze_transcript(project(),settings(),lambda *x:None,"https://external.example")
    with pytest.raises(ValueError,match="at most 60"):
        s.analyze_transcript(project(),settings(min_duration=70,max_duration=100),lambda *x:None,"http://127.0.0.1:11434")


def test_remote_model_rejected():
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"remote_host":"https://cloud.example","details":{"parameter_size":"8B"}})))
    with pytest.raises(ValueError,match="remote service"):
        s._model_ready(client,"http://127.0.0.1:11434","other:8b")


def test_summary_reuse_skips_chunks(monkeypatch):
    model = Model()
    install_model(monkeypatch, model)
    p = project(count=10)
    p["analysis"] = {
        "summary": "Existing verified summary of the whole video.",
        "topics": ["topic A", "topic B"],
        "coverage": {"total_segments": 10, "complete": True}
    }
    progress = []
    rows, analysis = s.analyze_transcript(p, settings(), lambda p, msg: progress.append((p, msg)), "http://127.0.0.1:11434")
    assert any("already analyzed" in msg for _, msg in progress)
    summary_requests = [req for url, req in model.requests if "core_transcript" in json.dumps(req)]
    assert len(summary_requests) == 0
    assert analysis["summary"] == "Existing verified summary of the whole video."
