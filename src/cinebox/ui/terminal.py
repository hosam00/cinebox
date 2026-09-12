"""Low-level terminal handling: raw/cbreak mode and single-key reading."""

from __future__ import annotations

import os
import select
import sys
import time

if os.name == "nt":  # pragma: no cover - not exercised on Linux CI
    import msvcrt
else:
    import termios
    import tty


class RawTerminal:
    """Context manager switching the terminal to cbreak mode (POSIX).

    cbreak (rather than raw) keeps Ctrl+C signal handling working. On
    Windows this is a no-op since msvcrt drives input.
    """

    _active_instance: RawTerminal | None = None

    def __init__(self) -> None:
        self.fd: int | None = None
        self.old_settings = None

    def __enter__(self) -> RawTerminal:
        if os.name != "nt":
            try:
                self.fd = sys.stdin.fileno()
                self.old_settings = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
                RawTerminal._active_instance = self
            except (termios.error, OSError, ValueError):
                self.old_settings = None
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        RawTerminal._active_instance = None
        if os.name != "nt" and self.old_settings is not None:
            try:
                termios.tcflush(self.fd, termios.TCIFLUSH)
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except (termios.error, OSError):
                pass


def restore_terminal_for_input() -> None:
    """Temporarily restore normal mode so Rich's Prompt.ask works.

    Call this before Prompt.ask inside a RawTerminal context, then call
    enter_raw_mode_after_input() afterwards.
    """
    if os.name == "nt":
        return
    instance = RawTerminal._active_instance
    if instance and instance.old_settings is not None:
        try:
            termios.tcsetattr(instance.fd, termios.TCSADRAIN, instance.old_settings)
        except (termios.error, OSError):
            pass


def enter_raw_mode_after_input() -> None:
    """Re-enter cbreak mode after a Prompt.ask inside raw mode."""
    if os.name == "nt":
        return
    instance = RawTerminal._active_instance
    if instance and instance.old_settings is not None:
        try:
            tty.setcbreak(instance.fd)
        except (termios.error, OSError):
            pass


def flush_stdin() -> None:
    """Discard any pending input bytes."""
    if os.name == "nt":
        import msvcrt  # noqa: PLC0415 - local import on purpose

        while msvcrt.kbhit():
            msvcrt.getch()
        return
    try:
        termios.tcflush(sys.stdin.fileno(), termios.TCIOFLUSH)
    except (termios.error, OSError):
        pass


def get_key() -> str | None:
    """Read a single normalized key press (blocking, needs raw/cbreak mode).

    Returns tokens like 'UP', 'DOWN', 'RIGHT', 'LEFT', 'ENTER', 'ESC',
    'q', 'b', 'd', 'f', 'm', ' ' or a single printable character.
    Returns None only on non-blocking situations (not used here).
    """
    if os.name == "nt":  # pragma: no cover
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"\xe0", b"\x00"):
                key2 = msvcrt.getch()
                return {"H": "UP", "P": "DOWN", "M": "RIGHT", "K": "LEFT"}.get(
                    key2.decode("latin1", "ignore"), None
                )
            if key == b"\r":
                return "ENTER"
            ch = key.decode("utf-8", errors="ignore")
            return ch.lower() if ch.isalnum() else ch
        return None

    fd = sys.stdin.fileno()
    try:
        ch_bytes = os.read(fd, 1)
    except OSError:
        return None
    if not ch_bytes:
        return None

    ch = ch_bytes.decode("utf-8", errors="ignore")

    if ch == "\x03":
        raise KeyboardInterrupt

    if ch == "\x1b":
        seq = ch
        end_time = time.time() + 0.02
        while time.time() < end_time:
            if select.select([fd], [], [], 0.005)[0]:
                try:
                    next_byte = os.read(fd, 1)
                except OSError:
                    break
                if not next_byte:
                    break
                seq += next_byte.decode("utf-8", errors="ignore")
                if len(seq) >= 3:
                    last = seq[-1]
                    if (seq.startswith("\x1b[") or seq.startswith("\x1bO")) and last in "ABCD":
                        return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}[last]
            else:
                break
        return "ESC" if seq == "\x1b" else None

    if ch in "\r\n":
        return "ENTER"
    if ch.lower() in "qgbdlfms":
        return ch.lower()
    if ch == " ":
        return " "
    return ch
