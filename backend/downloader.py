"""Link downloader and subtitle extractor using yt-dlp.

Pulls metadata, subtitles and lightweight preview proxies without downloading
the full high-definition video. Full resolution is only fetched for the specific
time range during clip export.
"""
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import yt_dlp

from . import media


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
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser, None, None, None)
    return opts


def extract_info(url: str, cookies_browser: str | None = None) -> dict:
    """Extract video metadata and available subtitle tracks without downloading media.
    Supports YouTube, Instagram Reels, and Facebook video links with automatic cookie fallback.
    """
    candidates = [cookies_browser] if cookies_browser else [None, "chrome", "edge"]
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
            continue
    raise ValueError(f"Could not read video from this link: {last_exc or 'Unknown error'}")


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


def download_preview_proxy(url: str, output_path: Path, cookies_browser: str | None = None, update: Callable[[int, str], None] | None = None):
    """Download crisp 720p/480p preview proxy so editing and scrubbing look great without downloading 4K masters."""
    if update:
        update(15, "Fetching high-quality 720p preview video")

    opts = {
        **_ydl_base_opts(cookies_browser),
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=480]/best",
        "outtmpl": str(output_path),
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def download_clip_section(url: str, start: float, end: float, output_path: Path, max_height: int = 1080, cookies_browser: str | None = None, update: Callable[[int, str], None] | None = None):
    """Fetch ONLY the exact 30-60 second time range at full high definition (up to 1080p)."""
    if update:
        update(20, f"Fetching {end - start:.1f}s full-quality slice ({start:.1f}s to {end:.1f}s)")

    opts = {
        **_ydl_base_opts(cookies_browser),
        "format": f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": True,
        "outtmpl": str(output_path),
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
