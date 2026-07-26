import math
import time
from dataclasses import dataclass
from typing import Sequence

DB_FLOOR = -60.0
DB_CEILING = 0.0
# Ballistica asimetrica: subida rapida para que se note la respuesta al
# instante (no como un VU analogico "de verdad", que resultaba demasiado
# lento/estatico en pantalla), bajada lenta tipo VU clasico (ANSI C16.5,
# ~300ms) para que siga cayendo "a la antigua" cuando el audio calla.
VU_ATTACK_SECONDS = 0.08
VU_RELEASE_SECONDS = 0.3

# Presets de "fluidez" configurables desde Ajustes: escalan la misma
# ballistica asimetrica de arriba. "fast" reacciona casi al instante (mas
# nervioso/vivo, sigue de cerca cada transitorio); "smooth" es mas lento y
# amortiguado (movimiento mas fluido/cinematografico, menos fiel al pico
# exacto). "normal" son las constantes de siempre.
VU_SMOOTHING_PRESETS = {
    "fast": {"attack": 0.04, "release": 0.15},
    "normal": {"attack": VU_ATTACK_SECONDS, "release": VU_RELEASE_SECONDS},
    "smooth": {"attack": 0.18, "release": 0.7},
}


@dataclass
class AudioLevel:
    db: float


class LevelMeter:
    """Convierte fragmentos de muestras PCM (mono, floats en -1..1) en dBFS,
    con ballistica de ataque/liberacion asimetrica: sube rapido (respuesta
    inmediata a la musica) y baja despacio (efecto VU-metro clasico) en vez
    de saltar/pegarse con cada fragmento de audio."""

    def __init__(self, attack_seconds: float = VU_ATTACK_SECONDS, release_seconds: float = VU_RELEASE_SECONDS):
        self._attack_seconds = attack_seconds
        self._release_seconds = release_seconds
        self._smoothed_db = DB_FLOOR
        self._last_update: float | None = None

    def set_ballistics(self, attack_seconds: float, release_seconds: float) -> None:
        self._attack_seconds = attack_seconds
        self._release_seconds = release_seconds

    def update(self, samples: Sequence[float]) -> float:
        raw_db = self._rms_db(samples)
        tau = self._attack_seconds if raw_db > self._smoothed_db else self._release_seconds

        now = time.monotonic()
        dt = tau if self._last_update is None else now - self._last_update
        self._last_update = now

        alpha = 1 - math.exp(-dt / tau) if tau > 0 else 1
        self._smoothed_db += alpha * (raw_db - self._smoothed_db)
        return self._smoothed_db

    @staticmethod
    def _rms_db(samples: Sequence[float]) -> float:
        if not samples:
            return DB_FLOOR
        mean_square = sum(s * s for s in samples) / len(samples)
        if mean_square <= 0:
            return DB_FLOOR
        db = 10 * math.log10(mean_square)  # 20*log10(rms) == 10*log10(rms**2)
        return max(DB_FLOOR, min(DB_CEILING, db))
