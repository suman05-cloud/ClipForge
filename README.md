# ClipForge Studio

A personal, local video editor inspired by the long-video-to-short-clips workflow investigated on ScaleReach. Bring your own video, find useful moments, edit captions and framing, render MP4 files, and download them. There are **no social-media connections, automatic posts, subscriptions, or required cloud AI accounts**.

This is original application code, not ScaleReach's source or private backend. The investigation can establish public pages and browser-delivered code, not the implementation of authenticated or server-only features.

## Start on this computer

From PowerShell:

```powershell
cd E:\REA\clipforge
.\start.ps1
```

Open **http://127.0.0.1:8000**. The script opens your browser once the server responds. To leave the browser closed or choose another port:

```powershell
.\start.ps1 -NoBrowser -Port 8001
```

Keep that terminal open. Press **Ctrl+C** to stop the server; projects and exports remain on disk. If your PowerShell execution policy blocks scripts, run this one script with a process-only policy override:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

## Install from the source

Prerequisites:

- Windows PowerShell 5.1+ or PowerShell 7.
- Python **3.11+** (3.12 recommended).
- Node.js **20.19+**, **22.12+**, or a newer supported LTS, with npm.
- FFmpeg and FFprobe on PATH. FFmpeg needs H.264 (`libx264`), AAC and the `subtitles`/libass filter for the supplied rendering workflow.

```powershell
cd E:\REA\clipforge
.\setup.ps1
.\start.ps1
```

Setup creates/reuses `.venv`, installs backend packages, installs frontend npm dependencies and builds `frontend/dist`. An existing uv-created environment without pip is supported: the script bootstraps pip with Python's bundled `ensurepip`. It checks tools but does not install system Python, Node, or FFmpeg.

Runtime discovery prefers PATH or explicit arguments. On the original workstation it can fall back to the existing REA Node directory and FFmpeg installation; those paths are not required on another computer. To provide custom tool locations:

```powershell
.\setup.ps1 -PythonExecutable 'C:\Python312\python.exe' -NodeDirectory 'C:\Program Files\nodejs' -FFmpegDirectory 'C:\tools\ffmpeg\bin'
.\start.ps1 -FFmpegDirectory 'C:\tools\ffmpeg\bin'
```

Optional speech-recognition dependencies and test tools:

```powershell
.\setup.ps1 -InstallTranscription -InstallDevTools
```

**Download behavior:** base setup downloads Python/npm packages, not AI model weights. Optional `setup-gpu.ps1` installs compatible NVIDIA CUDA/cuDNN runtime packages; these can be hundreds of MB and are libraries, not Whisper weights. Installing transcription dependencies can still be a substantial package download. The app does not pull Ollama models. Missing Whisper weights are downloaded only when you explicitly enable the download checkbox for a transcription request. Leave it unchecked to use an existing cache or receive a clear missing-model error. On this workstation, an existing **`base.en`** speech-model cache can be reused; select that cached model for English videos. No new speech-model download is needed for that path. Speech-recognition models are separate from Ollama language models.

## Make a video without any AI

1. Choose **New video**, upload a local video, and give the project a title. Common MP4/MOV/WebM/MKV files are accepted if FFmpeg can read them. The original source file is not modified; the app stores its own copy.
2. Create a clip and enter start/end times. Use the video preview to review the cut.
3. Choose vertical **9:16**, square **1:1**, or landscape **16:9**. Choose **crop** or **fit/contain**; adjust horizontal framing when cropping.
4. For captions, import a UTF-8 **SRT/WebVTT** transcript or enter timed captions manually. Edit the words/times and save. You can also export without captions.
5. Set the caption style, font size and colors. Save changes, choose **720p** or **1080p**, and render.
6. Download the finished **MP4** from the exports view. Upload it manually wherever you choose. The editor adds no watermark.

The source, saved clip settings, caption segments, export files and project metadata persist between restarts. Deleting a project removes the app's project data; download any exports you want to keep first.

## Optional local AI

### Automatic captions

Install optional transcription packages, then select **Transcribe**. Choose an already cached speech model, or explicitly allow the one-time weight download. Audio stays local. Use Auto/GPU when the compatible NVIDIA runtime is available, or CPU int8 as a fallback. The requested CPU budget is eight threads; this is not eight parallel speech models on the GPU. The app records the actual execution device and any fallback in the result. Models remain cached for reuse. Auto chooses CUDA when the driver and required DLLs are detected, then retries on CPU if the isolated GPU worker fails. Explicit GPU mode reports an error rather than silently switching to CPU. GPU execution uses float16, batch size 4 and beam size 1; CPU fallback uses int8, beam size 1 and one model worker with eight CPU threads. These speed-oriented settings can affect transcription quality; review the captions. `base.en` is for English; use a multilingual model for other languages. Automatic captions should be reviewed, especially names, accents, mixed languages and noisy speech.

To install the optional GPU runtime (no model weights), run `.\setup-gpu.ps1`, then restart ClipForge. If runtime DLLs already exist elsewhere, set `WHISPER_CUDA_PATH` to their directories.

### Suggested clips and titles

Save the complete transcript, then select **Find moments**. Ollama first summarizes all transcript chunks and the recording as a whole, then reviews source-aligned candidate windows and ranks a distinct shortlist. Read the summary, coverage and selection reasons before exporting. The editorial score measures four local review criteria; it is not a virality or views prediction. See [the exact selection method](docs/CLIP-SELECTION.md).

Available methods:

