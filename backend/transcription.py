"""Isolated Whisper execution: CUDA failures cannot terminate the web server."""
import functools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except (OSError, PermissionError):
        return False


def safe_has_file(path: Path, filename: str) -> bool:
    try:
        return (path / filename).is_file()
    except (OSError, PermissionError):
        return False


def cuda_directories():
    """Return only legitimate CUDA and cuDNN runtime library directories."""
    candidates = [Path(p) for p in os.getenv("WHISPER_CUDA_PATH", "").split(os.pathsep) if p]
    local = os.getenv("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v12")
        candidates.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v13")
        candidates.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama")
    candidates.extend(Path(sys.prefix).glob("Lib/site-packages/nvidia/*/bin"))
    candidates.extend(Path(sys.prefix).glob("lib/python*/site-packages/nvidia/*/lib"))
    for p in os.getenv("PATH", "").split(os.pathsep):
        if not p:
            continue
        path_obj = Path(p)
        if safe_is_dir(path_obj):
            if safe_has_file(path_obj, "cublas64_12.dll") or safe_has_file(path_obj, "cudnn64_9.dll"):
                candidates.append(path_obj)
    res = []
    for p in candidates:
        if safe_is_dir(p):
            res.append(p)
    return list(dict.fromkeys(res))


@functools.lru_cache(maxsize=1)
def capabilities():
    ready = False
    gpu_name = ""
    try:
        probe = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if probe.returncode == 0 and probe.stdout.strip():
            gpu_name = probe.stdout.strip().splitlines()[0]
            ready = True
        if os.name == "nt":
            paths = cuda_directories()
            has_cublas = any(
                safe_has_file(p, "cublas64_12.dll") or safe_has_file(p, "cublasLt64_12.dll")
                for p in paths
            )
            has_cudnn = any(
                safe_has_file(p, "cudnn64_9.dll") or safe_has_file(p, "cudnn_ops64_9.dll")
                for p in paths
            )
            ready = ready and has_cublas and has_cudnn
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "transcription_gpu_available": ready,
        "transcription_device": "cuda" if ready else "cpu",
        "transcription_cpu_threads": 8,
        "gpu_name": gpu_name or ("NVIDIA GPU" if ready else None),
    }


def run(config, update):
    requested = config.get("device", "auto")
    caps = capabilities()
    ready = caps["transcription_gpu_available"]
    gpu_name = caps.get("gpu_name") or "NVIDIA GPU"
    threads = config.get("cpu_threads", 8)

    if requested == "cuda" and not ready:
        raise ValueError(
            "NVIDIA CUDA/cuDNN runtime is unavailable. Choose Auto/CPU or install the GPU runtime using setup-gpu.ps1, then restart ClipForge."
        )
    device = "cuda" if requested != "cpu" and ready else "cpu"
    device_label = f"{gpu_name} (CUDA)" if device == "cuda" else f"CPU ({threads} threads)"
    warnings = []

    for attempt in range(2):
        current_config = {**config, "device": device, "cpu_threads": threads}
        update(3, f"Initializing Whisper on {device_label} · {threads} CPU threads")
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
            process = subprocess.Popen(
                [sys.executable, "-m", "backend.transcription_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            result = None
            try:
                process.stdin.write(json.dumps(current_config))
                process.stdin.close()
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "progress":
                        update(event["progress"], event["message"])
                    elif event.get("type") == "result":
                        result = event
                process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            if process.returncode == 0 and result is not None:
                result.pop("type", None)
                return {
                    **result,
                    "device": device,
                    "gpu_name": gpu_name if device == "cuda" else None,
                    "cpu_threads": threads,
                    "warnings": warnings,
                }
            errors.seek(0)
            error = errors.read()[-1600:]
        if device == "cuda" and requested == "auto" and attempt == 0:
            warnings.append("GPU transcription failed; completed using CPU fallback with 8 threads.")
            update(5, "GPU could not transcribe this video; falling back to 8 CPU threads")
            device = "cpu"
            device_label = f"CPU ({threads} threads)"
            continue
        raise ValueError("Whisper transcription failed. " + error)
