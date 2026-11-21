# Verification — 18 November 2026

Completed on Windows x64, Python 3.12, Node 24, local FFmpeg 8.1.1 and Chrome.

| Check | Result |
|---|---|
| TypeScript compile and Vite production build | Passed |
| Backend pytest suite | 8 passed; actual FFmpeg renders, not mocked output |
| Browser end-to-end workflow | Upload, clip creation, trim, framing, save, SRT import/edit, export and MP4 download passed |
| Responsive layout | 390px viewport checked; no horizontal overflow |
| Browser JavaScript errors | None during tested workflow |
| Output inspection | H.264/AAC MP4, 720x1280, exactly 5.0 seconds; burned-in edited caption visually verified |
| Other output sizes | 720 square, 1280x720 landscape and 1080x1920 silent-source output passed |
| Real transcription | Cached faster-whisper base.en CPU/int8: 7 segments from locally synthesized speech; no weight download |
| Real AI suggestions | Installed qwen2.5:7b: 2 validated clip suggestions from the transcript |
| Dependency consistency | uv pip check passed after pinning PyAV 16.1.0 compatibility |
| Launcher scripts | PowerShell parse checks passed; localhost startup checked |

Backend tests also cover video byte-range playback, malformed inputs, escaping ASS text, caption overlaps, bad subtitles, no-audio transcription refusal, transcript downloads, project/clip deletion, safe export lookup, foreign-origin rejection and interrupted-job recovery. Model cache discovery has a no-network test.

The browser test is in `scripts/test-browser.cjs` and uses playwright-core with installed Chrome. Set `PLAYWRIGHT_MODULE` to an existing module directory or install playwright-core as a development dependency. `scripts/test-ai.py` expects a running test server and `test-output/speech.mp4`; it deliberately never downloads weights. It is a smoke-test utility, not part of app startup.

For reproducible backend tests on hosts with a restricted system temp directory, create `test-output` and pass `--basetemp` with a new directory beneath it. Do not point pytest's temporary directory at user data.

Known limits: no production multi-user/security/load testing, arbitrary-codec matrix, accuracy benchmark, or paid ScaleReach dashboard parity test. Automated transcription quality and LLM selections require review. Source footage and models are excluded from the source archive. Optional future hosted APIs are researched, not integrated or tested.

Evidence summaries: `docs/evidence/browser-results.json`, `docs/evidence/ai-results.json`, and `docs/evidence/scalereach-rea-evidence.json`.

## Ollama response fix — 19 November 2026

The suggestion request now sends an explicit JSON schema, uses typed validation and retries one malformed or unusable response. Overlong model selections are shortened only at actual transcript end boundaries within the requested duration range, with an explicit review note. Out-of-range and too-short selections are rejected. Regression coverage: 14 tests passed, including malformed/truncated JSON, invalid response shapes, invalid timestamps, and boundary-based shortening. Existing transcripts and projects are not rewritten by this fix.
Real local Qwen2.5 7B verification on the user-selected saved transcript passed: 4 valid clips (59.54, 33.29, 58, 21 seconds), 38.2 seconds elapsed. Read-only test; no clips added. Examined 601 of 742 segments within the existing character budget.
