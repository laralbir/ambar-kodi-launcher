import os
import sys

from ambar.ports.window_controller import WindowController


class SystemService:
    """Comandos de sistema del kiosko: pantalla completa, salir, apagar, reiniciar."""

    def __init__(self, window: WindowController):
        self._window = window

    def execute(self, action: str | None) -> None:
        if action == "fullscreen":
            self._window.toggle_fullscreen()
        elif action == "exit":
            self._window.close()
        elif action == "shutdown":
            os.system("shutdown /s /t 0" if sys.platform == "win32" else "sudo shutdown -h now")
        elif action == "restart":
            os.system("shutdown /r /t 0" if sys.platform == "win32" else "sudo shutdown -r now")
