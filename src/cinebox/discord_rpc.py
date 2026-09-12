"""Optional Discord Rich Presence integration.

Uses pypresence to announce what the user is watching. Gated behind the
``[discord] enabled`` config flag and requires a Discord application
client ID (set as ``[discord] client_id``). All failures are silently
swallowed so the presence layer never disturbs playback.
"""

from __future__ import annotations

import threading

from .config import get


class DiscordRPCManager:
    """Thin, fully-optional wrapper around pypresence."""

    def __init__(self) -> None:
        self._client = None
        self._presence = None
        self._enabled = False
        self._connected = False
        self._lock = threading.Lock()

    def enabled(self) -> bool:
        self._enabled = bool(get("discord", "enabled", False) and get("discord", "client_id", ""))
        return self._enabled

    def connect(self) -> bool:
        if not self.enabled():
            return False
        try:
            from pypresence import Presence  # noqa: PLC0415 - optional dep

            client_id = get("discord", "client_id", "")
            self._client = Presence(client_id)
            self._client.connect()
            self._presence = self._client
            self._connected = True
            return True
        except Exception:  # noqa: BLE001
            self._connected = False
            return False

    def update_status(self, title: str, media_type: str = "", detail: str = "") -> None:
        if not self._connected and not self.connect():
            return
        try:
            state = detail or media_type or "Watching"
            self._presence.update(
                state=state,
                details=title,
                large_text="cinebox",
                small_text="▶ Streaming",
            )
        except Exception:  # noqa: BLE001
            self._connected = False

    def clear(self) -> None:
        if self._presence is not None:
            try:
                self._presence.clear()
                self._presence.close()
            except Exception:  # noqa: BLE001
                pass
        self._connected = False
