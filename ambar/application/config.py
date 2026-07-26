from typing import Callable

from ambar.ports.config_repository import ConfigRepository


class ConfigService:
    """Lee/actualiza la configuracion persistida y notifica a los adapters que
    dependen de ella (Kodi/Spotify) cuando cambia."""

    def __init__(
        self,
        repository: ConfigRepository,
        initial_config: dict,
        kodi_default_host: str,
        kodi_default_port: str,
        on_update: Callable[[dict], None] | None = None,
        is_first_run: bool = False,
    ):
        self._repository = repository
        self._config = dict(initial_config)
        self._kodi_default_host = kodi_default_host
        self._kodi_default_port = kodi_default_port
        self._on_update = on_update
        self._is_first_run = is_first_run

    def get_public(self) -> dict:
        return {
            "SPOTIFY_CLIENT_ID": self._config.get("SPOTIFY_CLIENT_ID", ""),
            "SPOTIFY_CLIENT_SECRET": self._config.get("SPOTIFY_CLIENT_SECRET", ""),
            "KODI_HOST": self._config.get("KODI_HOST", self._kodi_default_host),
            "KODI_PORT": self._config.get("KODI_PORT", self._kodi_default_port),
            "VU_METER_STYLE": self._config.get("VU_METER_STYLE", "leds"),
            "VU_METER_SMOOTHING": self._config.get("VU_METER_SMOOTHING", "normal"),
            "SHOW_PLAYLIST": self._config.get("SHOW_PLAYLIST", False),
            "SKIN": self._config.get("SKIN", ""),
            "IS_FIRST_RUN": self._is_first_run,
            "DEFAULT_SCREEN": self._config.get("DEFAULT_SCREEN", 0),
        }

    def update(self, data: dict) -> None:
        self._config.update(data)
        self._repository.save(self._config)
        if self._on_update:
            self._on_update(self._config)
