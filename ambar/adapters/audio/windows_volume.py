import sys

# El VU-metro (windows_wasapi.py) importa `soundcard` antes que este modulo
# y, al hacerlo, inicializa COM en el hilo principal en modo multi-hilo
# (MTA). `comtypes` inicializa COM en cuanto se importa (efecto secundario
# de su propio modulo), pero en modo un-solo-hilo (STA) por defecto -- y
# Windows no permite cambiar el modelo de hilos COM ya establecido en un
# hilo (error RPC_E_CHANGED_MODE / WinError -2147417850). Fijar
# sys.coinit_flags a MTA *antes* del primer `import comtypes` hace que use
# el mismo modo que `soundcard` ya establecio, evitando el choque.
sys.coinit_flags = 0  # COINIT_MULTITHREADED

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class WindowsVolumeController:
    """Control del volumen maestro de salida en Windows via pycaw (envuelve
    la interfaz COM IAudioEndpointVolume de WASAPI). Verificado en vivo en
    el mini PC real: volumen leido/subido/bajado/silenciado de verdad."""

    def _endpoint_volume(self) -> IAudioEndpointVolume:
        # AudioUtilities.GetSpeakers() devuelve un wrapper AudioDevice (no
        # el puntero COM crudo) desde que pycaw dejo de tener version fijada
        # en requirements.txt y se instalo una release reciente -- su
        # propiedad .EndpointVolume ya hace el Activate+QueryInterface por
        # dentro. Confirmado en vivo: la forma vieja de este metodo
        # (devices.Activate(...) a mano) lanzaba AttributeError, que el
        # try/except de get()/set_level()/set_muted() tragaba en silencio
        # -- por eso el volumen se quedaba siempre en 0% sin avisar de nada.
        devices = AudioUtilities.GetSpeakers()
        return devices.EndpointVolume

    def get(self) -> dict:
        try:
            vol = self._endpoint_volume()
            return {
                "level": round(vol.GetMasterVolumeLevelScalar() * 100),
                "muted": bool(vol.GetMute()),
            }
        except Exception:
            return {"level": 0, "muted": False}

    def set_level(self, level: int) -> None:
        try:
            level = max(0, min(100, int(level)))
            self._endpoint_volume().SetMasterVolumeLevelScalar(level / 100, None)
        except Exception:
            pass

    def set_muted(self, muted: bool) -> None:
        try:
            self._endpoint_volume().SetMute(muted, None)
        except Exception:
            pass
