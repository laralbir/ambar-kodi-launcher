import ctypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class WindowsWakeLock:
    """Evita que Windows apague la pantalla o entre en reposo, via la API
    nativa SetThreadExecutionState de kernel32 (sin dependencia nueva).

    Sin verificar en hardware/VM Windows real en esta sesion -- probar
    antes de confiar en ello (mismo patron que el resto de adapters
    especificos de Windows en ambar/adapters/)."""

    def acquire(self) -> None:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )

    def release(self) -> None:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
