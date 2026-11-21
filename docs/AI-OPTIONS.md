# AI models, execution and optional search

Updated 19 November 2026. These are ClipForge engineering choices, not claims about ScaleReach's private backend. Research uses primary documentation; local hardware/model facts come from this workstation's inspection.

## What is required

**No AI model is required for manual trimming, cropping, caption editing or MP4 export.** FFmpeg performs those media operations. Automatic transcription needs a speech-recognition model; transcript summaries, editorial ranking and suggested titles use a language model. Neither task requires generative video, a voice clone or a social-media connection.

The requested default is the **already-installed Ollama `qwen3.5:9b`**. ClipForge uses that local installation; it does not pull a new copy. The installed artifact reported 9.7B parameters and about 6.59 GB storage during inspection. This is a deliberate exception to the earlier strict <=9B preference, following the explicit request to use this tag. Tag names and remote defaults can change; the installed artifact is the relevant runtime. The [official model page](https://ollama.com/library/qwen3.5:9b) describes its text/vision capabilities, but this application supplies transcript text rather than raw video frames.

`qwen2.5:7b` remains an already-installed, lower-memory alternative (approximately 4.68 GB Q4 weights). It can be selected if the requested default is too slow or memory-constrained. The [official model metadata](https://ollama.com/library/qwen2.5:7b) lists 7.62B parameters and structured-output capability. Smaller optional alternatives include [Qwen3 4B](https://ollama.com/library/qwen3:4b); do not download extra models just to use the manual workflow.

## This computer and realistic GPU use

This workstation has a Ryzen 7 7840HS (8 physical cores / 16 logical processors), approximately 16 GB RAM and an RTX 4050 Laptop GPU with 6,141 MiB VRAM. Ollama is available at `http://127.0.0.1:11434`. FFmpeg is installed separately.

A roughly 6.6 GB model file plus runtime/context memory does not fit entirely into 6 GB VRAM. Ollama may split execution across GPU and CPU memory; the application cannot promise full-GPU execution. Increasing context size also consumes memory. Use bounded transcript chunks and check actual loaded-model placement through Ollama's `/api/ps` or CLI `ps`, as documented in the [Ollama FAQ](https://docs.ollama.com/faq).

**Eight CPU threads means CPU assistance or a CPU inference/fallback budget, not eight simultaneous models on one GPU.** ClipForge keeps heavy jobs serialized. Loading Whisper and the language model concurrently can exhaust VRAM and slow both. GPU kernels do the model's accelerated compute; audio decoding, preprocessing, orchestration and CPU fallback still use the host processor. Hardware detection by itself is not a measured speedup. See the actual build's [verification record](VERIFICATION.md) for observed runs; no benchmark is inferred from model sizes or vendor examples.

## Speech recognition

Use the existing cached **`base.en`** for English without a new model download. For other languages, choose an appropriate cached multilingual model. Models missing from cache require the explicit download checkbox; installing the faster-whisper Python package alone does not install weights.

faster-whisper can use CUDA acceleration or CPU int8 inference. GPU support needs compatible NVIDIA drivers and CUDA/cuBLAS/cuDNN runtime libraries; seeing the GPU in `nvidia-smi` is not sufficient. Current upstream requirements identify CUDA 12 cuBLAS and cuDNN 9 for recent CTranslate2 releases. See [faster-whisper installation requirements](https://github.com/SYSTRAN/faster-whisper). Runtime-library setup is distinct from downloading speech models. Optional `setup-gpu.ps1` installs those runtime dependencies and can download hundreds of MB (the selected cuDNN archive is approximately 648 MB). The original workstation reuses existing Ollama CUDA12 libraries where possible. For an existing custom installation, `WHISPER_CUDA_PATH` accepts runtime directories separated by semicolons on Windows. Restart the app after runtime changes because capability discovery is cached.

CTranslate2 distinguishes device, compute precision, worker count and CPU intra-operation threads. Setting eight CPU threads does not allocate eight GPUs or create eight copies of Whisper. More batching/workers may consume more VRAM and is not automatically faster for a short recording. See [CTranslate2 Whisper parameters](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html). The app uses GPU float16 with batch size 4 and beam size 1, or CPU int8 with beam size 1, eight CPU threads and one worker. Auto checks for the NVIDIA device and compatible runtime libraries, runs Whisper in an isolated subprocess, and retries on CPU if the GPU worker fails. Explicit CUDA mode fails rather than silently falling back. Consult the job result's actual `device`, `cpu_threads` and `warnings`, rather than assuming that an Auto request ran on GPU. These are speed-oriented settings; caption accuracy still needs review.

## Full-transcript reasoning

The upgraded workflow reads saved transcript content across the entire recording in bounded chunks, summarizes those chunks and combines them into global context, then proposes and ranks timestamp-grounded candidate windows. It does not mean the complete raw transcript fits into one model prompt. See [clip-selection method and limits](CLIP-SELECTION.md).

Local Ollama supports JSON-schema response formats, but the backend still needs to validate IDs, time ranges, durations and scores. A schema cannot make a model's interpretation correct. See [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs). Review recommended clips in context before publishing.

## Optional Tavily topic search

Tavily is **off by default**. It is only used when the user opts into web context for a suggestion request and configures `TAVILY_API_KEY` on the backend. Only a short model-derived topic query (up to 200 characters, using topics or a summary fallback) is sent to Tavily; the full transcript, uploaded video and audio are not sent. A query can still reveal topics or brief summary details, so leave web context disabled for private subject matter. API access can consume credits and depends on the account's current limits.

Tavily's response supplies web snippets and links that can help explain terminology or provide current topic context. It is not a source of actual viewer retention, audience demand, channel analytics or guaranteed popularity. Retrieved text is treated as untrusted context, not executable instructions. Source URLs should remain visible with the resulting analysis. API keys belong in the local `.env` file or shell environment, never the frontend bundle. See [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search).

## Free hosted AI alternatives (not implemented)

| Service | Potential role | Practical limits |
|---|---|---|
| Groq Free plan | Whisper transcription or text ranking | Account/API key required; speech docs state a 25 MB free-tier audio upload limit and word/segment timestamp support. Quotas are account-specific. |
| Gemini Developer API Free tier | Transcript summaries and titles | Limited selected models and project/model quotas. Free-tier content may be used to improve Google's products; choose local processing for private content. |

Groq sources: [speech-to-text](https://console.groq.com/docs/speech-to-text), [rate limits](https://console.groq.com/docs/rate-limits), [data controls](https://console.groq.com/docs/your-data). Groq says inference content is not retained by default, with exceptions for reliability/abuse and optional retention controls. Gemini sources: [pricing and free-tier terms](https://ai.google.dev/gemini-api/docs/pricing), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

These are research alternatives, not implemented inference providers or silent fallbacks. Tavily is an optional search integration, not a replacement for Ollama or Whisper. You can still finish and download a video with every optional AI/search feature disabled.


