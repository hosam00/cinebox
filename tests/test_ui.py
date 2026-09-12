"""Unit tests for the TUI themes, art, and poster pure function."""

import numpy as np

from cinebox.ui.art import get_goodbye_renderable, get_header_renderable
from cinebox.ui.components import EpisodeChoice, Setting
from cinebox.ui.poster import QUADRANTS, pixel_grid_to_ansi
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
    arr = np.array([[[100, 150, 200]]], dtype=np.uint8)
    lines = pixel_grid_to_ansi(arr)
    assert len(lines) == 1
    assert QUADRANTS[15] in lines[0]


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
        assert "on #" in ln


def test_episode_choice_defaults():
    ec = EpisodeChoice(action="play", index=0)
    assert ec.marked == ()
    assert ec.action == "play"


def test_setting_dataclass():
    s = Setting(label="Theme", value_text="blue", edit_id="theme")
    assert s.label == "Theme"
    assert s.edit_id == "theme"
