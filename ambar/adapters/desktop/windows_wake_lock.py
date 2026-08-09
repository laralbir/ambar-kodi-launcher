import ctypes
import threading
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

REASSERT_INTERVAL_SECONDS = 30


class WindowsWakeLock:
    """Evita que Windows apague la pantalla o entre en reposo, via la API
    nativa SetThreadExecutionState de kernel32 (sin dependencia nueva).

    Confirmado en vivo en el mini PC real: una unica llamada al arrancar
    (aunque con ES_CONTINUOUS, que segun la documentacion de Microsoft
    deberia persistir indefinidamente hasta la siguiente llamada) no
    bastaba -- la sesion se bloqueo igualmente por el salvapantallas del
    propio Windows. Por eso se reafirma en un hilo de fondo cada
    REASSERT_INTERVAL_SECONDS en vez de fiarse de una sola llamada, mismo
    patron que usan apps tipo "Caffeine" por el mismo motivo.

    Importante -- esto NO sustituye desactivar el salvapantallas/bloqueo
    por inactividad de Windows a nivel de sistema en el equipo del
    kiosko: ninguna app puede evitar de forma soportada el bloqueo de
    sesion "seguro" (ScreenSaverIsSecure) desde fuera, es una proteccion
    de seguridad intencional. Ver README.md/docs para el paso de
    configuracion del equipo (una vez, al preparar el mini PC)."""

    def __init__(self):
        self._active = False
        self._thread: threading.Thread | None = None

    def acquire(self) -> None:
        if self._active:
            return
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while self._active:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            time.sleep(REASSERT_INTERVAL_SECONDS)

    def release(self) -> None:
        self._active = False
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
