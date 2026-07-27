import os
import sys

from ambar.application.audio_level import AudioLevelService
from ambar.ports.window_controller import WindowController


class SystemService:
    """Comandos de sistema del kiosko: pantalla completa, salir, apagar, reiniciar."""

    def __init__(
        self,
        window: WindowController,
        audio_level_service: AudioLevelService,
        volume_controller,
        kodi_gateway,
        spotify_gateway,
        screen_wake_lock,
    ):
        self._window = window
        self._audio_level_service = audio_level_service
        self._volume_controller = volume_controller
        self._kodi_gateway = kodi_gateway
        self._spotify_gateway = spotify_gateway
        self._screen_wake_lock = screen_wake_lock

    def start(self) -> None:
        # Evitar que la pantalla se apague/salte el salvapantallas/el equipo
        # entre en reposo mientras Ambar esta en ejecucion -- un kiosko se
        # supone siempre visible.
        self._screen_wake_lock.acquire()

    def get_volume(self) -> dict:
        return self._volume_controller.get()

    def set_volume_level(self, level: int) -> None:
        self._volume_controller.set_level(level)

    def set_volume_muted(self, muted: bool) -> None:
        self._volume_controller.set_muted(muted)

    def execute(self, action: str | None) -> None:
        if action == "fullscreen":
            self._window.toggle_fullscreen()
        elif action == "exit":
            # Parar la reproduccion actual (Kodi/Spotify, lo que este sonando)
            # antes de cerrar -- si no, el audio se queda sonando aunque el
            # launcher ya no este. Ambas llamadas son best-effort (no lanzan
            # si esa fuente no esta activa/configurada).
            self._kodi_gateway.stop()
            self._spotify_gateway.pause()
            self._screen_wake_lock.release()
            # Parar la captura de audio ANTES de cerrar la ventana: si el
            # proceso empieza a apagarse mientras ScreenCaptureKit sigue
            # disparando callbacks nativos de ObjC en un hilo de fondo, el
            # interprete puede reventar al finalizar (crash visible como
            # "Ambar-x se ha cerrado inesperadamente" en macOS).
            self._audio_level_service.stop()
            self._window.close()
        elif action == "shutdown":
            os.system("shutdown /s /t 0" if sys.platform == "win32" else "sudo shutdown -h now")
        elif action == "restart":
            os.system("shutdown /r /t 0" if sys.platform == "win32" else "sudo shutdown -r now")
