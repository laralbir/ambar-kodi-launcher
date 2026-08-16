import asyncio
import sys
import threading

from ambar.domain.playback import PlaybackState

try:
    from winrt.windows.media import MediaPlaybackAutoRepeatMode
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winrt.windows.storage.streams import Buffer, InputStreamOptions
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False


class WindowsSMTCGateway:
    """Ahora-suena y control de Spotify via SMTC (System Media Transport
    Controls, Windows.Media.Control) en vez de la Web API -- solo funciona
    si el propio Spotify de escritorio esta instalado y sonando en ESTA
    misma maquina Windows (no sirve para reflejar una reproduccion elegida
    desde el movil por Spotify Connect: SMTC solo ve sesiones locales).

    Motivo de existir: la Web API de Spotify tiene limite de peticiones, y
    el sondeo de "ahora suena" cada 2s lo agota tarde o temprano (ver
    CHANGELOG.md, "rate_limited_until"). SMTC es una API nativa de Windows
    (la misma que usa el propio Windows para el mini-reproductor de la
    barra de tareas) sin limite de peticiones ni autenticacion -- IPC local,
    no red. SpotifyGateway la usa con preferencia sobre la Web API para
    get_state/control/seek/pause cuando esta disponible (ver
    spotify/gateway.py), y cae a la Web API si no hay sesion local (p.ej.
    reproduciendo desde el movil, o en macOS en desarrollo).

    Requiere los paquetes modulares winrt-Windows.Media.Control /
    winrt-Windows.Storage.Streams / winrt-Windows.Foundation.Collections
    (ver requirements.txt) -- NO el paquete "winsdk" (su sucesor oficial),
    que en la fecha de este commit no publica rueda para Python 3.13.

    Todas las llamadas WinRT son async y viven en un hilo de fondo con su
    propio bucle de asyncio (en vez de asyncio.run() por peticion): los
    objetos WinRT/COM son afines al hilo que los crea, y crear/destruir un
    bucle en cada peticion del servidor (una peticion = un hilo nuevo, ver
    Flask-SocketIO threaded=True) tendria un coste real dado que esto se
    consulta cada 2s.
    """

    # Coincide con el AUMID reportado por el Spotify de escritorio clasico
    # (Spotify.exe) -- comprobado en vivo. Sirve tambien para la version de
    # Microsoft Store, cuyo AUMID largo tambien contiene "spotify".
    _AUMID_NEEDLE = "spotify"
    # Orden de ciclo para "repeat_cycle", en el vocabulario comun de la
    # app ("off"/"one"/"all", ver domain/playback.py) -- igual que el
    # "cycle" nativo de Kodi (Player.Repeat.Extended).
    _REPEAT_CYCLE = {"off": "one", "one": "all", "all": "off"}

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager = None
        self._last_track_key: str | None = None
        self._last_art_bytes: bytes | None = None
        self._last_art_mime: str = "image/png"
        self._art_version = 0
        if WINRT_AVAILABLE and sys.platform == "win32":
            ready = threading.Event()
            threading.Thread(target=self._run_loop, args=(ready,), daemon=True).start()
            ready.wait(timeout=5)

    def _run_loop(self, ready: threading.Event) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        ready.set()
        self._loop.run_forever()

    def _run(self, coro, timeout: float = 5.0):
        if not self._loop:
            return None
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=timeout)
        except Exception:
            return None

    async def _get_manager(self):
        if self._manager is None:
            self._manager = await SessionManager.request_async()
        return self._manager

    async def _spotify_session(self):
        manager = await self._get_manager()
        for session in manager.get_sessions():
            aumid = (session.source_app_user_model_id or "").lower()
            if self._AUMID_NEEDLE in aumid:
                return session
        return None

    def is_available(self) -> bool:
        """Hay una sesion de Spotify local activa ahora mismo -- para que
        SpotifyGateway decida si usar esto o caer a la Web API."""
        return self._run(self._spotify_session()) is not None

    def get_state(self) -> PlaybackState | None:
        return self._run(self._get_state())

    async def _get_state(self) -> PlaybackState | None:
        session = await self._spotify_session()
        if not session:
            return None
        try:
            props = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()
            info = session.get_playback_info()
        except Exception:
            return None
        if not props or not props.title:
            return None
        track_key = f"{props.title}|{props.artist}|{props.album_title}"
        if track_key != self._last_track_key:
            self._last_track_key = track_key
            self._last_art_bytes = None
            if props.thumbnail:
                await self._load_thumbnail(props.thumbnail)
        art = f"/api/library/spotify/smtc-art?v={self._art_version}" if self._last_art_bytes else None
        duration = timeline.end_time.total_seconds()
        position = timeline.position.total_seconds()
        return PlaybackState(
            source="spotify",
            playing=info.playback_status == PlaybackStatus.PLAYING,
            title=props.title or "",
            artist=props.artist or "",
            album=props.album_title or "",
            art=art,
            track_id=track_key,
            progress=int(100 * position / duration) if duration > 0 else 0,
            elapsed_seconds=int(position),
            total_seconds=int(duration),
            shuffle=bool(info.is_shuffle_active),
            repeat=self._repeat_from_winrt(info.auto_repeat_mode),
        )

    @staticmethod
    def _repeat_from_winrt(mode) -> str:
        """MediaPlaybackAutoRepeatMode (WinRT) -> vocabulario comun de la
        app ("off"/"one"/"all", ver domain/playback.py). None (no
        reportado por la sesion) se trata como "off"."""
        if mode == MediaPlaybackAutoRepeatMode.TRACK:
            return "one"
        if mode == MediaPlaybackAutoRepeatMode.LIST:
            return "all"
        return "off"

    @staticmethod
    def _repeat_to_winrt(value: str):
        if value == "one":
            return MediaPlaybackAutoRepeatMode.TRACK
        if value == "all":
            return MediaPlaybackAutoRepeatMode.LIST
        return MediaPlaybackAutoRepeatMode.NONE

    async def _load_thumbnail(self, thumbnail_ref) -> None:
        try:
            stream = await thumbnail_ref.open_read_async()
            size = stream.size
            # Techo generoso (10MB) solo para no confiar a ciegas en lo que
            # reporte el stream -- las caratulas reales de Spotify rondan
            # unos pocos cientos de KB (confirmado en vivo, ~150KB en PNG).
            if size <= 0 or size > 10_000_000:
                return
            buf = Buffer(size)
            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            self._last_art_bytes = bytes(buf)
            self._last_art_mime = stream.content_type or "image/png"
            self._art_version += 1
        except Exception:
            pass

    def get_art(self) -> tuple[bytes, str] | None:
        """Bytes+mimetype de la caratula ya descargada por get_state() --
        para la ruta /api/library/spotify/smtc-art. No vuelve a leer el
        stream (ya se cachea en _load_thumbnail, una vez por cancion)."""
        if self._last_art_bytes:
            return self._last_art_bytes, self._last_art_mime
        return None

    def control(self, action: str) -> bool:
        return bool(self._run(self._control(action)))

    async def _control(self, action: str) -> bool:
        session = await self._spotify_session()
        if not session:
            return False
        try:
            if action == "playpause":
                return await session.try_toggle_play_pause_async()
            if action == "play":
                return await session.try_play_async()
            if action == "pause":
                return await session.try_pause_async()
            if action == "next":
                return await session.try_skip_next_async()
            if action == "previous":
                return await session.try_skip_previous_async()
            if action == "shuffle_toggle":
                current = session.get_playback_info().is_shuffle_active
                return await session.try_change_shuffle_active_async(not bool(current))
            if action == "repeat_cycle":
                current = self._repeat_from_winrt(session.get_playback_info().auto_repeat_mode)
                next_mode = self._repeat_to_winrt(self._REPEAT_CYCLE.get(current, "off"))
                return await session.try_change_auto_repeat_mode_async(next_mode)
        except Exception:
            return False
        return False

    def pause(self) -> bool:
        return self.control("pause")

    def seek(self, percentage: float) -> bool:
        return bool(self._run(self._seek(percentage)))

    async def _seek(self, percentage: float) -> bool:
        session = await self._spotify_session()
        if not session:
            return False
        try:
            timeline = session.get_timeline_properties()
            duration = timeline.end_time.total_seconds()
            if duration <= 0:
                return False
            target_seconds = duration * max(0.0, min(100.0, percentage)) / 100
            # try_change_playback_position_async espera "ticks" (unidades
            # de 100ns, convencion .NET TimeSpan) como entero -- NO acepta
            # un datetime.timedelta directamente pese a que timeline.position
            # SI devuelve uno (confirmado en vivo: pasar un timedelta lanza
            # TypeError, pasar el entero de ticks funciona).
            ticks = int(target_seconds * 10_000_000)
            return await session.try_change_playback_position_async(ticks)
        except Exception:
            return False
