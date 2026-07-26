import time
from typing import Sequence

from ambar.domain.audio import LevelMeter
from ambar.domain.events import AudioLevelChanged
from ambar.ports.audio_level_source import AudioLevelSource


class AudioLevelService:
    """Conecta un AudioLevelSource (captura de audio real, al menos estereo)
    con un LevelMeter por canal (dBFS + ballistica) y publica
    AudioLevelChanged en el EventBus, limitando la frecuencia de publicacion
    (los callbacks de audio pueden llegar a cientos por segundo; el frontend
    no necesita mas de ~20 actualizaciones/s)."""

    def __init__(self, source: AudioLevelSource, event_bus, throttle_hz: float = 20.0):
        self._source = source
        self._event_bus = event_bus
        self._meters: list[LevelMeter] = []
        self._min_interval = 1.0 / throttle_hz
        self._last_publish: float | None = None

    def start(self) -> None:
        self._source.start(self._on_samples)

    def stop(self) -> None:
        self._source.stop()

    def _on_samples(self, channels: Sequence[Sequence[float]]) -> None:
        while len(self._meters) < len(channels):
            self._meters.append(LevelMeter())

        db_per_channel = [self._meters[i].update(samples) for i, samples in enumerate(channels)]

        now = time.monotonic()
        if self._last_publish is not None and (now - self._last_publish) < self._min_interval:
            return
        self._last_publish = now
        self._event_bus.publish(AudioLevelChanged(db=db_per_channel))
