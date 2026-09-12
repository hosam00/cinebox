"""Unit tests for the downloader helpers."""

import pytest

from cinebox.downloader import (
    _format_selector,
    episode_filename,
    format_selector_for_height,
    resolution_height,
)


def test_format_selector_named_qualities():
    assert "height<=480" in _format_selector("480p")
    assert "height<=720" in _format_selector("720p")
    assert "height<=1080" in _format_selector("1080p")
    assert _format_selector("best") == "bestvideo+bestaudio/best"


def test_format_selector_unknown_raises():
    with pytest.raises(ValueError):
        _format_selector("144p")


def test_resolution_height_parses_label():
    assert resolution_height("1920x800 (4.5 Mbps)") == 800
    assert resolution_height("1280x534 (2.3 Mbps)") == 534
    assert resolution_height("640x266 (0.7 Mbps)") == 266


def test_resolution_height_defaults_to_1080():
    assert resolution_height("unknown") == 1080
    assert resolution_height("4K Ultra HD") == 2160


def test_format_selector_for_height():
    assert "height<=480" in format_selector_for_height(480)
    assert "height<=720" in format_selector_for_height(700)
    assert "height<=1080" in format_selector_for_height(1080)
    assert "height<=2160" in format_selector_for_height(2160)


def test_episode_filename():
    assert episode_filename("Breaking Bad", 1, 1) == "Breaking Bad - S01E01"
    assert episode_filename("Breaking Bad", 12, 305) == "Breaking Bad - S12E305"
