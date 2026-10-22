"""Shared pytest setup: keep every test away from the real user config."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_cinebox_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv(
        "CINEBOX_CONFIG_DIR",
        str(tmp_path_factory.mktemp("cinebox-config")),
    )
