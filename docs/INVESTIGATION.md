# ScaleReach investigation and implementation plan

Investigated 18 November 2026. Scope: public marketing page, public login page, shipped homepage JavaScript. No account or private dashboard access was supplied. No private APIs, server code, model weights, or processing infrastructure were recovered.

## Findings and evidence

| Area | Finding | Evidence / confidence |
|---|---|---|
| Main workflow | Import video, select suggested moments, adjust captions/framing, export clips | Public homepage and login copy; advertised behavior, not a verified paid workflow |
| Features | Clip detection, transcript/caption editing, animated captions, aspect ratios, reframing, thumbnails, downloads | Public page declarations |
| Other features | Social scheduling, sharing links, MCP/API integration, translation, split-screen layouts | Public declarations; excluded from this personal export app |
| Design | Spacious light marketing page, nature hero image, large type, source input, demos and feature cards; two-column sign-in page | REA controlled browser observation |
| Homepage stack | Astro v5.17.1 generator metadata, Astro island markup, React runtime fingerprint | Saved HTML plus REA static analysis; React fingerprint medium confidence |
| Login frontend | Next.js asset paths and React server payload markers | Public login HTML; inference about frontend, not proof of backend framework |
| Backend / AI | Actual models, queues, database, cloud provider and rendering algorithms unknown | Public assets cannot establish these |

REA evidence: homepage replay `ev_5fd6064a1491d82ab0425da3fd3bb073cce0eac8c3d075d4d6c6ca07902fcb34`; bundle `ev_d295214b4a38b86afce4431654547b29af8296adc11aa83664ebb37dc0346bd9`; login summary `ev_b41777c8c01c2863e2f7e1f4c9713cc45980d47463312644cede8366844194a5`. Full checkpoint is in the accompanying research evidence file. Bundle analysis parsed 25 of 26 scripts; one exceeded a 15-second analysis deadline. The `astro-island` string was a low-confidence detector match, not an actual network endpoint. We do not infer authenticated routes from it.

Public sources: [ScaleReach](https://www.scalereach.ai/), [login](https://app.scalereach.ai/login). Ghidra/Hopper were not needed: this target exposes web pages and JavaScript, not a supplied native application.

## Simple plan adopted before implementation

1. Build an independent local studio with original UI and source. Upload files rather than connect social accounts.
2. Store projects in SQLite and preserve original media. Use a single background queue for heavier work.
3. Make manual trimming, captions and export usable without any model. Import/export SRT and import VTT.
4. Offer optional local speech recognition (faster-whisper) and local text-based moment suggestions. The initial <=9B choice was expanded on 19 November to the explicitly requested installed `qwen3.5:9b` artifact, which reports 9.7B.
5. Render final downloadable H.264/AAC MP4s through FFmpeg with real caption burn-in, crop/contain framing, 720/1080 output and thumbnails.
6. Test both API/media operations and the browser upload-to-download path; document limitations.

## Deliberate implementation choices

React + TypeScript + Vite for the editing interface; FastAPI for upload/jobs/media; SQLite for persistence; FFmpeg for deterministic video processing. Heavy jobs remain serialized to limit contention on the 6GB GPU. The updated transcription path supports requested GPU use when runtime libraries are available, with an eight-thread CPU budget for assistance/fallback; actual device and timings must be verified rather than inferred. This stack is our choice, not a claim about ScaleReach's private architecture. No copied logos, imagery, source code or private data are used.

This is a working simpler version, not full ScaleReach parity. It has manual horizontal framing rather than automatic speaker/face tracking; approximate karaoke timing rather than word alignment; no virality claims; no translation, split-screen stock footage, silence removal, URL ingestion or social publishing. The updated AI workflow summarizes all saved transcript text hierarchically, reviews source-aligned windows across the recording and ranks a distinct shortlist with a transparent editorial rubric. This replaces the earlier bounded-prefix analysis. Full transcript coverage does not eliminate summary loss or guarantee good clips. See README and AI-OPTIONS for configuration and limitations.

## 19 November refinement

The user requested complete-transcript understanding before clip selection, the existing Qwen3.5 9B-class model, optional topic search, GPU-accelerated transcription with eight CPU threads, and a white/light-brown editor with clearer cropping. These are independent product improvements; no additional private ScaleReach implementation was recovered.

The selection pipeline now reports whole-transcript coverage and a global summary, generates timestamp-valid candidates from subtitle boundaries, scores four 0–5 editorial criteria and compares candidates globally. It removes substantial overlap rather than padding the requested clip count. Tavily is optional and receives only a brief summary-derived topic query; source links and fallback warnings remain visible. These are not popularity predictions. See [clip selection](CLIP-SELECTION.md) and [AI execution/privacy](AI-OPTIONS.md) for the implementation details and primary-source rationale. Runtime benchmark results belong in [verification](VERIFICATION.md), not inferred from GPU specifications.
