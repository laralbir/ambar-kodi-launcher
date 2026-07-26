class NullVolumeController:
    """Adapter no-op: fallback seguro cuando no hay control de volumen real
    disponible (plataforma no soportada o dependencia nativa ausente). El
    control de volumen del launcher queda inactivo, pero el resto de la app
    sigue funcionando con normalidad."""

    def get(self) -> dict:
        return {"level": 0, "muted": False}

    def set_level(self, level: int) -> None:
        pass

    def set_muted(self, muted: bool) -> None:
        pass
