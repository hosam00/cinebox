"""Download HLS streams to local files via yt-dlp."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .config import get
from .models import StreamInfo
from .utils import Log, ensure_command, sanitize_filename


def _which_ytdlp() -> str:
    return ensure_command("yt-dlp", "pip install yt-dlp")


def download_stream(
    stream: StreamInfo,
    output_dir: str,
    quality: str = "1080p",
    filename: str | None = None,
    format_selector: str | None = None,
) -> Path:
    """Download a stream to output_dir. Returns the resulting file path."""
    ytdlp = _which_ytdlp()
    output_dir_path = Path(os.path.expanduser(output_dir))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    base = filename or sanitize_filename(stream.title or "download")
    outtmpl = str(output_dir_path / f"{base}.%(ext)s")

    if format_selector is None:
        fmt = _format_selector(quality)
    else:
        fmt = format_selector
    cmd = [
        ytdlp,
        "--format",
        fmt,
        "--no-continue",
        "--no-playlist",
        "--restrict-filenames",
        "--output",
        outtmpl,
    ]
    # Referer header
    if stream.referer:
        cmd += ["--referer", stream.referer]
    headers = stream.get_headers()
    if headers:
        for key, value in headers.items():
            cmd += ["--add-header", f"{key}: {value}"]
    try:
        fragments = int(get("download", "parallel_fragments", 3))
    except (TypeError, ValueError):
        fragments = 3
    fragments = max(1, min(16, fragments))
    if fragments > 1:
        cmd += ["--concurrent-fragments", str(fragments)]
    cmd.append(stream.url)

    Log.debug(f"Exec {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp exited with code {proc.returncode}.")

    # Find the resulting file (yt-dlp may remux to mkv/mp4/webm).
    candidates = sorted(output_dir_path.glob(f"{base}.*"))
    if not candidates:
        raise RuntimeError(f"Download finished but no file found in {output_dir_path}.")
    return candidates[0]


def _format_selector(quality: str) -> str:
    q = quality.strip().lower()
    if q == "best":
        return "bestvideo+bestaudio/best"
    if q == "480p":
        return "bestvideo[height<=480]+bestaudio/best[height<=480]"
    if q == "720p":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    if q == "1080p":
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    raise ValueError(f"Unknown quality {quality!r}. Use 480p, 720p, 1080p or best.")


def episode_filename(title: str, season: int, episode: int) -> str:
    """Build a TV episode filename: 'Breaking Bad - S01E01'."""
    base = sanitize_filename(title)
    return f"{base} - S{season:02d}E{episode:02d}"


def resolution_height(label: str) -> int:
    """Extract the pixel height from a quality label ('1920x800 (4.5 Mbps)')."""
    match = re.search(r"\d{3,4}x(\d+)", label)
    if match:
        return int(match.group(1))
    if "4k" in label.lower():
        return 2160
    return 1080


def format_selector_for_height(height: int) -> str:
    """Map a resolved pixel height to a yt-dlp format selector.

    Picks the smallest standard bucket (480/720/1080/2160) that is
    greater than or equal to the requested height.
    """
    if height <= 480:
        return "bestvideo[height<=480]+bestaudio/best[height<=480]"
    if height <= 720:
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    if height <= 1080:
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    return "bestvideo[height<=2160]+bestaudio/best[height<=2160]"
