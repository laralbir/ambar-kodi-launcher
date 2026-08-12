import threading

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
        # Para detectar transiciones "empezo a sonar ahora mismo" en
        # enforce_single_source -- ver ahi.
        self._kodi_was_playing = False
        self._spotify_was_playing = False
        # Evita que llamadas solapadas a enforce_single_source() (sondeo
        # periodico cada 3s, ver adapters/spotify/poller.py) se acumulen
        # si una tarda mas de la cuenta (p. ej. Spotify via SMTC yendo
        # lento) -- se descarta la nueva en vez de esperar a la anterior,
        # confirmado en vivo que sin esto la navegacion por Kodi se notaba
        # lenta al competir varias llamadas a la vez por el mismo hilo de
        # SMTC (ver WindowsSMTCGateway).
        self._enforce_lock = threading.Lock()

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

    def enforce_single_source(self) -> None:
        """Si una fuente empieza a sonar mientras la otra ya estaba
        sonando, pausa la otra -- para que solo suene una a la vez sin
        importar desde donde se inicio la reproduccion (mando, el propio
        Kodi, Spotify Connect desde el movil...). kodi_play()/
        spotify_play() en LibraryService ya paran la otra fuente cuando
        se arranca reproduccion desde la biblioteca del propio launcher;
        esto cubre el resto de casos. Se llama periodicamente (ver
        adapters/spotify/poller.py, cada 3s) -- limitado a esa cadencia a
        proposito, ver _enforce_lock."""
        if not self._enforce_lock.acquire(blocking=False):
            return
        try:
            kodi_state = self._kodi.get_state()
            spotify_state = self._spotify.get_state()
            kodi_playing = bool(kodi_state and kodi_state.playing)
            spotify_playing = bool(spotify_state and spotify_state.playing)

            kodi_just_started = kodi_playing and not self._kodi_was_playing
            spotify_just_started = spotify_playing and not self._spotify_was_playing

            if kodi_just_started and spotify_playing:
                self._spotify.pause()
            elif spotify_just_started and kodi_playing:
                self._kodi.pause()

            self._kodi_was_playing = kodi_playing
            self._spotify_was_playing = spotify_playing
        finally:
            self._enforce_lock.release()
