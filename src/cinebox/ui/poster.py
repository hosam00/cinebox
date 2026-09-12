"""Render movie posters as ANSI truecolor art in the terminal.

The poster (if any) is downloaded over HTTP, resized to fit the panel
height while preserving aspect ratio, and each 2x2 pixel block is
collapsed to a single Unicode quadrant character with fg/bg truecolor
escape codes. Results are cached in-memory per URL.
"""

from __future__ import annotations

import functools
from io import BytesIO

import numpy as np
from rich.text import Text

from ..utils import new_http_client

QUADRANTS = [" ", "▘", "▝", "▀", "▖", "▌", "▞", "▛", "▗", "▚", "▐", "▜", "▄", "▙", "▟", "█"]


def _hex(rgb: np.ndarray) -> str:
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def pixel_grid_to_ansi(arr: np.ndarray) -> list[str]:
    """Convert a 2D RGB pixel array (even dims preferred) to ANSI block-art lines.

    Each output line corresponds to two source rows; each character to a
    2x2 quadrant block. Pure function (testable without an image).
    """
    height, width = arr.shape[:2]
    output_lines: list[str] = []
    for y in range(0, height, 2):
        line_parts: list[str] = []
        for x in range(0, width, 2):
            p0 = arr[y, x]
            p1 = arr[y, x + 1] if x + 1 < width else p0
            p2 = arr[y + 1, x] if y + 1 < height else p0
            p3 = arr[y + 1, x + 1] if (y + 1 < height and x + 1 < width) else p0

            def lum(p) -> float:
                return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]

            pix = [p0, p1, p2, p3]
            lums = [lum(p) for p in pix]
            avg = sum(lums) / 4
            mask = [lm > avg for lm in lums]

            bright = [p for p, m in zip(pix, mask, strict=True) if m]
            dark = [p for p, m in zip(pix, mask, strict=True) if not m]

            fg = np.mean(bright, axis=0).astype(int) if bright else np.mean(pix, axis=0).astype(int)
            bg = np.mean(dark, axis=0).astype(int) if dark else fg

            if all(mask) or not any(mask):
                char_idx = 15
            else:
                q_val = 0
                for i, m in enumerate(mask):
                    if m:
                        q_val += 1 << i
                char_idx = q_val

            line_parts.append(f"[{_hex(fg)} on {_hex(bg)}]{QUADRANTS[char_idx]}[/]")
        output_lines.append("".join(line_parts))
    return output_lines


@functools.lru_cache(maxsize=64)
def render_poster(poster_url: str, max_height: int = 40) -> Text:
    """Download a poster and return it as a Rich Text of ANSI block art.

    Returns a friendly fallback text on any failure so callers never crash.
    """
    if not poster_url:
        return Text("No poster available", style="secondary")
    try:
        from PIL import Image, ImageEnhance  # noqa: PLC0415 - lazy optional deps

        with new_http_client(timeout=8.0) as client:
            res = client.get(poster_url)
            res.raise_for_status()
        img = Image.open(BytesIO(res.content)).convert("RGB")

        img = ImageEnhance.Sharpness(img).enhance(1.8)
        img = ImageEnhance.Contrast(img).enhance(1.15)

        target_pixel_height = max_height * 2
        new_height = target_pixel_height
        new_width = int((img.width / img.height) * new_height * 2.0)
        if new_width % 2 != 0:
            new_width -= 1
        if new_height % 2 != 0:
            new_height -= 1

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        arr = np.array(img, dtype=np.uint8)
        text = Text.from_markup("\n".join(pixel_grid_to_ansi(arr)))
        return text
    except Exception:  # noqa: BLE001 - poster rendering must never crash the UI
        return Text("Poster unavailable", style="dim")
