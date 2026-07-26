from ambar.ports.playback_source import PlaybackSource


class PlaybackControlService:
    """Enruta un comando de transporte (playpause/next/previous) hacia la
    fuente indicada."""

    def __init__(self, kodi_source: PlaybackSource, spotify_source: PlaybackSource):
        self._kodi = kodi_source
        self._spotify = spotify_source

    def execute(self, source: str | None, action: str | None) -> None:
        if source == "kodi":
            self._kodi.control(action)
        elif source == "spotify":
            self._spotify.control(action)

    def seek(self, source: str | None, percentage: float) -> None:
        if source == "kodi":
            self._kodi.seek(percentage)
        elif source == "spotify":
            self._spotify.seek(percentage)

    def play_playlist_item(self, source: str | None, position: int | None, uri: str | None) -> None:
        # Saltar a una pista de la playlist en curso -- distinto de
        # LibraryService.kodi_play/spotify_play (esos arrancan una
        # reproduccion nueva desde la biblioteca con exclusion mutua); aqui
        # ya estamos dentro de la playlist activa de una fuente, asi que no
        # hace falta parar la otra fuente (ya deberia estar parada).
        if source == "kodi" and position is not None:
            self._kodi.goto_position(position)
        elif source == "spotify" and uri:
            self._spotify.play_track(uri)
