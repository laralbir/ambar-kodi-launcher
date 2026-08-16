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
    track_id: str | None = None
    progress: int = 0
    elapsed_seconds: int = 0
    total_seconds: int = 0
    # Vocabulario unificado entre Kodi/Spotify (ver KodiGateway.get_state,
    # SpotifyGateway.get_state, WindowsSMTCGateway._get_state): shuffle es
    # simplemente activado/desactivado; repeat usa los mismos valores que
    # ya usa la propia API de Kodi de forma nativa ("off"/"one"/"all" --
    # Spotify y SMTC traducen los suyos a este vocabulario al leerlo, y de
    # vuelta al suyo propio al escribirlo).
    shuffle: bool = False
    repeat: str = "off"
