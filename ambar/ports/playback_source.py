from typing import Protocol

from ambar.domain.playback import PlaybackState


class PlaybackSource(Protocol):
    """Puerto que implementan las fuentes de reproduccion (Kodi, Spotify)."""

    def get_state(self) -> PlaybackState | None: ...

    def control(self, action: str) -> None: ...

    def seek(self, percentage: float) -> None: ...
