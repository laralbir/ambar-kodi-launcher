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
from ambar.adapters.desktop.webview_window import WebviewWindowController
from ambar.adapters.kodi.gateway import KodiGateway
from ambar.adapters.kodi.ws_listener import listen as kodi_listen
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
from ambar.domain.events import AudioLevelChanged, PlaybackStateChanged

DEFAULT_SPOTIFY_REDIRECT_URI = "http://localhost:5005/callback"


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


def _build_container(app_dir: str) -> tuple[AppContainer, EventBus]:
    config_repository = JsonConfigRepository(os.path.join(app_dir, "config.json"))
    is_first_run = not config_repository.exists()
    app_config = config_repository.load()

    kodi_host = app_config.get("KODI_HOST") or os.environ.get("KODI_HOST", "localhost")
    kodi_port = app_config.get("KODI_PORT") or os.environ.get("KODI_PORT", "8080")
    kodi_gateway = KodiGateway(kodi_host, kodi_port)

    spotify_gateway = SpotifyGateway(os.path.join(app_dir, ".spotify-cache"))
    _configure_spotify(spotify_gateway, app_config)

    event_bus = EventBus()
    now_playing_service = NowPlayingService(kodi_gateway, spotify_gateway, event_bus)
    playback_control_service = PlaybackControlService(kodi_gateway, spotify_gateway)
    library_service = LibraryService(kodi_gateway, spotify_gateway)
    audio_level_service = AudioLevelService(_build_audio_level_source(), event_bus)
    system_service = SystemService(WebviewWindowController(), audio_level_service, _build_volume_controller())
    skins_dir = os.path.join(app_dir, "skins")
    skin_service = SkinService(skins_dir)

    def on_config_updated(config: dict) -> None:
        kodi_gateway.host = config.get("KODI_HOST", kodi_gateway.host)
        kodi_gateway.port = config.get("KODI_PORT", kodi_gateway.port)
        _configure_spotify(spotify_gateway, config)

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
    )
    return container, event_bus


def _start_server(app: Flask, socketio: SocketIO, container: AppContainer, event_bus: EventBus) -> None:
    threading.Thread(
        target=kodi_listen, args=(container.kodi_gateway, container.now_playing_service), daemon=True
    ).start()
    threading.Thread(target=spotify_poll, args=(container.now_playing_service,), daemon=True).start()
    container.audio_level_service.start()
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
        webview.create_window(
            title="Ámbar",
            url="http://localhost:5005",
            width=1920,
            height=720,
            frameless=True,
            fullscreen=True,
            background_color="#17181a",
        )
        webview.start()
    else:
        _start_server(app, socketio, container, event_bus)
