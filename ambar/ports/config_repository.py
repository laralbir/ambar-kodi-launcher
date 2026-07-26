from typing import Protocol


class ConfigRepository(Protocol):
    """Puerto de persistencia de la configuracion (host/puerto de Kodi, credenciales de Spotify)."""

    def load(self) -> dict: ...

    def save(self, data: dict) -> None: ...
