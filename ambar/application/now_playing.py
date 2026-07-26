from ambar.domain.events import PlaybackStateChanged
from ambar.domain.playback import PlaybackState
from ambar.ports.playback_source import PlaybackSource


class NowPlayingService:
    """Decide que fuente manda (Kodi tiene prioridad sobre Spotify) y publica
    PlaybackStateChanged en el EventBus. Reutilizado tanto por la ruta HTTP
    /api/now-playing como por los listeners de fondo de Kodi/Spotify."""

    def __init__(self, kodi_source: PlaybackSource, spotify_source: PlaybackSource, event_bus):
        self._kodi = kodi_source
        self._spotify = spotify_source
        self._event_bus = event_bus
        self.last_source: str | None = None

    def get_state(self) -> PlaybackState:
        state = self._kodi.get_state() or self._spotify.get_state()
        if not state:
            state = PlaybackState()
        self.last_source = state.source
        return state

    def get_playlist(self) -> list:
        state = self.get_state()
        if state.source == "kodi":
            return self._kodi.get_playlist()
        elif state.source == "spotify":
            return self._spotify.get_playlist()
        return []

    def publish_current_state(self) -> None:
        self._event_bus.publish(PlaybackStateChanged(self.get_state()))

    def poll_spotify(self) -> None:
        """Solo consulta y publica Spotify si Kodi no es la ultima fuente activa
        conocida (evita pisar el estado de Kodi y no abusar de la API)."""
        if self.last_source == "kodi":
            return
        state = self._spotify.get_state()
        if state:
            self._event_bus.publish(PlaybackStateChanged(state))
