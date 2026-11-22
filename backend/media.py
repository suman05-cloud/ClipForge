"""Media operations. Every command uses an argv array, never a command shell."""
import functools
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path


@functools.lru_cache(maxsize=1)
def nvenc_available() -> bool:
    """Check if NVIDIA NVENC H.264 hardware encoder is supported and functional."""
    try:
        probe = subprocess.run(
            [binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        return probe.returncode == 0
    except Exception:
        return False


def binary(name):
    override = os.getenv(f"CLIPFORGE_{name.upper()}")
    path = override or shutil.which(name)
    if not path:
        raise ValueError(f"{name} is missing. Install FFmpeg and put its bin directory on PATH.")
    return str(path)


def run(args, timeout=60, cwd=None):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
    if result.returncode:
        raise ValueError(f"Media processing failed: {result.stderr[-1600:]}")
    return result.stdout


def probe(path):
    data = json.loads(run([binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    videos = [s for s in data.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("This file has no playable video stream.")
    video = videos[0]
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0 or duration > 4 * 3600:
        raise ValueError("Video must have a known duration between 0 and 4 hours.")
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    if min(width, height) <= 0:
        raise ValueError("Cannot read video dimensions.")
    rotation = next((s.get("rotation", 0) for s in video.get("side_data_list", []) if "rotation" in s), 0)
    if abs(float(rotation)) % 180 == 90:
        width, height = height, width
    return {"duration": duration, "width": width, "height": height, "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}


def thumbnail(source, output, at=0):
    run([binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(source), "-frames:v", "1", "-vf", "scale=480:-2", "-update", "1", str(output)])


def timestamp(seconds, ass=False):
    scale = 100 if ass else 1000
    total = max(0, round(seconds * scale))
    hours, rem = divmod(total, 3600 * scale)
    minutes, rem = divmod(rem, 60 * scale)
    sec, frac = divmod(rem, scale)
    return f"{hours}:{minutes:02}:{sec:02}.{frac:02}" if ass else f"{hours:02}:{minutes:02}:{sec:02},{frac:03}"


def srt(segments):
    return "\n\n".join(f"{i+1}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}" for i, s in enumerate(segments)) + "\n"


def parse_subtitles(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    pattern = r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})"
    timing = re.compile(pattern + r"\s*-->\s*" + pattern + r"[^\n]*\n([^\n]*(?:\n(?!\n)[^\n]*)*)")
    result = []
    for m in timing.finditer(text):
        values = m.groups()
        def secs(v):
            return int(v[0] or 0)*3600 + int(v[1])*60 + int(v[2]) + int(v[3])/1000
        body = re.sub(r"<[^>]*>", "", values[8]).strip()
        if body:
            result.append({"start": secs(values[:4]), "end": secs(values[4:8]), "text": body})
    if not result:
        raise ValueError("No timed captions found. Import a UTF-8 SRT or WebVTT file.")
    return result


def ass_color(hex_color):
    value = hex_color.lstrip("#")
    return f"&H00{value[4:6]}{value[2:4]}{value[0:2]}"


def escape_ass(text):
    # User text never becomes ASS drawing/style tags.
    return text.replace("\\", "＼").replace("{", "(").replace("}", ")").replace("\n", r"\N").replace("\r", "")


def ass_document(segments, clip, width, height):
    style = clip["caption_style"]
    size = round(clip["font_size"] * width / 720)
    outline = 3 if style in ("bold", "karaoke") else 2
    margin = round(height * 0.09)
    primary = ass_color(clip["caption_color"])
    accent = ass_color(clip["accent_color"])
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,{size},{accent if style == 'karaoke' else primary},{primary},&H00101010,&H80000000,{int(style != 'clean')},0,0,0,100,100,0,0,1,{outline},1,2,{round(width*.06)},{round(width*.06)},{margin},1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    rows = []
    for segment in segments:
        start = max(clip["start"], segment["start"])
        end = min(clip["end"], segment["end"])
        if end <= start:
            continue
        # Short phrase blocks fit phone screens. Equal word time is explicitly approximate.
        words = segment["text"].split()
        chunks = [words[i:i+7] for i in range(0, len(words), 7)]
        offset = 0
        for chunk in chunks:
            a = start + (end-start) * offset/max(1,len(words))
            offset += len(chunk)
            b = start + (end-start) * offset/max(1,len(words))
            text = escape_ass(" ".join(chunk))
            if style == "karaoke":
                duration = max(1, round((b-a)*100/len(chunk)))
                text = " ".join(f"{{\\kf{duration}}}{escape_ass(word)}" for word in chunk)
            rows.append(f"Dialogue: 0,{timestamp(a-clip['start'],True)},{timestamp(b-clip['start'],True)},Default,,0,0,0,,{text}")
    return head + "\n".join(rows) + "\n"


def dimensions(aspect, resolution):
    return {
        "9:16": (resolution, round(resolution * 16 / 9 / 2) * 2),
        "1:1": (resolution, resolution),
        "16:9": (round(resolution * 16 / 9 / 2) * 2, resolution),
        "4:5": (resolution, round(resolution * 5 / 4 / 2) * 2),
    }[aspect]


def render(source, output, clip, segments, resolution, update):
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    width, height = dimensions(clip["aspect"], resolution)
    if clip["fit"] == "crop":
        zoom = clip.get("zoom", 1)
        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            f"scale=trunc(iw*{zoom}/2)*2:trunc(ih*{zoom}/2)*2",
            f"crop={width}:{height}:(iw-ow)*{clip['crop_x']}:(ih-oh)*{clip.get('crop_y', 0.5)}"
        ]
    else:
        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101014"
        ]
    filters.append("setsar=1")
    subtitle = output_path.with_suffix(".ass")
    if clip["burn_captions"] and clip["caption_style"] != "none" and segments:
        subtitle.write_text(ass_document(segments, clip, width, height), encoding="utf-8")
        # Simple generated basename, working directory avoids Windows drive/filter escaping.
        filters.append(f"ass=filename={subtitle.name}")

    use_gpu = nvenc_available()
    attempts = [True, False] if use_gpu else [False]
    last_error = ""

    try:
        for is_gpu in attempts:
            if is_gpu:
                v_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p"]
            else:
                cpu_threads = str(min(os.cpu_count() or 4, 16))
                v_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-threads", cpu_threads]

            command = [
                binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(clip["start"]),
                "-i", str(source_path),
                "-t", str(clip["end"] - clip["start"]),
                "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", ",".join(filters),
                *v_args,
                "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart",
                "-progress", "pipe:1", "-nostats",
                str(output_path)
            ]
            log = output_path.with_suffix(".log")
            try:
                with log.open("w", encoding="utf-8") as errors:
                    process = subprocess.Popen(
                        command,
                        cwd=output_path.parent,
                        stdout=subprocess.PIPE,
                        stderr=errors,
                        text=True,
                        encoding="utf-8",
                        errors="replace"
                    )
                    try:
                        clip_dur = max(0.1, clip["end"] - clip["start"])
                        label = "Rendering MP4 (GPU NVENC)" if is_gpu else "Rendering MP4 (CPU)"
                        for line in process.stdout:
                            if line.startswith("out_time_us="):
                                try:
                                    elapsed = float(line.strip().split("=", 1)[1]) / 1_000_000
                                    update(min(95, 10 + int(85 * elapsed / clip_dur)), label)
                                except ValueError:
                                    pass
                        process.wait(timeout=60)
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                    if process.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 1024:
                        return
                    last_error = log.read_text(encoding="utf-8")[-1400:] if log.is_file() else "Unknown FFmpeg error"
                    output_path.unlink(missing_ok=True)
            finally:
                log.unlink(missing_ok=True)

        raise ValueError("FFmpeg export failed: " + last_error)
    finally:
        subtitle.unlink(missing_ok=True)
