"""Unit tests for the TUI themes, art, and poster pure function."""

import numpy as np

from cinebox.ui import poster
from cinebox.ui.art import get_goodbye_renderable, get_header_renderable
from cinebox.ui.components import EpisodeChoice, Setting
from cinebox.ui.poster import _poster_pixel_dims, pixel_grid_to_ansi
from cinebox.ui.themes import THEME_NAMES, THEMES, highlight_style


def test_themes_all_present():
    assert len(THEMES) == 17
    assert len(THEME_NAMES) == 17
    assert "blue" in THEMES
    assert "sunset" in THEMES


def test_highlight_style_uses_theme_colors():
    style = highlight_style()
    assert "on " in style
    assert "bold" in style


def test_header_renderable_nonempty():
    text = get_header_renderable()
    assert len(str(text)) > 100


def test_goodbye_renderable():
    text = get_goodbye_renderable()
    assert len(str(text)) > 20


def test_pixel_grid_to_ansi_uniform():
    arr = np.array([[[100, 150, 200]], [[100, 150, 200]]], dtype=np.uint8)
    lines = pixel_grid_to_ansi(arr)
    assert len(lines) == 1
    assert "▀" in lines[0]


def test_pixel_grid_to_ansi_two_rows():
    arr = np.zeros((4, 2, 3), dtype=np.uint8)
    arr[0, 0] = [255, 255, 255]
    arr[0, 1] = [0, 0, 0]
    arr[1, 0] = [0, 0, 0]
    arr[1, 1] = [255, 255, 255]
    arr[2, :] = [[50, 50, 50], [50, 50, 50]]
    arr[3, :] = [[50, 50, 50], [50, 50, 50]]
    lines = pixel_grid_to_ansi(arr)
    assert len(lines) == 2
    for ln in lines:
        assert "▀" in ln
        assert "on #" in ln


def test_pixel_grid_to_ansi_top_bottom_colors():
    arr = np.zeros((2, 1, 3), dtype=np.uint8)
    arr[0, 0] = [255, 255, 255]
    arr[1, 0] = [0, 0, 0]
    lines = pixel_grid_to_ansi(arr)
    assert len(lines) == 1
    assert "[#ffffff on #000000]▀" in lines[0]


def test_episode_choice_defaults():
    ec = EpisodeChoice(action="play", index=0)
    assert ec.marked == ()
    assert ec.action == "play"


def test_setting_dataclass():
    s = Setting(label="Theme", value_text="blue", edit_id="theme")
    assert s.label == "Theme"
    assert s.edit_id == "theme"


def test_poster_pixel_dims_even_height():
    w, h = _poster_pixel_dims(700, 1037, 20, 1.0)
    assert h % 2 == 0
    assert w >= 1


def test_poster_pixel_dims_aspect():
    w, h = _poster_pixel_dims(700, 1037, 20, 1.0)
    expected_w = int(0.675 * 40 * 1.0)
    assert abs(w - expected_w) <= 2


def test_poster_pixel_dims_max_chars_clamps():
    w, h = _poster_pixel_dims(700, 1037, 40, 1.0, max_chars=15)
    assert w <= 15
    # aspect preserved: char_w / char_h ≈ (source_w/source_h) * 2 * scale
    char_h = h // 2
    expected = (700 / 1037) * 2.0 * 1.0  # ≈ 1.35
    assert abs(w / max(1, char_h) - expected) < 0.6


def test_poster_pixel_dims_min_size():
    w, h = _poster_pixel_dims(700, 1037, 1, 1.0)
    assert w >= 1
    assert h >= 2


def test_poster_pixel_dims_zero_source():
    w, h = _poster_pixel_dims(0, 0, 20, 1.0)
    assert w == 0
    assert h == 0


def test_theme_reload_updates_art(monkeypatch, tmp_path):
    from cinebox import config
    from cinebox.ui import themes

    monkeypatch.setenv("CINEBOX_CONFIG_DIR", str(tmp_path / "config"))
    config.set_config("ui", "theme", "red")
    themes.reload_theme()
    try:
        assert themes.COLOR_BORDER == themes.THEMES["red"]["border"]
        text = get_header_renderable()
        assert text.spans[0].style == f"bold {themes.THEMES['red']['ascii']}"
    finally:
        config.set_config("ui", "theme", "blue")
        themes.reload_theme()


def test_invalid_poster_scale_falls_back(monkeypatch):
    monkeypatch.setattr(poster, "get", lambda *args: "not-a-number")
    assert poster.configured_poster_scale() == 1.0
