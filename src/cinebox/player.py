"""Media player management: launch mpv or VLC with the resolved stream."""

from __future__ import annotations

import shutil
import subprocess

from .models import StreamInfo
from .utils import Log, ensure_command


def _player_path(player: str) -> str:
    hint = f"Install it via your package manager (e.g. sudo apt install {player})"
    return ensure_command(player, hint)


def build_mpv_cmd(
    stream: StreamInfo,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
    subtitle_file: str | None = None,
) -> list[str]:
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
    cmd.append(stream.url)
    return cmd


def build_vlc_cmd(
    stream: StreamInfo,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
    subtitle_file: str | None = None,
) -> list[str]:
    cmd = ["vlc"]
    if fullscreen:
        cmd.append("--fullscreen")
    cmd.append("--network-caching=3000")
    if stream.referer:
        cmd.append(f"--http-referrer={stream.referer}")
    if subtitle_file:
        cmd.append(f"--sub-file={subtitle_file}")
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(stream.url)
    return cmd


def play(
    stream: StreamInfo,
    player: str = "mpv",
    subtitle_file: str | None = None,
    fullscreen: bool = True,
    extra_args: list[str] | None = None,
) -> int:
    """Launch the selected player in its own window and block until it exits.

    The player's stdio is fully detached so it never interferes with the TUI
    running in the parent terminal (mpv opens a window via --force-window).
    """
    player_path = _player_path(player)
    if player == "vlc":
        cmd = build_vlc_cmd(
            stream, fullscreen=fullscreen, extra_args=extra_args,
            subtitle_file=subtitle_file,
        )
    else:
        cmd = build_mpv_cmd(
            stream, fullscreen=fullscreen, extra_args=extra_args,
            subtitle_file=subtitle_file,
        )

    Log.debug(f"Exec {cmd}")
    proc = subprocess.run(
        [player_path, *cmd[1:]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode


def player_exists(player: str) -> bool:
    return shutil.which(player) is not None
