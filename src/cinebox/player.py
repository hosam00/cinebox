"""Media player management: launch mpv or VLC with the resolved stream."""

from __future__ import annotations

import shutil
import subprocess

from .models import StreamInfo
from .utils import Log, ensure_command, validate_stream_url


def _player_path(player: str) -> str:
    hint = f"Install it via your package manager (e.g. sudo apt install {player})"
    return ensure_command(player, hint)


def build_mpv_cmd(
    stream: StreamInfo,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
    subtitle_file: str | None = None,
) -> list[str]:
    url = validate_stream_url(stream.url)
    cmd = ["mpv"]
    cmd.append("--force-window=yes")
    if fullscreen:
        cmd.append("--fs")
    if stream.title:
        cmd.append(f"--force-media-title={stream.title}")
    headers = stream.get_headers()
    if headers:
        fields = ",".join(f"{k}: {v}" for k, v in headers.items())
        cmd.append(f"--http-header-fields={fields}")
    if subtitle_file:
        cmd.append(f"--sub-file={subtitle_file}")
    if extra_args:
        cmd.extend(extra_args)
    cmd += ["--", url]
    return cmd


def build_vlc_cmd(
    stream: StreamInfo,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
    subtitle_file: str | None = None,
) -> list[str]:
    url = validate_stream_url(stream.url)
    headers = stream.get_headers()
    referer = _header(headers, "Referer")
    user_agent = _header(headers, "User-Agent")
    cmd = ["vlc"]
    if fullscreen:
        cmd.append("--fullscreen")
    cmd.append("--network-caching=3000")
    if referer:
        cmd.append(f"--http-referrer={referer}")
    if user_agent:
        cmd.append(f"--http-user-agent={user_agent}")
    # VLC 3 has no --http-origin option and exits immediately on it.
    # Referer and User-Agent are the supported request-header options.
    if subtitle_file:
        cmd.append(f"--sub-file={subtitle_file}")
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    return cmd


def _header(headers: dict[str, str], name: str) -> str:
    """Return a header case-insensitively, or an empty string."""
    wanted = name.lower()
    return next(
        (value for key, value in headers.items() if key.lower() == wanted),
        "",
    )


def play(
    stream: StreamInfo,
    player: str = "mpv",
    subtitle_file: str | None = None,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
) -> int:
    """Launch the selected player in its own window and block until it exits.

    Stdout is detached so it never interferes with the TUI. Stderr is captured
    so VLC's exit-code-0 input failures can be reported instead of silently
    falling through to the post-watch menu.
    """
    player_path = _player_path(player)
    if player == "vlc":
        cmd = build_vlc_cmd(
            stream,
            fullscreen=fullscreen,
            extra_args=extra_args,
            subtitle_file=subtitle_file,
        )
    else:
        cmd = build_mpv_cmd(
            stream,
            fullscreen=fullscreen,
            extra_args=extra_args,
            subtitle_file=subtitle_file,
        )

    Log.debug(f"Exec {player_path}.")
    proc = subprocess.run(
        [player_path, *cmd[1:]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if player == "vlc" and "input can't be opened" in (proc.stderr or ""):
        raise RuntimeError("VLC could not open the stream.")
    return proc.returncode


def player_exists(player: str) -> bool:
    return shutil.which(player) is not None
