import asyncio
import sys
import threading
from typing import Callable

try:
    from winrt.windows.media import (
        MediaPlaybackStatus,
        MediaPlaybackType,
        SystemMediaTransportControlsButton,
    )
    from winrt.windows.media.playback import MediaPlayer
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False


class WindowsSMTCPublisher:
    """Publica una sesion SMTC (Windows.Media.Control) propia que
    representa a Kodi -- Windows enruta las teclas multimedia (play/pausa/
    siguiente/anterior) del mando o el teclado a la sesion SMTC que
    considere "actual", y Kodi no se registra como una por si mismo
    (confirmado: sin soporte nativo ni addon para esto, ver
    forum.kodi.tv/showthread.php?tid=375121). Sin esto, esas teclas solo
    llegaban a la sesion de Spotify (la unica que existia), sonara Kodi o
    Spotify -- confirmado en vivo con un mando G20S Pro real.

    Esta sesion solo se activa (PlaybackStatus Playing/Paused) mientras
    Kodi es la fuente activa (ver update()) -- en cuanto deja de serlo se
    cierra (Closed) para no competir con la sesion nativa de Spotify por
    la atencion de Windows cuando es Spotify quien realmente suena (esa
    ya funciona sola, ver WindowsSMTCGateway).

    A diferencia de WindowsSMTCGateway (que solo LEE la sesion de
    Spotify), aqui se crea un `MediaPlayer` real -- es el unico mecanismo
    fiable para obtener un `SystemMediaTransportControls` publicable desde
    una app Win32 clasica (no UWP) con pywinrt; nunca se reproduce audio
    de verdad a traves de el, solo se usa como vehiculo para el objeto
    SMTC. Necesita quedar referenciado mientras dure el proceso o Windows
    lo recicla y la sesion desaparece."""

    def __init__(
        self,
        on_playpause: Callable[[], None],
        on_next: Callable[[], None],
        on_previous: Callable[[], None],
    ):
        self._on_playpause = on_playpause
        self._on_next = on_next
        self._on_previous = on_previous
        self._loop: asyncio.AbstractEventLoop | None = None
        self._player = None
        self._smtc = None
        self._updater = None
        if WINRT_AVAILABLE and sys.platform == "win32":
            ready = threading.Event()
            threading.Thread(target=self._run_loop, args=(ready,), daemon=True).start()
            ready.wait(timeout=5)

    def _run_loop(self, ready: threading.Event) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._setup()
        except Exception:
            self._loop = None
        ready.set()
        if self._loop:
            self._loop.run_forever()

    def _setup(self) -> None:
        self._player = MediaPlayer()
        self._smtc = self._player.system_media_transport_controls
        self._smtc.is_enabled = True
        self._smtc.is_play_enabled = True
        self._smtc.is_pause_enabled = True
        self._smtc.is_next_enabled = True
        self._smtc.is_previous_enabled = True
        self._smtc.playback_status = MediaPlaybackStatus.CLOSED
        self._updater = self._smtc.display_updater
        self._updater.type = MediaPlaybackType.MUSIC
        self._smtc.add_button_pressed(self._on_button_pressed)

    def _on_button_pressed(self, sender, args) -> None:
        # Callback nativo de WinRT -- no bloquear aqui (la llamada real a
        # Kodi es una peticion HTTP), se delega a un hilo aparte.
        button = args.button
        if button in (SystemMediaTransportControlsButton.PLAY, SystemMediaTransportControlsButton.PAUSE):
            threading.Thread(target=self._on_playpause, daemon=True).start()
        elif button == SystemMediaTransportControlsButton.NEXT:
            threading.Thread(target=self._on_next, daemon=True).start()
        elif button == SystemMediaTransportControlsButton.PREVIOUS:
            threading.Thread(target=self._on_previous, daemon=True).start()

    def update(self, active: bool, playing: bool, title: str = "", artist: str = "", album: str = "") -> None:
        """Llamar cada vez que cambia el estado de reproduccion combinado
        (ver bootstrap.py, suscrito a PlaybackStateChanged) -- active=True
        solo cuando Kodi es la fuente que esta sonando ahora mismo."""
        if not self._loop:
            return
        self._loop.call_soon_threadsafe(self._update_sync, active, playing, title, artist, album)

    def _update_sync(self, active: bool, playing: bool, title: str, artist: str, album: str) -> None:
        try:
            if not active:
                self._smtc.playback_status = MediaPlaybackStatus.CLOSED
                return
            self._updater.music_properties.title = title or ""
            self._updater.music_properties.artist = artist or ""
            self._updater.music_properties.album_title = album or ""
            self._updater.update()
            self._smtc.playback_status = (
                MediaPlaybackStatus.PLAYING if playing else MediaPlaybackStatus.PAUSED
            )
        except Exception:
            pass
