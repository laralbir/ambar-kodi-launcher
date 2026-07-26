from typing import Protocol


class VolumeController(Protocol):
    """Puerto que implementan los adapters de volumen del sistema (uno por
    plataforma). Volumen maestro de salida, no el volumen de Kodi/Spotify
    individualmente -- control real del equipo, como el mando o el teclado."""

    def get(self) -> dict: ...

    def set_level(self, level: int) -> None: ...

    def set_muted(self, muted: bool) -> None: ...
