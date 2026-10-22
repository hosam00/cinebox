"""Tests for the interactive settings editor."""

from __future__ import annotations

from cinebox import settings as settings_mod
from cinebox.settings import SettingsEditor


class FakeUI:
    def __init__(self, menu_choice=None, answer=""):
        self.menu_choice = menu_choice
        self.answer = answer
        self.asked = []

    def generic_menu(self, choices, title, subtitle=None):
        return self.menu_choice

    def ask(self, prompt, default=None, secret=False):
        self.asked.append((prompt, default, secret))
        return self.answer


def test_edit_dir_back_does_not_write(monkeypatch):
    writes = []
    monkeypatch.setattr(settings_mod, "get", lambda *a: "~/Movies")
    monkeypatch.setattr(settings_mod, "set_config", lambda *a: writes.append(a))
    editor = SettingsEditor(FakeUI(menu_choice=None))
    editor.edit("movies_dir")
    assert writes == []


def test_edit_dir_custom_path(monkeypatch, tmp_path):
    writes = []
    monkeypatch.setattr(settings_mod, "get", lambda *a: "~/Movies")
    monkeypatch.setattr(settings_mod, "set_config", lambda *a: writes.append(a))
    custom_index = len(settings_mod.DIRS)
    editor = SettingsEditor(FakeUI(menu_choice=custom_index, answer=str(tmp_path / "Films")))
    editor.edit("movies_dir")
    assert writes == [("download", "movies_dir", str(tmp_path / "Films"))]


def test_open_subtitles_toggle(monkeypatch):
    writes = []
    monkeypatch.setattr(
        settings_mod,
        "get",
        lambda section, key, default=None: (
            True if (section, key) == ("opensubtitles", "enabled") else default
        ),
    )
    monkeypatch.setattr(settings_mod, "set_config", lambda *a: writes.append(a))
    SettingsEditor(FakeUI()).edit("os_enabled")
    assert writes == [("opensubtitles", "enabled", False)]


def test_open_subtitles_username_edit(monkeypatch):
    writes = []
    monkeypatch.setattr(settings_mod, "get", lambda *a: "")
    monkeypatch.setattr(settings_mod, "set_config", lambda *a: writes.append(a))
    SettingsEditor(FakeUI(menu_choice=0, answer="alice")).edit("os_username")
    assert writes == [("opensubtitles", "username", "alice")]


def test_open_subtitles_password_uses_secret_prompt(monkeypatch):
    writes = []
    monkeypatch.setattr(settings_mod, "get", lambda *a: "")
    monkeypatch.setattr(settings_mod, "set_config", lambda *a: writes.append(a))
    ui = FakeUI(menu_choice=0, answer="hunter2")
    SettingsEditor(ui).edit("os_password")
    assert writes == [("opensubtitles", "password", "hunter2")]
    assert ui.asked[-1][2] is True
