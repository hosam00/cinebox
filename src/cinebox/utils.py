"""Shared helpers: http client, logging, retries, shell detection."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

from .config import DEFAULT_HEADERS

T = TypeVar("T")


class CineError(Exception):
    """Base exception for cinebox."""


class SearchError(CineError):
    pass


class NoResultsError(CineError):
    pass


class ProviderError(CineError):
    pass


class PlayerNotFoundError(CineError):
    pass


class Log:
    """Tiny leveled logger respecting --verbose."""

    verbose = False

    @staticmethod
    def info(msg: str) -> None:
        print(f"[INFO] {msg}")

    @staticmethod
    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")

    @staticmethod
    def error(msg: str) -> None:
        print(f"[ERROR] {msg}")

    @staticmethod
    def debug(msg: str) -> None:
        if Log.verbose:
            print(f"[DEBUG] {msg}")


def new_http_client(
    timeout: float = 15.0,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Client:
    """Build an httpx client with sane defaults."""
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    return httpx.Client(
        timeout=timeout,
        headers=merged,
        follow_redirects=follow_redirects,
    )


def retry(
    func: Callable[[], T],
    retries: int = 2,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> T:
    """Retry a zero-arg callable with exponential backoff."""
    attempt = 0
    current_delay = delay
    while True:
        try:
            return func()
        except CineError:
            raise
        except Exception as e:
            attempt += 1
            if attempt > retries:
                raise e
            Log.debug(f"Retry {attempt}/{retries} after error: {e}")
            time.sleep(current_delay)
            current_delay *= backoff


def which(cmd: str) -> str | None:
    """Return absolute path to a command, or None if missing."""
    return shutil.which(cmd)


def ensure_command(cmd: str, hint: str = "") -> str:
    """Raise PlayerNotFoundError if a required command is missing."""
    path = which(cmd)
    if path is None:
        extra = f" ({hint})" if hint else ""
        raise PlayerNotFoundError(f"Required command '{cmd}' not found{extra}. ")
    return path


def pipe_to_command(
    cmd: list[str], stdin: str | None = None
) -> subprocess.CompletedProcess:
    """Run a command, piping stdin if given, capturing stdout/stderr."""
    return subprocess.run(
        cmd,
        input=stdin if stdin is not None else None,
        capture_output=True,
        text=True,
    )


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Strip characters unsafe in filenames."""
    import re

    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return cleaned[:max_len].rstrip(" .")
