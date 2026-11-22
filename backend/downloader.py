"""Link downloader and subtitle extractor using yt-dlp.

Pulls metadata, subtitles and lightweight preview proxies without downloading
the full high-definition video. Full resolution is only fetched for the specific
time range during clip export.
"""
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import yt_dlp

from . import media


def _find_cookie_file() -> Path | None:
    for candidate in (Path("clipforge/cookies.txt"), Path("cookies.txt"), Path("clipforge/data/cookies.txt"), Path("data/cookies.txt")):
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate.resolve()
        except OSError:
            pass
    return None


def _ydl_base_opts(cookies_browser: str | None = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    # Use system or bundled Node.js for YouTube JavaScript signature extraction
    node_path = shutil.which("node") or os.getenv("NODE_PATH")
    if node_path:
        opts["js_runtimes"] = {"node": {"path": node_path}}
    else:
        opts["js_runtimes"] = {"node": {}}
    cookie_file = _find_cookie_file()
    if cookie_file:
        opts["cookiefile"] = str(cookie_file)
    elif cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser, None, None, None)
    return opts


def extract_info(url: str, cookies_browser: str | None = None) -> dict:
    """Extract video metadata and available subtitle tracks without downloading media.
    Supports YouTube, Instagram Reels, and Facebook video links.
    """
    candidates = [cookies_browser] if cookies_browser else [None]
    last_exc = None
    for browser in candidates:
        try:
            opts = {
                **_ydl_base_opts(browser),
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue
                duration = float(info.get("duration") or 0)
                # Fallback for Instagram reels / Facebook videos that don't report duration in initial payload
                if duration <= 0:
                    duration = 60.0
                if duration > 12 * 3600:
                    raise ValueError("Videos longer than 12 hours are not supported.")
                info["_resolved_browser"] = browser
                return info
        except Exception as exc:
            last_exc = exc
            err_msg = str(exc)
            if "Could not copy Chrome cookie database" in err_msg or "Permission denied" in err_msg:
                raise ValueError("Cannot read browser cookies while Chrome/Edge is currently open. Please close your browser window so Windows unlocks the database, or use a cookies.txt file.")
            if "Sign in to confirm you’re not a bot" in err_msg:
                raise ValueError("YouTube bot check triggered for this video. To import it, either place a cookies.txt file in the ClipForge folder or select Chrome/Edge cookies in the dropdown.")
            continue
    err_str = str(last_exc) if last_exc else "Unknown error"
    if "Sign in to confirm you’re not a bot" in err_str:
        raise ValueError("YouTube bot check triggered for this video. To import it, either place a cookies.txt file in the ClipForge folder, or select Chrome/Edge cookies in the dropdown.")
    raise ValueError(f"Could not read video from this link: {err_str}")


def extract_subtitles(info: dict) -> list[dict]:
    """Fetch existing YouTube subtitles or auto-captions and parse them into segments."""
    all_subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    candidates = []
    # Prefer English manual or automatic subtitles
    for lang in ("en", "en-US", "en-GB", "en-CA", "en-AU"):
        if lang in all_subs:
            candidates.extend(all_subs[lang])
        if lang in auto_subs:
            candidates.extend(auto_subs[lang])
    # Fallback to any language available
    if not candidates:
        for lang, tracks in {**all_subs, **auto_subs}.items():
            candidates.extend(tracks)
            if candidates:
                break
    if not candidates:
        return []

    # Prefer VTT format for clean timestamped parsing
    vtt_url = next((s["url"] for s in candidates if s.get("ext") == "vtt"), None) or candidates[0].get("url")
    if not vtt_url:
        return []

    req = urllib.request.Request(vtt_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8", errors="replace")
    return media.parse_subtitles(content)


def download_thumbnail(thumbnail_url: str, output_path: Path):
    """Download thumbnail image directly."""
    if not thumbnail_url:
        return
    req = urllib.request.Request(thumbnail_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        output_path.write_bytes(resp.read())


def _ensure_mp4_output(output_path: Path) -> Path:
    """Ensure output_path is a playable MP4 file, remuxing if yt-dlp saved as webm/mkv or with appended ext."""
    if output_path.is_file() and output_path.stat().st_size > 1024:
        return output_path

    parent = output_path.parent
    base_name = output_path.stem
    # Find any downloaded candidate matching base_name
    candidates = [
        f for f in parent.glob(f"{base_name}*")
        if f.is_file() and f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".json", ".sqlite3")
        and f != output_path and f.stat().st_size > 1024
    ]

    if not candidates:
        return output_path

    chosen = max(candidates, key=lambda p: p.stat().st_size)
    ffmpeg_bin = os.getenv("CLIPFORGE_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
    try:
        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(chosen),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(output_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if res.returncode != 0 or not output_path.is_file() or output_path.stat().st_size < 1024:
            # Fallback to hardware or multithreaded re-encoding video if codec copy in MP4 container is unsupported
            v_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"] if media.nvenc_available() else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "0"]
            cmd_fallback = [
                ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(chosen),
                *v_args,
                "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart",
                str(output_path)
            ]
            subprocess.run(cmd_fallback, capture_output=True, text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        if output_path.is_file() and output_path.stat().st_size > 1024:
            try:
                chosen.unlink()
            except OSError:
                pass
    except Exception:
        if not output_path.is_file() and chosen.is_file():
            try:
                chosen.rename(output_path)
            except OSError:
                pass

    return output_path


def download_preview_proxy(url: str, output_path: Path, cookies_browser: str | None = None, update: Callable[[int, str], None] | None = None):
    """Download crisp 720p/480p preview proxy so editing and scrubbing look great without downloading 4K masters."""
    if update:
        update(15, "Fetching high-quality 720p preview video")

    target_base = str(output_path.with_suffix(""))
    opts = {
        **_ydl_base_opts(cookies_browser),
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=480]/best",
        "merge_output_format": "mp4",
        "outtmpl": f"{target_base}.%(ext)s",
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    _ensure_mp4_output(output_path)


def download_clip_section(url: str, start: float, end: float, output_path: Path, max_height: int = 1080, cookies_browser: str | None = None, update: Callable[[int, str], None] | None = None):
    """Fetch ONLY the exact 30-60 second time range at full high definition (up to 1080p)."""
    if update:
        update(20, f"Fetching {end - start:.1f}s full-quality slice ({start:.1f}s to {end:.1f}s)")

    target_base = str(output_path.with_suffix(""))
    opts = {
        **_ydl_base_opts(cookies_browser),
        "format": f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": True,
        "merge_output_format": "mp4",
        "outtmpl": f"{target_base}.%(ext)s",
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    _ensure_mp4_output(output_path)
