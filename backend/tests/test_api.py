import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main, media
from backend.store import Store


@pytest.fixture()
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,"DATA",tmp_path/"data")
    monkeypatch.setattr(main,"store",Store(tmp_path/"data"))
    with TestClient(main.app) as client:
        yield client


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    folder=tmp_path_factory.mktemp("media")
    path=folder/"sample.mp4"
    subprocess.run([media.binary("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=size=320x180:rate=12","-f","lavfi","-i","sine=frequency=440:sample_rate=16000","-t","4","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(path)],check=True)
    return path


def upload(client,video):
    with video.open("rb") as source:
        response=client.post("/api/projects",files={"file":("sample.mp4",source,"video/mp4")},data={"title":"Test source"})
    assert response.status_code==201,response.text
    return response.json()


def wait_job(client,id):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        job=client.get("/api/jobs/"+id).json()
        if job["status"] in ("completed","failed"):
            assert job["status"]=="completed",job
            return job
        time.sleep(.1)
    pytest.fail("Job timed out")


def test_full_export_flow(client,video):
    p=upload(client,video)
    assert p["has_audio"] and p["duration"]>=4
    assert client.get(p["video_url"],headers={"Range":"bytes=0-99"}).status_code==206
    assert client.get(p["thumbnail_url"]).status_code==200
    transcript="1\n00:00:00,000 --> 00:00:01,800\nHello {danger} \\N world!\n\n2\n00:00:02,000 --> 00:00:03,900\nMake a useful clip.\n"
    response=client.post(f"/api/projects/{p['id']}/transcript/import",files={"file":("captions.srt",transcript,"text/plain")})
    assert response.status_code==200,response.text
    assert len(response.json()["segments"])==2
    assert "Hello" in client.get(f"/api/projects/{p['id']}/transcript?format=srt").text
    clip=client.post(f"/api/projects/{p['id']}/clips",json={"title":"Export test","start":.5,"end":3.5,"aspect":"9:16","fit":"contain","caption_style":"karaoke"}).json()
    response=client.post(f"/api/projects/{p['id']}/clips/{clip['id']}/export",json={"resolution":720})
    assert response.status_code==202,response.text
    job=wait_job(client,response.json()["id"])
    export=job["result"]
    assert (export["width"],export["height"])==(720,1280)
    assert abs(export["duration"]-3)<.2
    result=client.get(export["url"])
    assert result.status_code==200 and result.content[4:8]==b"ftyp"
    assert "attachment" in result.headers["content-disposition"]
    assert client.get(export["thumbnail_url"]).status_code==200
    assert len(client.get(f"/api/projects/{p['id']}").json()["exports"])==1
    assert client.delete(f"/api/projects/{p['id']}").status_code==204
    assert client.get(f"/api/projects/{p['id']}").status_code==404


@pytest.mark.parametrize("aspect,expected",[("1:1",(720,720)),("16:9",(1280,720)),("4:5",(720,900))])
def test_crop_ratios(client,video,aspect,expected):
    p=upload(client,video)
    clip=client.post(f"/api/projects/{p['id']}/clips",json={"start":0,"end":.5,"aspect":aspect,"fit":"crop","crop_x":.2,"burn_captions":False}).json()
    response=client.post(f"/api/projects/{p['id']}/clips/{clip['id']}/export",json={"resolution":720})
    export=wait_job(client,response.json()["id"])["result"]
    assert (export["width"],export["height"])==expected


def test_bad_inputs_and_heuristic(client,video):
    p=upload(client,video)
    url=f"/api/projects/{p['id']}"
    assert client.post(url+"/clips",json={"start":3,"end":2}).status_code==422
    assert client.post(url+"/clips",json={"start":0,"end":9}).status_code==422
    assert client.post(url+"/clips",json={"start":0,"end":2,"caption_color":"red;bad"}).status_code==422
    assert client.put(url+"/transcript",json={"segments":[{"start":0,"end":3,"text":"one"},{"start":2,"end":4,"text":"two"}]}).status_code==400
    assert client.post("/api/projects",files={"file":("bad.mp4",b"not a video")}).status_code==400
    response=client.post(url+"/suggest",json={"provider":"heuristic","min_duration":1,"max_duration":2,"count":2})
    clips=wait_job(client,response.json()["id"])["result"]["clips"]
    assert len(clips)==2
    assert clips[0]["suggestion_provider"]=="heuristic"
    assert len(client.get(url).json()["clips"])==2
    updated=client.put(url+"/clips/"+clips[0]["id"],json={"start":.2,"end":1.8,"title":"Edited"})
    assert updated.status_code==200 and updated.json()["title"]=="Edited"
    assert client.delete(url+"/clips/"+clips[0]["id"]).status_code==204
    assert client.post(url+"/clips",json={"start":0,"end":1},headers={"Origin":"https://evil.example"}).status_code==403
    assert client.get(url+"/exports/../../config/download").status_code==404


def test_subtitles_and_ass():
    rows=media.parse_subtitles("WEBVTT\n\n00:00.000 --> 00:01.000\n<v Narrator>Hello</v>\n")
    assert rows==[{"start":0,"end":1,"text":"Hello"}]
    assert "{\\" not in media.escape_ass("{\\pos(1,2)} text")
    assert media.timestamp(1.9996)=="00:00:02,000"


def test_restart_recovery(tmp_path):
    store=Store(tmp_path)
    store.put_job({"id":"job","project_id":"p","status":"running"})
    store.recover_jobs()
    assert store.job("job")["status"]=="failed"


def test_silent_video_1080_and_empty_subtitles(client, tmp_path):
    source=tmp_path/"silent.mp4"
    subprocess.run([media.binary("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=blue:s=160x120:r=10","-t","1","-c:v","libx264","-pix_fmt","yuv420p",str(source)],check=True)
    p=upload(client,source)
    assert not p['has_audio']
    path=f"/api/projects/{p['id']}"
    assert client.post(path+'/transcribe',json={'model':'base.en','allow_download':False}).status_code==422
    assert client.post(path+'/transcript/import',files={'file':('bad.srt','not timed captions')}).status_code==400
    clip=client.post(path+'/clips',json={'start':0,'end':.5,'aspect':'9:16','caption_style':'none'}).json()
    job=client.post(path+f"/clips/{clip['id']}/export",json={'resolution':1080}).json()
    result=wait_job(client,job['id'])['result']
    assert (result['width'],result['height'])==(1080,1920)


def test_cache_reuse_without_network(tmp_path, monkeypatch):
    cache=tmp_path/'hub'/'models--Systran--faster-whisper-base.en'/'snapshots'/'revision'
    cache.mkdir(parents=True)
    for f in ('model.bin','config.json','tokenizer.json'):
        (cache/f).write_text('fixture')
    monkeypatch.setenv('HF_HUB_CACHE',str(tmp_path/'hub'))
    assert main.cached_speech_model('base.en')==str(cache)
    assert main.cached_speech_model('medium') is None


def test_link_import_and_sliced_export(client, monkeypatch, tmp_path):
    # Invalid URL returns 400
    res = client.post("/api/projects/link", json={"url": "not-a-valid-url"})
    assert res.status_code == 400

    from backend import downloader

    # Mock extract_info
    monkeypatch.setattr(downloader, "extract_info", lambda url, *args, **kwargs: {
        "id": "mock_yt_123",
        "title": "Mock YouTube Stream",
        "duration": 180.0,
        "width": 1920,
        "height": 1080,
        "thumbnail": None
    })

    # Mock extract_subtitles
    monkeypatch.setattr(downloader, "extract_subtitles", lambda info, *args, **kwargs: [
        {"id": "s1", "start": 10.0, "end": 14.0, "text": "This is a great moment in the video."}
    ])

    # Mock preview proxy download (creates tiny blank mp4)
    def mock_preview(url, out, *args, **kwargs):
        subprocess.run([media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:r=10", "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
    monkeypatch.setattr(downloader, "download_preview_proxy", mock_preview)

    # Mock clip section slice download
    downloaded_ranges = []
    def mock_download_slice(url, start, end, out, max_height=1080, *args, **kwargs):
        downloaded_ranges.append((start, end, max_height))
        duration = max(0.5, end - start)
        subprocess.run([media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)], check=True)
    monkeypatch.setattr(downloader, "download_clip_section", mock_download_slice)

    # Import link
    res = client.post("/api/projects/link", json={
        "url": "https://www.youtube.com/watch?v=mock_yt_123",
        "title": "Custom Title",
        "fetch_subtitles": True
    })
    assert res.status_code == 202
    job_id = res.json()["id"]
    completed_job = wait_job(client, job_id)
    project_id = completed_job["project_id"]

    # Verify project properties
    p = client.get(f"/api/projects/{project_id}").json()
    assert p["is_link"] is True
    assert p["source_url"] == "https://www.youtube.com/watch?v=mock_yt_123"
    assert p["title"] == "Custom Title"
    assert len(p["segments"]) == 1
    assert p["segments"][0]["text"] == "This is a great moment in the video."

    # Create a clip spanning 10s to 15s
    clip_res = client.post(f"/api/projects/{project_id}/clips", json={
        "start": 10.0,
        "end": 15.0,
        "title": "Viral Hook",
        "aspect": "9:16",
        "caption_style": "bold"
    })
    assert clip_res.status_code == 201
    clip_id = clip_res.json()["id"]

    # Export the clip at 720p
    exp_job_res = client.post(f"/api/projects/{project_id}/clips/{clip_id}/export", json={"resolution": 720})
    assert exp_job_res.status_code == 202
    exp_job = wait_job(client, exp_job_res.json()["id"])
    assert exp_job["status"] == "completed"

    # Verify download_clip_section was invoked with exact start and end slice
    assert len(downloaded_ranges) == 1
    assert downloaded_ranges[0] == (10.0, 15.0, 720)

    # Verify export file is accessible
    export_result = exp_job["result"]
    assert export_result["width"] == 720
    assert export_result["height"] == 1280
    assert client.get(export_result["url"]).status_code == 200


def test_extract_audio_wav_and_no_audio_handling(tmp_path):
    from backend import transcription_worker, media
    import pytest

    # 1. Video with audio
    vid_with_audio = tmp_path / "with_audio.mp4"
    subprocess.run([
        media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
        "-t", "1",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", str(vid_with_audio)
    ], check=True)

    wav_out = transcription_worker.extract_audio_wav(vid_with_audio)
    assert Path(wav_out).is_file()
    assert Path(wav_out).stat().st_size > 100
    try:
        Path(wav_out).unlink()
    except OSError:
        pass

    # 2. Silent video with NO audio stream
    vid_silent = tmp_path / "silent.mp4"
    subprocess.run([
        media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=160x120:r=10",
        "-t", "1",
        "-c:v", "libx264",
        str(vid_silent)
    ], check=True)

    with pytest.raises(ValueError, match="no audio track"):
        transcription_worker.extract_audio_wav(vid_silent)


def test_downloader_ensure_mp4_remux(tmp_path):
    from backend import downloader, media

    target_mp4 = tmp_path / "source.mp4"
    fake_webm = tmp_path / "source.mp4.webm"
    # Create webm file
    subprocess.run([
        media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
        "-t", "1",
        "-shortest", str(fake_webm)
    ], check=True)

    assert not target_mp4.is_file()
    assert fake_webm.is_file()

    out = downloader._ensure_mp4_output(target_mp4)
    assert out.is_file()
    assert target_mp4.is_file()
    assert target_mp4.stat().st_size > 1000
    meta = media.probe(target_mp4)
    assert meta["has_audio"] is True

