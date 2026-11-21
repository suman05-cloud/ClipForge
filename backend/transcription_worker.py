"""One disposable process per transcription, releasing all GPU memory on exit."""
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from .transcription import cuda_directories


def extract_audio_wav(source_path: str | Path) -> str:
    """Pre-extract audio to a 16kHz mono WAV file using FFmpeg.

    This avoids PyAV demuxer container bugs (e.g. IndexError in StreamContainer.get),
    removes container overhead, and ensures seamless Whisper ingestion.
    """
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    temp_wav = Path(tempfile.gettempdir()) / f"whisper_audio_{os.getpid()}_{src.stem[:24]}.wav"
    ffmpeg_bin = os.getenv("CLIPFORGE_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vn", "-sn", "-dn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(temp_wav)
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    if res.returncode != 0 or not temp_wav.is_file() or temp_wav.stat().st_size < 100:
        if temp_wav.is_file():
            try:
                temp_wav.unlink()
            except OSError:
                pass
        err_msg = res.stderr.strip()
        err_lower = err_msg.lower()
        if "does not contain any stream" in err_lower or "matches no streams" in err_lower or "output file is empty" in err_lower:
            raise ValueError("This video contains no audio track to transcribe.")
        # If extraction failed for another reason, fallback to original source
        return str(source_path)
    return str(temp_wav)


def deduplicate_sentences(text: str) -> str:
    """Eliminate consecutive repeated sentences or loop hallucinations."""
    parts = re.split(r'([.?!]\s+)', text.strip())
    cleaned = []
    prev = ""
    for p in parts:
        norm = re.sub(r'[^a-zA-Z0-9]', '', p).lower()
        if norm and norm == prev:
            continue
        if norm:
            prev = norm
        cleaned.append(p)
    return "".join(cleaned).strip() or text.strip()


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def preload_cuda_dlls(paths):
    handles = []
    for path in paths:
        if os.name == "nt":
            try:
                handles.append(os.add_dll_directory(str(path)))
            except OSError:
                pass
    # Specific ordered pre-loading prevents Windows dynamic linker resolution crashes:
    # 1. cublasLt -> 2. cublas -> 3. cudnn_ops -> 4. cudnn
    ordered_dlls = ["cublasLt64_12.dll", "cublas64_12.dll", "cudnn_ops64_9.dll", "cudnn64_9.dll"]
    for dll_name in ordered_dlls:
        for path in paths:
            target = Path(path) / dll_name
            try:
                if target.is_file():
                    ctypes.CDLL(str(target))
                    break
            except OSError:
                pass
    return handles


def main():
    config = json.load(sys.stdin)
    device = config.get("device", "cpu")
    cpu_threads = int(config.get("cpu_threads", 8))
    duration = float(config.get("duration", 0))

    handles = []
    if device == "cuda":
        paths = cuda_directories()
        os.environ["PATH"] = os.pathsep.join(map(str, paths)) + os.pathsep + os.environ.get("PATH", "")
        handles = preload_cuda_dlls(paths)

    from faster_whisper import WhisperModel, BatchedInferencePipeline

    compute_type = "float16" if device == "cuda" else "int8"
    num_workers = 1 if device == "cuda" else min(cpu_threads, 4)

    emit({
        "type": "progress",
        "progress": 6,
        "message": f"Loading Whisper ({config['model']}) on {device.upper()} · {cpu_threads} CPU threads"
    })

    model = WhisperModel(
        config["model_path"],
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        num_workers=num_workers,
        download_root=config["download_root"],
        local_files_only=not config["allow_download"]
    )

    emit({
        "type": "progress",
        "progress": 12,
        "message": f"Decoding audio & detecting speech via VAD · {device.upper()}"
    })

    options = dict(
        language=config.get("language"),
        beam_size=1,
        vad_filter=True,
        word_timestamps=False,
        condition_on_previous_text=False,
        repetition_penalty=1.2,
        no_repeat_ngram_size=3
    )
    engine = model
    if device == "cuda":
        engine = BatchedInferencePipeline(model=model)
        options["batch_size"] = 16

    audio_path = config["source"]
    temp_wav_created = None
    try:
        audio_path = extract_audio_wav(config["source"])
        if audio_path != config["source"]:
            temp_wav_created = audio_path

        segments, info = engine.transcribe(audio_path, **options)
        result = []
        video_dur = duration or getattr(info, "duration", 0) or 1.0

        for segment in segments:
            start = max(0.0, segment.start)
            end = min(video_dur, segment.end)
            cleaned_text = deduplicate_sentences(segment.text)
            if cleaned_text and end > start:
                result.append({"start": round(start, 3), "end": round(end, 3), "text": cleaned_text})
            pct = min(96, 12 + int(end / video_dur * 84))
            emit({
                "type": "progress",
                "progress": pct,
                "message": f"Transcribing ({pct}%) on {device.upper()} · {end:.1f}s / {video_dur:.1f}s ({len(result)} captions)"
            })

        emit({
            "type": "progress",
            "progress": 100,
            "message": f"Finalizing {len(result)} captions · {device.upper()}"
        })
        emit({
            "type": "result",
            "segments": result,
            "language": info.language,
            "provider": "faster-whisper",
            "model": config["model"]
        })
    finally:
        if temp_wav_created and os.path.exists(temp_wav_created):
            try:
                os.remove(temp_wav_created)
            except OSError:
                pass


if __name__ == "__main__":
    main()
