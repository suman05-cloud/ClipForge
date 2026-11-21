"""One disposable process per transcription, releasing all GPU memory on exit."""
import ctypes
import json
import os
import sys
from pathlib import Path
from .transcription import cuda_directories


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
        word_timestamps=False
    )
    engine = model
    if device == "cuda":
        engine = BatchedInferencePipeline(model=model)
        options["batch_size"] = 16

    segments, info = engine.transcribe(config["source"], **options)
    result = []
    video_dur = duration or getattr(info, "duration", 0) or 1.0

    for segment in segments:
        start = max(0.0, segment.start)
        end = min(video_dur, segment.end)
        if segment.text.strip() and end > start:
            result.append({"start": round(start, 3), "end": round(end, 3), "text": segment.text.strip()})
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


if __name__ == "__main__":
    main()
