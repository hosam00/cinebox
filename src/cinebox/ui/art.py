"""ASCII art banners for cinebox."""

from __future__ import annotations

from rich.text import Text

from .themes import COLOR_ASCII, COLOR_TITLE

HEADER_ART = r"""
  ▄████████ ▄█   ▄█▄    ▄████████    ▄████████ ▄██████▄     ▄████████ ███▄▄▄▄
 ███    ███ ███ ▄███▀   ███    ███   ███    ███ ███    ███   ███    ███ ███▀▀▀██▄
 ███    █▀  ███▐██▀     ███    █▀    ███    █▀  ███    █▀    ███    ███ ███   ███
 ███        ▄█████▀    ▄███▄▄▄       ███        ███          ███    ███ ███   ███
▀███████████▀▀█████▄  ▀▀███▀▀▀     ▀███████████ ███        ▀███████████ ███   ███
 ███    ███   ███▐██▄   ███    █▄           ███ ███    ███   ███    ███ ███   ███
 ███    ███   ███ ▀███▄ ███    ███    ▄█    ███ ███    ███   ███    ███ ███   ███
 ██████████   ███   ▀█▀ ██████████  ▄████████▀  ████████▀    ███    █▀   ▀█   █▀
                           Stream · Watch · Download
"""

GOODBYE_ART = r"""
  ▄████████ ███▄▄▄▄    ▄█   ▄█▄
 ███    ███ ███▀▀▀██▄ ███  ████
 ███    █▀  ███   ███ ███▌ ████
 ███        ███   ███ ███▌ ▐██
▀███████████ ███   ███ ███▌  ██
 ███    ███ ███   ███ ███   ▄████▄
 ███    ███ ███   ███ ███  ███▀  ██
 ██████████  ▀█   █▀  █▀  ███   ██
                           ▀▀▀▀ ▀▀
"""

# Compact fallback for narrower terminals where the full banner wraps.
COMPACT_HEADER = (
    "  ____ ___ _   _ _____    ____ _     ___\n"
    " / ___|_ _| \\ | | ____|  / ___| |   |_ _|\n"
    "| |    | ||  \\| |  _|   | |   | |    | |\n"
    "| |___ | || |\\  | |___  | |___| |___ | |\n"
    " \\____|___|_| \\_|_____|  \\____|_____|___|\n"
)


def get_header_renderable() -> Text:
    """Render the cinebox banner with the active theme's ascii color.

    Uses the full block-art banner when the terminal is wide enough to
    avoid wrapping, otherwise a compact wordmark that never exceeds ~72
    columns.
    """
    import shutil

    if shutil.get_terminal_size().columns >= 88:
        body = HEADER_ART.rstrip()
    else:
        body = COMPACT_HEADER.rstrip()
    return Text.from_markup(f"[bold {COLOR_ASCII}]{body}[/]", justify="center")


def get_goodbye_renderable() -> Text:
    return Text.from_markup(f"[bold {COLOR_TITLE}]{GOODBYE_ART.rstrip()}[/]", justify="center")
