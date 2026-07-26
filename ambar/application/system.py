import os
import socket
import sys

from ambar.application.audio_level import AudioLevelService
from ambar.ports.window_controller import WindowController


class SystemService:
    """Comandos de sistema del kiosko: pantalla completa, salir, apagar, reiniciar."""

    def __init__(self, window: WindowController, audio_level_service: AudioLevelService):
        self._window = window
        self._audio_level_service = audio_level_service

    def get_lan_ip(self) -> str | None:
        """IP del equipo en la red local, para mostrar en el asistente de
        Spotify la URL exacta que hay que abrir desde otro dispositivo
        (no hace falta que el usuario la busque a mano)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            finally:
                s.close()
        except Exception:
            return None

    def execute(self, action: str | None) -> None:
        if action == "fullscreen":
            self._window.toggle_fullscreen()
        elif action == "exit":
            # Parar la captura de audio ANTES de cerrar: si el proceso empieza
            # a apagarse mientras ScreenCaptureKit sigue disparando callbacks
            # nativos de ObjC en un hilo de fondo, el interprete puede
            # reventar al finalizar (crash visible como "Ambar-x se ha
            # cerrado inesperadamente" en macOS).
            self._audio_level_service.stop()
            self._window.close()
        elif action == "shutdown":
            os.system("shutdown /s /t 0" if sys.platform == "win32" else "sudo shutdown -h now")
        elif action == "restart":
            os.system("shutdown /r /t 0" if sys.platform == "win32" else "sudo shutdown -r now")
