"""Rich-based TUI for cinebox (replaces the fzf UI)."""

from __future__ import annotations

from .components import EpisodeChoice, Setting, UIManager
from .terminal import get_key

__all__ = ["EpisodeChoice", "Setting", "UIManager", "get_key"]