- **Transcript heuristic** works without a language model. It proposes transcript-based windows for review.
- **Ollama** sends the transcript to a local model. The requested default is the already-installed **`qwen3.5:9b`**; the app does not pull model weights. This installed artifact reports 9.7B parameters, accepted here following your explicit model choice. `qwen2.5:7b` remains a lower-memory installed alternative. Start Ollama and refresh the toolkit status if it is not detected. Choose minimum/maximum clip duration and count, then review suggested cuts.

Manual editing, rendering and download work without Ollama or Whisper. There is no hosted LLM/speech fallback. Optional Tavily search adds topic context only when explicitly enabled and configured; it can consume API credits. See [AI options, hardware and sources](docs/AI-OPTIONS.md) and [how clips are selected](docs/CLIP-SELECTION.md).

### Optional topic context with Tavily

Add `TAVILY_API_KEY` to the local `.env` file or backend environment, restart the app, and opt into web context in the analysis dialog. The default remains off. Search receives a short query derived from the video summary (at most 200 characters), not the complete transcript, video or audio. That query can still disclose its subject. Results supply up to three source links for context, not audience metrics or proof of popularity. A missing key is reported; a search outage falls back to local selection with a warning. API credits may apply.

## Configuration and storage

Copy `.env.example` to `.env` only if you need overrides. `start.ps1` reads these values as literal strings; it never executes file contents. The Python backend reads environment variables, so if you launch uvicorn yourself, set them in that shell.

| Setting | Default / purpose |
|---|---|
| `CLIPFORGE_DATA_DIR` | `data` beside this README; project database, uploads, exports and model cache |
| `CLIPFORGE_MAX_UPLOAD_MB` | `2048` MB upload ceiling |
| `CLIPFORGE_FFMPEG` | Optional full path to `ffmpeg.exe` |
| `CLIPFORGE_FFPROBE` | Optional full path to `ffprobe.exe` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434`; only loopback hosts are accepted |
| `TAVILY_API_KEY` | Optional backend secret, used only for opted-in topic searches |
| `WHISPER_CUDA_PATH` | Optional CUDA/cuDNN DLL directories, separated by semicolons on Windows |

Back up the entire data directory while the server is stopped to retain both SQLite metadata and media files. Source archives exclude videos, model weights, virtual environments, node_modules and personal data.

## Architecture

```text
Browser: React + TypeScript + Vite
        | localhost HTTP
Python: FastAPI + SQLite + one background job worker
        |-- FFmpeg / FFprobe: inspect, crop, captions, H.264/AAC export
        |-- optional faster-whisper: local speech-to-text
        |-- optional Ollama HTTP: local summaries and clip selection
        `-- optional Tavily HTTPS: opt-in topic query only
```

The built UI is served by the same FastAPI process. SQLite holds project/job metadata; files remain in the local data directory. A single media/AI worker reduces competing RAM/VRAM use. Interrupted jobs are marked failed after a server restart and can be retried. API documentation is available at `/docs` while the local server is running.

## Development and testing

For a backend development server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

For frontend hot reload, in a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

The Vite development proxy targets the backend on port 8000. Build the distributable UI after edits:

```powershell
cd frontend
npm.cmd run build
```

Run the automated tests from the project root after installing `requirements-dev.txt`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

See [verified test results](docs/VERIFICATION.md), [investigation and implementation plan](docs/INVESTIGATION.md), and [AI options](docs/AI-OPTIONS.md). The tests do not cover every possible video codec, language or hardware combination.

## Current boundaries

- This is a personal localhost app, not a hosted multi-user service. It has no login, billing, collaboration, distributed queue or social publishing. Keep it bound to `127.0.0.1`; do not expose it directly to a network.
- Uploads are limited to 2 GB by default and videos to 4 hours. Actual processing speed and available disk space depend on the machine. Longer files need enough space for the stored original plus every export.
- Highlights are transcript-based. There is no automatic speaker tracking, scene-aware B-roll, advanced video generation, voice cloning or guaranteed viral score.
- Framing is manually controlled. Fit mode can show padding. The browser preview is an editing aid; the rendered MP4 is the authoritative result.
- Browser playback depends on browser codecs. A source that FFmpeg can read may need conversion to H.264/AAC MP4 for reliable browser preview.
- Caption styling and exported timing should be reviewed before publishing; speech recognition and language-model suggestions can be wrong.
- Karaoke highlighting estimates equal word durations within each transcript segment; it is not word-aligned speech timing. Full AI analysis summarizes every saved transcript segment through bounded chunks before reviewing candidates. Summary compression and bounded candidate excerpts can miss nuance; complete input coverage is not a guarantee of complete understanding.
- Hosted AI alternatives are documented but not implemented. Optional Tavily topic search is separate and opt-in. You do not need a paid AI model or search key to use the complete manual workflow.

## Troubleshooting

- **FFmpeg missing:** add its `bin` directory to PATH or use `-FFmpegDirectory`. Ensure `ffprobe.exe` is in the same directory. Caption rendering requires libass.
- **Port busy:** run `start.ps1 -Port 8001`; the script will not terminate unrelated processes.
- **UI missing:** run `setup.ps1` or `npm.cmd run build` inside `frontend`.
- **Ollama unavailable:** start Ollama, verify a local model is installed, then refresh toolkit status. Manual editing remains available.
- **GPU unavailable:** run the optional GPU-runtime setup or provide compatible DLL directories, restart the server, and check toolkit status. Auto can retry on CPU; explicit GPU reports failure. Driver detection is not a benchmark.
- **Speech model missing:** select a cached model, import SRT/VTT instead, or explicitly allow the download. Installing faster-whisper alone does not provide model weights.
- **Render/transcription failed:** read the job error, fix the stated input/dependency issue, and retry. Source files are retained.




