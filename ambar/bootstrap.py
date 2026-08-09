"""Composition root: instancia adapters, los inyecta en los servicios de
aplicacion, conecta el EventBus y arranca el servidor (+ ventana pywebview)."""

import os
import sys
import threading
import time
from dataclasses import dataclass

from flask import Flask
from flask_socketio import SocketIO

from ambar.adapters.audio.null_source import NullAudioLevelSource
from ambar.adapters.audio.null_volume import NullVolumeController
from ambar.adapters.desktop.null_wake_lock import NullWakeLock
from ambar.adapters.desktop.webview_window import WebviewWindowController
from ambar.adapters.kodi.gateway import KodiGateway
from ambar.adapters.kodi.ws_listener import listen as kodi_listen
from ambar.adapters.musicbrainz.gateway import MusicBrainzGateway
from ambar.adapters.persistence.json_config_repository import JsonConfigRepository
from ambar.adapters.spotify.gateway import SpotifyGateway
from ambar.adapters.spotify.poller import poll as spotify_poll
from ambar.adapters.web.app import create_app
from ambar.adapters.web.socketio_bridge import SocketIOBridge
from ambar.application.audio_level import AudioLevelService
from ambar.application.config import ConfigService
from ambar.application.events import EventBus
from ambar.application.library import LibraryService
from ambar.application.now_playing import NowPlayingService
from ambar.application.playback_control import PlaybackControlService
from ambar.application.skins import SkinService
from ambar.application.system import SystemService
from ambar.domain.audio import VU_SMOOTHING_PRESETS
from ambar.domain.events import AudioLevelChanged, PlaybackStateChanged

# Spotify exige HTTPS en el redirect_uri salvo para la IP de loopback
# literal 127.0.0.1 (no vale el hostname "localhost", pese a resolver al
# mismo sitio -- su validador de la Dashboard lo rechaza igual, confirmado
# en vivo por el usuario). Ademas, por como funciona OAuth, esta URI solo
# puede resolverse correctamente en el mismo equipo donde corre Ambar: si
# se autoriza desde el movil, la redireccion final de Spotify a
# 127.0.0.1:5005/callback apuntaria al propio movil, no al servidor real,
# y la autorizacion nunca llegaria -- ver README.md/docs para el flujo
# correcto (un navegador normal en este mismo equipo, no el movil).
DEFAULT_SPOTIFY_REDIRECT_URI = "http://127.0.0.1:5005/callback"


@dataclass
class AppContainer:
    app_dir: str
    kodi_gateway: KodiGateway
    spotify_gateway: SpotifyGateway
    now_playing_service: NowPlayingService
    playback_control_service: PlaybackControlService
    library_service: LibraryService
    system_service: SystemService
    config_service: ConfigService
    audio_level_service: AudioLevelService
    skin_service: SkinService
    skins_dir: str
    available_screens: list


def _build_volume_controller():
    """Elige el adapter de control de volumen segun la plataforma, con el
    mismo fallback seguro que _build_audio_level_source(): si falla el
    import o la construccion, el control de volumen queda inactivo sin
    romper el arranque del resto de la app."""
    try:
        if sys.platform == "win32":
            from ambar.adapters.audio.windows_volume import WindowsVolumeController

            return WindowsVolumeController()
        if sys.platform == "darwin":
            from ambar.adapters.audio.macos_volume import MacVolumeController

            return MacVolumeController()
    except Exception as e:
        print(f"Control de volumen no disponible ({e}); quedara inactivo.")
    return NullVolumeController()


def _build_wake_lock():
    """Elige el adapter que evita la suspension de pantalla segun la
    plataforma, con el mismo fallback seguro que el resto de adapters
    opcionales: si falla, el kiosko sigue funcionando, solo que sin
    proteccion contra el salvapantallas/reposo."""
    try:
        if sys.platform == "win32":
            from ambar.adapters.desktop.windows_wake_lock import WindowsWakeLock

            return WindowsWakeLock()
        if sys.platform == "darwin":
            from ambar.adapters.desktop.macos_wake_lock import MacWakeLock

            return MacWakeLock()
    except Exception as e:
        print(f"Bloqueo de suspension de pantalla no disponible ({e}); quedara inactivo.")
    return NullWakeLock()


def _build_audio_level_source():
    """Elige el adapter de captura de audio segun la plataforma. Si falla el
    import (dependencia nativa ausente) o la construccion, cae a
    NullAudioLevelSource -- el VU-metro queda inactivo pero el resto de la
    app sigue funcionando con normalidad."""
    try:
        if sys.platform == "win32":
            from ambar.adapters.audio.windows_wasapi import WasapiLoopbackSource

            return WasapiLoopbackSource()
        if sys.platform == "darwin":
            from ambar.adapters.audio.macos_screencapturekit import ScreenCaptureKitAudioSource

            return ScreenCaptureKitAudioSource()
    except Exception as e:
        print(f"VU-meter: nivel de audio real no disponible ({e}); el medidor quedara inactivo.")
    return NullAudioLevelSource()


