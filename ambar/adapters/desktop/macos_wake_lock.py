import subprocess


class MacWakeLock:
    """Evita que macOS apague la pantalla, salte el salvapantallas o entre
    en reposo, lanzando `caffeinate -d -i` (viene con el sistema, sin
    dependencia adicional) como proceso auxiliar mientras Ambar esta en
    ejecucion. `-d` evita que se apague la pantalla, `-i` evita el reposo
    por inactividad del sistema. Verificado en vivo: el proceso se lanza,
    mantiene la aserción activa, y termina limpio al liberar."""

    def __init__(self):
        self._process: subprocess.Popen | None = None

    def acquire(self) -> None:
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(["caffeinate", "-d", "-i"])
        except Exception:
            self._process = None

    def release(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        self._process = None
