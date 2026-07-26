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
