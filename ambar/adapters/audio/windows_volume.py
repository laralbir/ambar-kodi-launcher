from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class WindowsVolumeController:
    """Control del volumen maestro de salida en Windows via pycaw (envuelve
    la interfaz COM IAudioEndpointVolume de WASAPI). Sin verificar en
    hardware/VM Windows real en esta sesion -- probar antes de confiar en
    ello (mismo patron que el resto de adapters de ambar/adapters/audio/)."""

    def _endpoint_volume(self) -> IAudioEndpointVolume:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

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
