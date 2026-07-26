from dataclasses import dataclass


@dataclass
class PlaybackState:
    """Estado de reproduccion unificado, independiente de la fuente (Kodi/Spotify)."""

    source: str | None = None
    playing: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    art: str | None = None
    progress: int = 0