def _configure_spotify(spotify_gateway: SpotifyGateway, config: dict) -> None:
    client_id = config.get("SPOTIFY_CLIENT_ID") or os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = config.get("SPOTIFY_CLIENT_SECRET") or os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = config.get("SPOTIFY_REDIRECT_URI") or os.environ.get(
        "SPOTIFY_REDIRECT_URI", DEFAULT_SPOTIFY_REDIRECT_URI
    )
    spotify_gateway.configure(client_id, client_secret, redirect_uri)


def _get_available_screens() -> list:
    """Enumera los monitores disponibles para elegir en cual arranca el
    kiosko (relevante porque el mini PC saca a la vez a la pantalla tactil y
    a la TV). DEBE llamarse desde el hilo principal (webview.screens usa
    APIs nativas -- NSScreen en macOS -- con la misma restriccion de hilo
    principal que el resto de pywebview), asi que se calcula aqui, en
    _build_container(), antes de arrancar ningun hilo de fondo, y se guarda
    como datos planos (int) en el container para que las rutas Flask (que
    corren en un hilo de fondo) puedan leerlo sin volver a tocar pywebview."""
    try:
        import webview
        return [{"index": i, "width": s.width, "height": s.height} for i, s in enumerate(webview.screens)]
    except Exception:
        return []


def _get_data_dir(resource_dir: str) -> str:
    """Directorio persistente para config.json/.spotify-cache/skins: junto
    al ejecutable/bundle, igual en Windows y macOS.

    En modo desarrollo, junto al codigo (resource_dir, comodo para iterar).
    En el binario compilado, NO se usa __file__ (en un app frozen de
    PyInstaller no apunta junto al .exe/.app real, sino dentro del bundle
    interno -- comprobado en vivo: config.json terminaba en
    Ambar.app/Contents/Frameworks/). En su lugar se usa sys.executable, que
    si apunta al binario real:
    - Windows: sys.executable = dist/Ambar/Ambar.exe -> se usa esa carpeta
      directamente (ya es "junto al ejecutable").
    - macOS: sys.executable = Ambar.app/Contents/MacOS/Ambar -- escribir ahi
      DENTRO del bundle se pierde en cada recompilacion (python build.py
      borra y recrea Ambar.app entero, confirmado en vivo). Por eso aqui se
      sube desde el ejecutable hasta encontrar la carpeta ".app" y se usa su
      carpeta *contenedora* -- el mismo sitio donde el usuario ve el icono
      de Ambar.app en Finder, junto a el pero fuera del bundle. PyInstaller
      solo borra/recrea la carpeta Ambar.app en si, no sus hermanos, asi que
      un fichero ahi si sobrevive a los rebuilds (verificado en vivo).
    """
    if not getattr(sys, "frozen", False):
        return resource_dir
    exe_path = sys.executable
    if sys.platform == "darwin":
        path = exe_path
        while path and path != os.path.dirname(path) and not path.endswith(".app"):
            path = os.path.dirname(path)
        return os.path.dirname(path) if path.endswith(".app") else os.path.dirname(exe_path)
    return os.path.dirname(exe_path)


