"""Render movie posters as ANSI truecolor art in the terminal.

The poster (if any) is downloaded over HTTP, resized to fit the panel
height while preserving aspect ratio, and rendered with the upper
half-block character (``▀``): each cell shows one source pixel on top
(foreground truecolor) and the next source row below it (background).
Two distinct pixels per character yields the sharpest block art a
terminal can draw. Results are cached in-memory per URL.
"""

from __future__ import annotations

import functools
from io import BytesIO

import numpy as np
from rich.text import Text

from ..config import get
from ..utils import new_http_client


def _poster_pixel_dims(
    source_w: int,
    source_h: int,
    max_height: int,
    scale: float,
    max_chars: int | None = None,
) -> tuple[int, int]:
    """Compute the (width, height) pixel grid for a poster.

    ``scale`` is the terminal cell aspect compensation (width factor,
    default 1.0 assumes a ~2:1 cell, which half-block pixels match).
    ``max_chars`` (if set) limits the rendered character width so the
    poster never overflows its panel; height shrinks to keep aspect.
    """
    if source_w <= 0 or source_h <= 0:
        return (0, 0)
    height = max(2, max_height * 2)
    width = int((source_w / source_h) * height * scale)
    if max_chars is not None and max_chars >= 1:
        if width > max_chars:
            height = max(2, int(height * max_chars / width))
            width = int((source_w / source_h) * height * scale)
    if height % 2 != 0:
        height -= 1
    return max(1, width), max(2, height)


def _hex(rgb: np.ndarray) -> str:
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def pixel_grid_to_ansi(arr: np.ndarray) -> list[str]:
    """Convert a 2D RGB pixel array to ANSI half-block art lines.

    Each output line corresponds to two source rows; each character is
    the upper half-block ``▀`` with the top pixel as foreground and the
    bottom pixel as background. Pure function (testable without an image).
    """
    height, width = arr.shape[:2]
    output_lines: list[str] = []
    for y in range(0, height - 1, 2):
        line_parts: list[str] = []
        for x in range(width):
            top = arr[y, x]
            bottom = arr[y + 1, x]
            line_parts.append(f"[{_hex(top)} on {_hex(bottom)}]▀[/]")
        output_lines.append("".join(line_parts))
    return output_lines


@functools.lru_cache(maxsize=64)
def render_poster(
    poster_url: str,
    max_height: int = 40,
    max_chars: int | None = None,
) -> Text:
    """Download a poster and return it as a Rich Text of ANSI block art.

    ``max_chars`` caps the rendered character width so the poster never
    overflows its panel; height shrinks to preserve aspect.

    Returns a friendly fallback text on any failure so callers never crash.
    """
    if not poster_url:
        return Text("No poster available", style="secondary")
    try:
        from PIL import Image  # noqa: PLC0415 - lazy optional deps

        scale = float(get("ui", "poster_scale", 1.0))

        with new_http_client(timeout=8.0) as client:
            res = client.get(poster_url)
            res.raise_for_status()
        img = Image.open(BytesIO(res.content)).convert("RGB")

        new_width, new_height = _poster_pixel_dims(
            img.width, img.height, max_height, scale, max_chars,
        )
        if new_width < 1 or new_height < 2:
            return Text("No poster available", style="secondary")

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        arr = np.array(img, dtype=np.uint8)
        text = Text.from_markup("\n".join(pixel_grid_to_ansi(arr)))
        return text
    except Exception:  # noqa: BLE001 - poster rendering must never crash the UI
        return Text("Poster unavailable", style="dim")
