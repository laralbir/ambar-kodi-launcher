from ambar.ports.audio_level_source import OnSamples


class NullAudioLevelSource:
    """Adapter no-op: nunca llama al callback. Fallback seguro cuando no hay
    captura de audio real disponible (plataforma no soportada, dependencia
    nativa ausente, o permiso denegado) para que el resto de la app siga
    funcionando y el VU-metro simplemente quede inactivo."""

    def start(self, on_samples: OnSamples) -> None:
        pass

    def stop(self) -> None:
        pass