def _build_container(app_dir: str) -> tuple[AppContainer, EventBus]:
    data_dir = _get_data_dir(app_dir)
    config_repository = JsonConfigRepository(os.path.join(data_dir, "config.json"))
    is_first_run = not config_repository.exists()
    app_config = config_repository.load()

    kodi_host = app_config.get("KODI_HOST") or os.environ.get("KODI_HOST", "localhost")
    kodi_port = app_config.get("KODI_PORT") or os.environ.get("KODI_PORT", "8080")
    # MusicBrainzGateway identifica CDs de audio insertados (titulo, artista,
    # pistas, caratula) via la tabla de contenidos del disco -- ver
    # ambar/adapters/musicbrainz/gateway.py. Inyectado en KodiGateway porque
    # es el unico que conoce el TOC (deriva de Files.GetDirectory). Cache en
    # disco junto a config.json/.spotify-cache -- sobrevive a reinicios del
    # launcher, no solo mientras el proceso sigue vivo.
    musicbrainz_gateway = MusicBrainzGateway(cache_path=os.path.join(data_dir, "cd_cache.json"))
    kodi_gateway = KodiGateway(kodi_host, kodi_port, cd_identifier=musicbrainz_gateway)

    spotify_gateway = SpotifyGateway(os.path.join(data_dir, ".spotify-cache"))
    _configure_spotify(spotify_gateway, app_config)

    event_bus = EventBus()
    now_playing_service = NowPlayingService(kodi_gateway, spotify_gateway, event_bus)
    playback_control_service = PlaybackControlService(kodi_gateway, spotify_gateway)
    library_service = LibraryService(kodi_gateway, spotify_gateway)
    smoothing_preset = VU_SMOOTHING_PRESETS.get(
        app_config.get("VU_METER_SMOOTHING", "normal"), VU_SMOOTHING_PRESETS["normal"]
    )
    audio_level_service = AudioLevelService(
        _build_audio_level_source(), event_bus,
        attack_seconds=smoothing_preset["attack"], release_seconds=smoothing_preset["release"],
    )
    system_service = SystemService(
        WebviewWindowController(), audio_level_service, _build_volume_controller(),
        kodi_gateway, spotify_gateway, _build_wake_lock(),
    )
    skins_dir = os.path.join(data_dir, "skins")
    skin_service = SkinService(skins_dir)

    def on_config_updated(config: dict) -> None:
        kodi_gateway.host = config.get("KODI_HOST", kodi_gateway.host)
        kodi_gateway.port = config.get("KODI_PORT", kodi_gateway.port)
        _configure_spotify(spotify_gateway, config)
        if "VU_METER_SMOOTHING" in config:
            preset = VU_SMOOTHING_PRESETS.get(config["VU_METER_SMOOTHING"], VU_SMOOTHING_PRESETS["normal"])
            audio_level_service.set_smoothing(preset["attack"], preset["release"])

    config_service = ConfigService(
        config_repository,
        app_config,
        kodi_default_host=kodi_host,
        kodi_default_port=kodi_port,
        on_update=on_config_updated,
        is_first_run=is_first_run,
    )

    container = AppContainer(
        app_dir=app_dir,
        kodi_gateway=kodi_gateway,
        spotify_gateway=spotify_gateway,
        now_playing_service=now_playing_service,
        playback_control_service=playback_control_service,
        library_service=library_service,
        system_service=system_service,
        config_service=config_service,
        audio_level_service=audio_level_service,
        skin_service=skin_service,
        skins_dir=skins_dir,
        available_screens=_get_available_screens(),
    )
    return container, event_bus


def _start_server(app: Flask, socketio: SocketIO, container: AppContainer, event_bus: EventBus) -> None:
    threading.Thread(
        target=kodi_listen, args=(container.kodi_gateway, container.now_playing_service), daemon=True
    ).start()
    threading.Thread(target=spotify_poll, args=(container.now_playing_service,), daemon=True).start()
    container.audio_level_service.start()
    container.system_service.start()
    print("Servidor corriendo en http://localhost:5005")
    # allow_unsafe_werkzeug: servidor local de un unico kiosko, no expuesto a
    # internet; el servidor de desarrollo de Werkzeug es suficiente aqui.
    socketio.run(app, host="0.0.0.0", port=5005, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


def run(app_dir: str) -> None:
    container, event_bus = _build_container(app_dir)

    app = create_app(container)
    # async_mode="threading" (en vez de "eventlet"): eventlet acapara el hilo
    # en el que corre, y cuando webview.start() toma el hilo principal en
    # macOS (bucle nativo de Cocoa vía PyObjC), el hub de eventlet en el hilo
    # de fondo deja de recibir tiempo de CPU y el servidor se queda colgado
    # (conexiones aceptadas pero nunca respondidas). Con hilos normales no
    # pasa: el accept()/read() bloqueante libera el GIL de verdad. WebSockets
    # reales se mantienen via el paquete simple-websocket.
    socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
    socketio_bridge = SocketIOBridge(socketio)
    event_bus.subscribe(PlaybackStateChanged, socketio_bridge.handle_playback_state_changed)
    event_bus.subscribe(AudioLevelChanged, socketio_bridge.handle_audio_level_changed)

    try:
        import webview
        webview_available = True
    except ImportError:
        webview_available = False

    if webview_available and "--no-window" not in sys.argv:
        # pywebview exige correr en el hilo principal en macOS (Cocoa/AppKit),
        # asi que el servidor se mueve a un hilo de fondo y la ventana nativa
        # se queda en el hilo principal (funciona igual en Windows).
        threading.Thread(
            target=_start_server, args=(app, socketio, container, event_bus), daemon=True
        ).start()
        time.sleep(1)  # esperar a que el servidor levante

        # Pantalla configurada en Ajustes (DEFAULT_SCREEN, indice sobre
        # available_screens) -- si el indice no es valido (monitor
        # desconectado, config antigua, etc.) cae al comportamiento por
        # defecto de pywebview (pantalla principal) en vez de fallar.
        screen_kwargs = {}
        try:
            screen_index = container.config_service.get_public().get("DEFAULT_SCREEN", 0)
            if 0 <= screen_index < len(webview.screens):
                screen_kwargs["screen"] = webview.screens[screen_index]
        except Exception:
            pass

        webview.create_window(
            title="Ámbar",
            url="http://localhost:5005",
            width=1920,
            height=720,
            frameless=True,
            fullscreen=True,
            background_color="#17181a",
            **screen_kwargs,
        )
        webview.start()
    else:
        _start_server(app, socketio, container, event_bus)
